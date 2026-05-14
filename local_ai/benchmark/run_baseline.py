#!/usr/bin/env python3
"""Run a model against benchmark tasks and record deterministic results.

For each task the runner:
  1. Calls the proxy API (configurable model, max_tokens, temperature)
  2. Extracts C code from the response (fence-first, heuristic fallback)
  3. Checks for truncation (unbalanced braces / does not end with '}')
  4. Validates structure (#include, int main, balanced braces)
  5. Compiles with gcc (if available)
  6. Runs the compiled binary with the task's sample_input
  7. Checks runtime output against expected tokens
  8. Runs semantic static analysis (scanf type mismatch, while(1) without break, …)
  9. Checks keyword presence (required C constructs)
 10. Computes a deterministic score (0–100)

All results are saved to reports/runs/<run_id>/results.jsonl.
A summary report is written by scoring.py automatically at the end.

Usage:
    python local_ai/benchmark/run_baseline.py
    python local_ai/benchmark/run_baseline.py --model qwen2.5-coder:3b
    python local_ai/benchmark/run_baseline.py --run-id my_run --max-tokens 2048
    python local_ai/benchmark/run_baseline.py --filter 2021 2022
    python local_ai/benchmark/run_baseline.py --no-compile        # skip compile+runtime
    python local_ai/benchmark/run_baseline.py --dry-run           # print tasks, no API calls

Env:
    CLAW_MODEL               model name override
    CLAW_BENCHMARK_MAX_TOKENS max tokens override
    CLAW_BENCHMARK_TIMEOUT    proxy request timeout in seconds
    CLAW_PROXY_URL            proxy base URL
"""
from __future__ import annotations

import argparse
import json
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
    find_compiler,
    extract_c,
    is_truncated,
    load_prompt_file,
    now_iso,
    run_exe,
    run_ts,
    write_json,
    write_jsonl,
)
from benchmark_cases import load_tasks

# ── Defaults ─────────────────────────────────────────────────────────────────

_DEFAULT_PROXY      = "http://127.0.0.1:8082"
_DEFAULT_MODEL      = "qwen2.5-coder:3b"
_DEFAULT_MAX_TOKENS = 1536
_DEFAULT_TIMEOUT    = 90       # proxy request timeout (seconds)
_DEFAULT_RUN_TIMEOUT = 8       # executable run timeout (seconds)
_DEFAULT_TEMPERATURE = 0.0     # deterministic by default
_ACCEPT_THRESHOLD   = 60


# ── Per-case evaluation ───────────────────────────────────────────────────────

def _semantic_check(code: str) -> dict:
    """Run static analysis.  Returns dict with keys: passed, warnings, errors, risk_score."""
    try:
        from static_analysis import analyse
        result = analyse(code)
        return {
            "passed":     len(result.errors) == 0,
            "warnings":   result.warnings,
            "errors":     result.errors,
            "risk_score": result.risk_score,
        }
    except ImportError:
        return {"passed": True, "warnings": [], "errors": [], "risk_score": 0.0,
                "note": "static_analysis not available"}


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
) -> dict:
    """Run a single benchmark task end-to-end and return a result record."""
    case_id = task["id"]

    # ── 1. Call proxy ──────────────────────────────────────────────────────
    raw_response, proxy_error, latency_ms = call_proxy(
        proxy_url=proxy_url,
        model=model,
        system=system_prompt,
        user=task["prompt"],
        max_tokens=max_tokens,
        timeout=timeout,
        temperature=_DEFAULT_TEMPERATURE,
    )

    proxy_timed_out = proxy_error is not None and "timeout" in proxy_error.lower()

    checks: dict = {}

    # ── 2. Extraction ──────────────────────────────────────────────────────
    if proxy_error:
        extracted_code  = ""
        extract_method  = "none"
        checks["proxy"] = {"passed": False, "note": proxy_error, "timed_out": proxy_timed_out}
    else:
        extracted_code, extract_method = extract_c(raw_response)
        checks["proxy"] = {"passed": True, "note": "ok", "timed_out": False}

    # ── 3. Truncation ──────────────────────────────────────────────────────
    truncated = is_truncated(extracted_code) if extracted_code else True
    checks["truncation"] = {
        "passed": not truncated,
        "note":   "ok" if not truncated else "code appears truncated",
    }

    # ── 4. Structure ───────────────────────────────────────────────────────
    if extracted_code:
        struct = check_structure(extracted_code)
    else:
        struct = {"ok": False, "score": 0.0, "issues": ["empty response"], "signals": {}}
    checks["structure"] = {
        "passed": struct["ok"],
        "score":  struct["score"],
        "issues": struct["issues"],
    }

    # ── 5. Compile ─────────────────────────────────────────────────────────
    if compiler and extracted_code:
        comp = compile_code(extracted_code, case_id, work_dir, compiler)
    else:
        reason = "no compiler" if not compiler else "no code"
        comp = {"ok": False, "message": reason, "errors": [], "warnings": [], "exe": None}
    checks["compile"] = {
        "passed":   comp["ok"],
        "message":  comp["message"],
        "errors":   comp.get("errors", []),
        "warnings": comp.get("warnings", []),
    }

    # ── 6. Runtime ─────────────────────────────────────────────────────────
    if comp["exe"]:
        run_result = run_exe(comp["exe"], task["sample_input"], timeout=run_timeout)
        out_match  = check_output_tokens(run_result["output"], task["expected_tokens"])
        checks["runtime"] = {
            "passed":      run_result["ok"] and out_match["match_ratio"] > 0,
            "timed_out":   run_result["timed_out"],
            "match_ratio": out_match["match_ratio"],
            "found":       out_match["found"],
            "missing":     out_match["missing"],
            "output_head": run_result["output"][:300],
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

    # ── 7. Semantic ────────────────────────────────────────────────────────
    if extracted_code:
        sem = _semantic_check(extracted_code)
    else:
        sem = {"passed": False, "warnings": [], "errors": ["empty code"], "risk_score": 1.0}
    checks["semantic"] = sem

    # ── 8. Keywords ────────────────────────────────────────────────────────
    kw_result = check_keywords(extracted_code, task["expected_keywords"])
    checks["keyword"] = {
        "passed":  kw_result["score"] >= 0.5,
        "score":   kw_result["score"],
        "found":   kw_result["found"],
        "missing": kw_result["missing"],
    }

    # ── 9. Score ───────────────────────────────────────────────────────────
    score_result = compute_score(
        structure_score=struct["score"],
        keyword_score=kw_result["score"],
        compile_ok=comp["ok"],
        runtime_ratio=checks["runtime"]["match_ratio"],
    )

    accepted = score_result["total"] >= _ACCEPT_THRESHOLD

    return {
        "id":             case_id,
        "model":          model,
        "timestamp":      now_iso(),
        "latency_ms":     latency_ms,
        "extract_method": extract_method,
        "raw_response":   raw_response[:4000],
        "extracted_code": extracted_code[:4000],
        "checks":         checks,
        "score":          score_result["total"],
        "score_breakdown": score_result["breakdown"],
        "accepted":       accepted,
        "task_meta": {
            "topic":      task["topic"],
            "difficulty": task["difficulty"],
            "points":     task["points"],
            "year":       task["year"],
            "exam":       task["exam"],
        },
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def run_benchmark(
    tasks: list[dict],
    proxy_url: str,
    model: str,
    system_prompt: str,
    max_tokens: int,
    timeout: int,
    run_timeout: int,
    run_id: str,
    dry_run: bool = False,
    skip_compile: bool = False,
) -> dict:
    out_dir = REPORTS_DIR / "runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    compiler   = None if skip_compile else find_compiler()
    work_dir   = Path(tempfile.mkdtemp(prefix="bench_build_"))
    results    = []

    # Save run metadata before starting
    meta = {
        "run_id":        run_id,
        "timestamp":     now_iso(),
        "model":         model,
        "proxy_url":     proxy_url,
        "max_tokens":    max_tokens,
        "timeout":       timeout,
        "run_timeout":   run_timeout,
        "system_prompt": system_prompt,
        "compiler":      compiler,
        "tasks_total":   len(tasks),
        "skip_compile":  skip_compile,
        "dry_run":       dry_run,
    }
    write_json(meta, out_dir / "meta.json")

    total = len(tasks)
    print(f"\n[benchmark] run_id={run_id}  model={model}  tasks={total}")
    print(f"[benchmark] proxy={proxy_url}  max_tokens={max_tokens}  timeout={timeout}s")
    print(f"[benchmark] compiler={'none (skip)' if skip_compile else (compiler or 'not found')}")
    print()

    for i, task in enumerate(tasks, 1):
        prefix = f"[{i:02d}/{total}] {task['id']}"
        if dry_run:
            print(f"{prefix}  [dry-run skipped]")
            continue

        print(f"{prefix}  ...", end="", flush=True)

        result = evaluate_case(
            task=task,
            proxy_url=proxy_url,
            model=model,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            timeout=timeout,
            run_timeout=run_timeout,
            compiler=compiler,
            work_dir=work_dir,
        )
        results.append(result)

        # One-line status summary
        c  = "C" if result["checks"]["compile"]["passed"] else "-"
        r  = "R" if result["checks"]["runtime"]["passed"] else "-"
        s  = "S" if result["checks"]["semantic"]["passed"] else "-"
        k  = "K" if result["checks"]["keyword"]["passed"]  else "-"
        tr = "T" if result["checks"]["truncation"]["passed"] else "-"
        score = result["score"]
        lat   = result["latency_ms"]
        print(f"  [{c}{r}{s}{k}{tr}] score={score:3d}  {lat}ms")

    if dry_run:
        print(f"\n[benchmark] dry-run: {total} tasks listed, no API calls made")
        return {}

    # Save results JSONL
    results_path = out_dir / "results.jsonl"
    write_jsonl(results, results_path)
    print(f"\n[benchmark] {len(results)} results saved -> {results_path}")

    # Inline scoring
    import scoring as _scoring
    report = _scoring.score_run(results=results, meta=meta, out_dir=out_dir)

    # Also copy to reports/ top-level for easy "latest baseline" access
    write_json(report, REPORTS_DIR / "baseline_report.json")
    _scoring.write_markdown(report, REPORTS_DIR / "baseline_report.md")

    passed = [r for r in results if r["accepted"]]
    failed = [r for r in results if not r["accepted"]]
    write_jsonl(passed, REPORTS_DIR / "passed_cases.jsonl")
    write_jsonl(failed, REPORTS_DIR / "failed_cases.jsonl")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run benchmark tasks against the local proxy model"
    )
    parser.add_argument("--model",
        default=os.environ.get("CLAW_MODEL", "").strip() or _DEFAULT_MODEL,
        help="Model name (default: qwen2.5-coder:3b)")
    parser.add_argument("--max-tokens", type=int,
        default=int(os.environ.get("CLAW_BENCHMARK_MAX_TOKENS", _DEFAULT_MAX_TOKENS)),
        help=f"Max tokens per response (default: {_DEFAULT_MAX_TOKENS})")
    parser.add_argument("--timeout", type=int,
        default=int(os.environ.get("CLAW_BENCHMARK_TIMEOUT", _DEFAULT_TIMEOUT)),
        help=f"Proxy request timeout in seconds (default: {_DEFAULT_TIMEOUT})")
    parser.add_argument("--run-timeout", type=int, default=_DEFAULT_RUN_TIMEOUT,
        help=f"Compiled binary run timeout in seconds (default: {_DEFAULT_RUN_TIMEOUT})")
    parser.add_argument("--proxy-url",
        default=os.environ.get("CLAW_PROXY_URL", _DEFAULT_PROXY))
    parser.add_argument("--run-id",
        default=None,
        help="Identifier for this run (default: baseline_<timestamp>)")
    parser.add_argument("--filter", "-f", nargs="*",
        help="Only run tasks whose ID starts with these strings")
    parser.add_argument("--prompt-file",
        default=str(PROMPTS_DIR / "code_gen_v1.txt"),
        help="Path to the system prompt file")
    parser.add_argument("--no-compile", action="store_true",
        help="Skip compile and runtime checks")
    parser.add_argument("--dry-run", action="store_true",
        help="List tasks without making API calls")
    args = parser.parse_args()

    run_id = args.run_id or f"baseline_{run_ts()}"

    prompt_path = Path(args.prompt_file)
    if not prompt_path.exists():
        # Fall back to default prompt if custom file not found
        default_prompt = (
            "You are a C programming assistant. "
            "Output exactly one complete C99 program. Do not explain."
        )
        print(f"[warn] prompt file not found: {prompt_path}, using built-in default")
        system_prompt = default_prompt
    else:
        system_prompt = load_prompt_file(prompt_path)

    tasks = load_tasks(filter_ids=args.filter)
    if not tasks:
        print("[error] no tasks found", file=sys.stderr)
        sys.exit(1)

    report = run_benchmark(
        tasks=tasks,
        proxy_url=args.proxy_url,
        model=args.model,
        system_prompt=system_prompt,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
        run_timeout=args.run_timeout,
        run_id=run_id,
        dry_run=args.dry_run,
        skip_compile=args.no_compile,
    )

    if report:
        r = report.get("rates", {})
        print(f"\n{'='*50}")
        print(f"Run: {run_id}")
        print(f"Model: {args.model}")
        print(f"Tasks: {report.get('cases_run', 0)}")
        print(f"  compile:  {r.get('compile_pass_rate', 0):.0%}")
        print(f"  runtime:  {r.get('runtime_pass_rate', 0):.0%}")
        print(f"  semantic: {r.get('semantic_pass_rate', 0):.0%}")
        print(f"  keyword:  {r.get('keyword_pass_rate', 0):.0%}")
        print(f"  truncation-free: {r.get('truncation_pass_rate', 0):.0%}")
        print(f"  avg score: {report.get('average_score', 0):.1f}/100")
        print(f"  accepted:  {report.get('accepted', 0)}/{report.get('cases_run', 0)}")
        print(f"{'='*50}")


if __name__ == "__main__":
    main()
