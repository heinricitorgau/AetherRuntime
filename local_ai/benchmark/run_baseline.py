#!/usr/bin/env python3
"""Run benchmark tasks against the local proxy and record deterministic results.

For each task the runner:
  1. Calls proxy (configurable model, max_tokens, temperature)
  2. Extracts C code from response (fence-first, heuristic fallback)
  3. Checks truncation (unbalanced braces / no trailing '}')
  4. Validates structure (#include, int main, balanced braces)
  5. Compiles with gcc -std=c99 -Wall
  6. Runs compiled binary with task's sample_input
  7. Checks runtime output against expected_tokens
  8. Runs semantic static analysis (scanf type mismatch, infinite loops, ...)
  9. Checks keyword presence (required C constructs)
 10. Computes deterministic score 0-100

Modes:
  default          temperature=0.0  max_tokens=768   prompt=code_gen_v1.txt
  --strict-code-only  temperature=0.1  max_tokens=384   prompt=code_gen_strict.txt
                   Reduces timeout risk by forcing the model to emit code only.

Output files (in reports/runs/<run_id>/):
  raw_outputs.jsonl        complete model responses (full text, no truncation)
  results.jsonl            per-case evaluation records
  baseline_report.json     aggregate metrics
  baseline_report.md       human-readable summary
  passed_cases.jsonl       cases with score >= 60
  failed_cases.jsonl       cases with score < 60

Usage:
  python local_ai/benchmark/run_baseline.py
  python local_ai/benchmark/run_baseline.py --strict-code-only
  python local_ai/benchmark/run_baseline.py --model qwen2.5-coder:3b --run-id baseline_3b
  python local_ai/benchmark/run_baseline.py --source accepted --filter 2021 2022
  python local_ai/benchmark/run_baseline.py --no-compile
  python local_ai/benchmark/run_baseline.py --dry-run

Env:
  CLAW_MODEL                       model name (default: qwen2.5-coder:3b)
  CLAW_PROXY_URL                   proxy base URL (default: http://127.0.0.1:8082)
  CLAW_BENCHMARK_MAX_TOKENS        max tokens per response (default: 768)
  CLAW_BENCHMARK_TIMEOUT_SECONDS   proxy request timeout seconds (default: 180)
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from _bench_common import (
    PROMPTS_DIR,
    REPORTS_DIR,
    call_proxy,
    check_keywords,
    check_output_tokens,
    check_structure,
    compile_code,
    compute_score,
    extract_c,
    find_compiler,
    is_truncated,
    load_prompt_file,
    now_iso,
    run_exe,
    run_ts,
    semantic_check,
    write_json,
    write_jsonl,
)
from benchmark_cases import load_tasks

# ── Defaults (match env var names in spec) ───────────────────────────────────

_DEFAULT_PROXY       = "http://127.0.0.1:8082"
_DEFAULT_MODEL       = "qwen2.5-coder:3b"
_DEFAULT_MAX_TOKENS  = 768
_DEFAULT_TIMEOUT     = 180     # CLAW_BENCHMARK_TIMEOUT_SECONDS
_DEFAULT_RUN_TIMEOUT = 8       # compiled binary run timeout
_DEFAULT_TEMPERATURE = 0.0     # deterministic default
_ACCEPT_THRESHOLD    = 60

# Strict code-only mode overrides
_STRICT_MAX_TOKENS  = 384
_STRICT_TEMPERATURE = 0.1
_STRICT_PROMPT_FILE = "code_gen_strict.txt"


# ── Per-case evaluation ───────────────────────────────────────────────────────

def evaluate_case(
    task: dict,
    proxy_url: str,
    model: str,
    system_prompt: str,
    max_tokens: int,
    timeout: int,
    run_timeout: int,
    compiler: str | None,
    work_dir: Path,
    temperature: float = _DEFAULT_TEMPERATURE,
) -> tuple[dict, dict]:
    """Evaluate one task.  Returns (result_record, raw_output_record)."""
    case_id = task["id"]

    # ── 1. Proxy call ─────────────────────────────────────────────────────
    raw_response, proxy_error, latency_ms = call_proxy(
        proxy_url=proxy_url,
        model=model,
        system=system_prompt,
        user=task["instruction"],
        max_tokens=max_tokens,
        timeout=timeout,
        temperature=temperature,
    )

    proxy_timed_out = proxy_error is not None and (
        "timeout" in proxy_error.lower() or "timed out" in proxy_error.lower()
    )

    raw_record = {
        "id":          case_id,
        "model":       model,
        "timestamp":   now_iso(),
        "latency_ms":  latency_ms,
        "raw_response": raw_response,
        "proxy_error":  proxy_error,
    }

    checks: dict = {}

    # ── 2. Proxy status ───────────────────────────────────────────────────
    checks["proxy"] = {
        "passed":    proxy_error is None,
        "timed_out": proxy_timed_out,
        "note":      proxy_error or "ok",
    }

    # ── 3. Extraction ─────────────────────────────────────────────────────
    if proxy_error:
        extracted_code, extract_method = "", "none"
    else:
        extracted_code, extract_method = extract_c(raw_response)

    # ── 4. Truncation ─────────────────────────────────────────────────────
    truncated = is_truncated(extracted_code) if extracted_code else True
    checks["truncation"] = {
        "passed": not truncated,
        "note":   "ok" if not truncated else "truncated",
    }

    # ── 5. Structure ──────────────────────────────────────────────────────
    if extracted_code:
        struct = check_structure(extracted_code)
    else:
        struct = {"ok": False, "score": 0.0, "issues": ["empty response"], "signals": {}}
    checks["structure"] = {
        "passed": struct["ok"],
        "score":  struct["score"],
        "issues": struct["issues"],
    }

    # ── 6. Compile ────────────────────────────────────────────────────────
    if compiler and extracted_code:
        comp = compile_code(extracted_code, case_id, work_dir, compiler)
    else:
        reason = "no compiler available" if not compiler else "no code extracted"
        comp = {"ok": False, "message": reason, "errors": [], "warnings": [], "exe": None}
    checks["compile"] = {
        "passed":   comp["ok"],
        "message":  comp["message"],
        "errors":   comp.get("errors", [])[:5],
        "warnings": comp.get("warnings", [])[:3],
    }

    # ── 7. Runtime ────────────────────────────────────────────────────────
    if comp.get("exe"):
        run_result = run_exe(comp["exe"], task["sample_input"], timeout=run_timeout)
        out_match  = check_output_tokens(run_result["output"], task["expected_tokens"])
        checks["runtime"] = {
            "passed":      run_result["ok"] and out_match["match_ratio"] > 0,
            "timed_out":   run_result["timed_out"],
            "match_ratio": out_match["match_ratio"],
            "found":       out_match["found"],
            "missing":     out_match["missing"],
            "output_head": run_result["output"][:400],
        }
    else:
        checks["runtime"] = {
            "passed":      False,
            "timed_out":   False,
            "match_ratio": 0.0,
            "found":       [],
            "missing":     task["expected_tokens"],
            "output_head": "",
            "note":        "not run (compile failed or no compiler)",
        }

    # ── 8. Semantic ───────────────────────────────────────────────────────
    checks["semantic"] = semantic_check(extracted_code) if extracted_code else {
        "passed": False, "warnings": [], "errors": ["empty code"], "risk_score": 1.0
    }

    # ── 9. Keywords ───────────────────────────────────────────────────────
    kw = check_keywords(extracted_code, task["expected_keywords"])
    checks["keyword"] = {
        "passed":  kw["score"] >= 0.5 if task["expected_keywords"] else True,
        "score":   kw["score"],
        "found":   kw["found"],
        "missing": kw["missing"],
    }

    # ── 10. Score ─────────────────────────────────────────────────────────
    score_result = compute_score(
        structure_score = struct["score"],
        keyword_score   = kw["score"],
        compile_ok      = comp["ok"],
        runtime_ratio   = checks["runtime"]["match_ratio"],
    )
    accepted = score_result["total"] >= _ACCEPT_THRESHOLD

    result = {
        "id":              case_id,
        "model":           model,
        "timestamp":       now_iso(),
        "latency_ms":      latency_ms,
        "extract_method":  extract_method,
        "extracted_code":  extracted_code[:4000],
        "checks":          checks,
        "score":           score_result["total"],
        "score_breakdown": score_result["breakdown"],
        "accepted":        accepted,
        "task_meta": {
            "topic":      task["topic"],
            "difficulty": task["difficulty"],
            "points":     task["points"],
            "year":       task["year"],
            "exam":       task["exam"],
        },
    }
    return result, raw_record


# ── Main runner ───────────────────────────────────────────────────────────────

def run_benchmark(
    tasks: list[dict],
    proxy_url: str,
    model: str,
    system_prompt: str,
    max_tokens: int,
    timeout: int,
    run_timeout: int,
    out_dir: Path,
    temperature: float = _DEFAULT_TEMPERATURE,
    strict_code_only: bool = False,
    dry_run: bool = False,
    skip_compile: bool = False,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    compiler = None if skip_compile else find_compiler()
    work_dir = Path(tempfile.mkdtemp(prefix="bench_build_"))

    results:     list[dict] = []
    raw_outputs: list[dict] = []

    total = len(tasks)
    mode_tag = "STRICT" if strict_code_only else "standard"
    print(f"\n[benchmark] model={model}  tasks={total}  mode={mode_tag}")
    print(f"[benchmark] proxy={proxy_url}  max_tokens={max_tokens}  timeout={timeout}s  temp={temperature}")
    print(f"[benchmark] compiler={'none (skip)' if skip_compile else (compiler or 'NOT FOUND')}")
    print(f"[benchmark] out_dir={out_dir}")
    if not compiler and not skip_compile:
        print("[benchmark] WARNING: no C compiler found — compile/runtime checks disabled")
    print()

    for i, task in enumerate(tasks, 1):
        prefix = f"[{i:02d}/{total}] {task['id']}"
        if dry_run:
            print(f"{prefix}  [dry-run]")
            continue

        print(f"{prefix}  ", end="", flush=True)

        result, raw = evaluate_case(
            task=task,
            proxy_url=proxy_url,
            model=model,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            timeout=timeout,
            run_timeout=run_timeout,
            compiler=compiler,
            work_dir=work_dir,
            temperature=temperature,
        )
        # Tag strict mode in result for later analysis
        result["strict_code_only"] = strict_code_only
        raw["strict_code_only"]    = strict_code_only

        results.append(result)
        raw_outputs.append(raw)

        chk = result["checks"]
        p   = "P" if chk.get("proxy",     {}).get("passed") else "-"
        c   = "C" if chk.get("compile",   {}).get("passed") else "-"
        r   = "R" if chk.get("runtime",   {}).get("passed") else "-"
        s   = "S" if chk.get("semantic",  {}).get("passed") else "-"
        k   = "K" if chk.get("keyword",   {}).get("passed") else "-"
        t   = "T" if chk.get("truncation",{}).get("passed") else "-"
        score = result["score"]
        lat   = result["latency_ms"]
        print(f"[{p}{c}{r}{s}{k}{t}] score={score:3d}  {lat}ms")

    if dry_run:
        print(f"\n[benchmark] dry-run: {total} tasks listed, no API calls made")
        return {}

    # ── Write output files ────────────────────────────────────────────────
    # raw_outputs keeps the full response text for truncation/waste analysis
    write_jsonl(raw_outputs, out_dir / "raw_outputs.jsonl")
    write_jsonl(results,     out_dir / "results.jsonl")

    passed = [r for r in results if r["accepted"]]
    failed = [r for r in results if not r["accepted"]]
    write_jsonl(passed, out_dir / "passed_cases.jsonl")
    write_jsonl(failed, out_dir / "failed_cases.jsonl")

    # ── Inline scoring ────────────────────────────────────────────────────
    import scoring as _scoring
    meta = {
        "model":            model,
        "proxy_url":        proxy_url,
        "max_tokens":       max_tokens,
        "temperature":      temperature,
        "strict_code_only": strict_code_only,
        "timeout":          timeout,
        "run_timeout":      run_timeout,
        "system_prompt":    system_prompt[:200],
        "compiler":         compiler,
        "tasks_total":      len(tasks),
        "skip_compile":     skip_compile,
    }
    report = _scoring.score_run(results=results, meta=meta, out_dir=out_dir)

    print(f"\n[benchmark] {len(results)} results saved -> {out_dir}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark a model against C code generation tasks"
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("CLAW_MODEL", "").strip() or _DEFAULT_MODEL,
    )
    parser.add_argument(
        "--max-tokens", type=int,
        default=int(os.environ.get("CLAW_BENCHMARK_MAX_TOKENS", _DEFAULT_MAX_TOKENS)),
    )
    parser.add_argument(
        "--timeout", type=int,
        default=int(os.environ.get("CLAW_BENCHMARK_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT)),
        help="Proxy request timeout in seconds",
    )
    parser.add_argument("--run-timeout", type=int, default=_DEFAULT_RUN_TIMEOUT)
    parser.add_argument(
        "--proxy-url",
        default=os.environ.get("CLAW_PROXY_URL", _DEFAULT_PROXY),
    )
    parser.add_argument(
        "--run-id", default=None,
        help="Identifier for this run (default: baseline_<timestamp>)",
    )
    parser.add_argument(
        "--source", default="test",
        choices=["test", "accepted", "all"],
        help="Task source JSONL (default: test = test_code_generation.jsonl)",
    )
    parser.add_argument(
        "--filter", "-f", nargs="*",
        help="Only run tasks whose ID starts with these strings",
    )
    parser.add_argument(
        "--prompt-file", default=None,
        help="Path to system prompt file (default depends on mode)",
    )
    parser.add_argument(
        "--strict-code-only", action="store_true",
        help=(
            "Strict code-only mode: forces max_tokens=384, temperature=0.1, "
            "and uses code_gen_strict.txt prompt to minimise explanation waste."
        ),
    )
    parser.add_argument("--temperature", type=float, default=None,
        help="Override temperature (default: 0.0 standard, 0.1 strict)")
    parser.add_argument("--no-compile", action="store_true")
    parser.add_argument("--dry-run",    action="store_true")
    args = parser.parse_args()

    # ── Resolve strict-mode overrides ────────────────────────────────────
    strict = args.strict_code_only

    effective_max_tokens = (
        _STRICT_MAX_TOKENS if strict else args.max_tokens
    )
    effective_temperature = (
        args.temperature if args.temperature is not None
        else (_STRICT_TEMPERATURE if strict else _DEFAULT_TEMPERATURE)
    )

    if args.prompt_file:
        prompt_path = Path(args.prompt_file)
    elif strict:
        prompt_path = PROMPTS_DIR / _STRICT_PROMPT_FILE
    else:
        prompt_path = PROMPTS_DIR / "code_gen_v1.txt"

    if prompt_path.exists():
        system_prompt = load_prompt_file(prompt_path)
    else:
        system_prompt = (
            "You are a C programming assistant. "
            "Output exactly one complete C99 program. Do not explain."
        )
        print(f"[warn] prompt file not found: {prompt_path}, using built-in default")

    # ── Run ID ────────────────────────────────────────────────────────────
    run_id = args.run_id or (
        f"strict_{run_ts()}" if strict else f"baseline_{run_ts()}"
    )
    out_dir = REPORTS_DIR / "runs" / run_id

    tasks = load_tasks(source=args.source, filter_ids=args.filter)
    if not tasks:
        print("[error] no tasks found", file=sys.stderr)
        sys.exit(1)

    report = run_benchmark(
        tasks=tasks,
        proxy_url=args.proxy_url,
        model=args.model,
        system_prompt=system_prompt,
        max_tokens=effective_max_tokens,
        timeout=args.timeout,
        run_timeout=args.run_timeout,
        out_dir=out_dir,
        temperature=effective_temperature,
        strict_code_only=strict,
        dry_run=args.dry_run,
        skip_compile=args.no_compile,
    )

    if report:
        # Also write top-level shortcuts
        import scoring as _scoring
        write_json(report, REPORTS_DIR / "baseline_report.json")
        _scoring.write_markdown(report, REPORTS_DIR / "baseline_report.md")
        passed_all = [r for r in report.get("results", []) if r.get("accepted")]
        failed_all = [r for r in report.get("results", []) if not r.get("accepted")]
        write_jsonl(passed_all, REPORTS_DIR / "passed_cases.jsonl")
        write_jsonl(failed_all, REPORTS_DIR / "failed_cases.jsonl")

        r = report.get("rates", {})
        print(f"\n{'='*60}")
        print(f"Run ID:          {run_id}")
        print(f"Model:           {args.model}")
        print(f"Mode:            {'STRICT code-only' if strict else 'standard'}")
        print(f"max_tokens:      {effective_max_tokens}")
        print(f"temperature:     {effective_temperature}")
        print(f"Tasks:           {report.get('cases_run', 0)}")
        print(f"  compile:       {r.get('compile_pass_rate', 0):.0%}")
        print(f"  runtime:       {r.get('runtime_pass_rate', 0):.0%}")
        print(f"  semantic:      {r.get('semantic_pass_rate', 0):.0%}")
        print(f"  keyword:       {r.get('keyword_pass_rate', 0):.0%}")
        print(f"  not-truncated: {r.get('truncation_pass_rate', 0):.0%}")
        print(f"  avg score:     {report.get('average_score', 0):.1f}/100")
        print(f"  accepted:      {report.get('accepted', 0)}/{report.get('cases_run', 0)}")
        print(f"{'='*60}")
        print(f"\nReports: {REPORTS_DIR / 'baseline_report.md'}")
        print(f"Run dir: {out_dir}")
        if strict:
            print(f"\nTip: python local_ai/benchmark/report_analysis.py --run-id {run_id}")


if __name__ == "__main__":
    main()
