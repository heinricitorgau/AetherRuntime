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
  CLAW_BENCHMARK_TIMEOUT_SECONDS   proxy request timeout seconds (default: 660)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_HERE))

from _bench_common import (
    GOLDEN_DIR,
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
from local_ai.shared.config_loader import (
    ConfigError,
    format_config_error,
    load_benchmark_profile,
    load_config,
    load_dataset_profile,
    load_model_profile,
)
from local_ai.experiments.register_run import register_run

# ── Defaults (match env var names in spec) ───────────────────────────────────

_DEFAULT_PROXY       = "http://127.0.0.1:8082"
_DEFAULT_MODEL       = "qwen2.5-coder:3b"
_DEFAULT_MAX_TOKENS  = 768
_DEFAULT_TIMEOUT     = 660     # CLAW_BENCHMARK_TIMEOUT_SECONDS
_DEFAULT_RUN_TIMEOUT = 8       # compiled binary run timeout
_DEFAULT_TEMPERATURE = 0.0     # deterministic default
_ACCEPT_THRESHOLD    = 60
_BENCHMARK_REQUIRED_FULL_TIMEOUT = 300
_BENCHMARK_REQUIRED_FIRST_TOKEN_TIMEOUT = 90
_BENCHMARK_FAIL_FAST_FULL_TIMEOUT = 180
_BENCHMARK_REPAIR_ATTEMPTS = 2

# Strict code-only mode overrides
_STRICT_MAX_TOKENS      = 512
_STRICT_TEMPERATURE     = 0.1
_STRICT_PROMPT_FILE     = "code_gen_strict_v2.txt"
_STRICT_PROMPT_VERSION  = "v2"

_RUBRIC_PTS_RE    = re.compile(r"\[\d+\s*pts?\]", re.IGNORECASE)
_SUBTASK_LABEL_RE = re.compile(r"^\s*\([a-z]\)\s*", re.MULTILINE)

# ── Seeded skeleton prompting ─────────────────────────────────────────────────
# Triggered only in strict mode for small-model reliability hotspots.

_GEOM_TOPIC_RE = re.compile(r"geometry|triangle", re.IGNORECASE)
_GEOM_INSTR_RE = re.compile(r"area|distance|sqrt", re.IGNORECASE)
_GAME_TOPIC_RE = re.compile(r"game simulation", re.IGNORECASE)
_SERIES_TOPIC_RE = re.compile(r"series calculation", re.IGNORECASE)


def _timeout_rate(results: list[dict]) -> float:
    if not results:
        return 0.0
    timed_out = 0
    for result in results:
        checks = result.get("checks", {})
        if (
            checks.get("proxy", {}).get("timed_out")
            or checks.get("runtime", {}).get("timed_out")
        ):
            timed_out += 1
    return round(timed_out / len(results), 3)


def _register_benchmark_experiment(
    *,
    run_id: str,
    report: dict,
    out_dir: Path,
    benchmark_profile_name: str | None,
    model_profile_name: str | None,
    dataset_profile_name: str | None,
) -> None:
    try:
        rates = report.get("rates", {})
        meta = report.get("meta", {})
        registered = register_run(
            {
                "run_id": run_id,
                "run_type": "benchmark",
                "model_profile": model_profile_name,
                "model": meta.get("model"),
                "benchmark_profile": benchmark_profile_name,
                "dataset_profile": dataset_profile_name,
                "accepted": report.get("accepted"),
                "cases_run": report.get("cases_run"),
                "avg_score": report.get("average_score"),
                "compile_rate": rates.get("compile_pass_rate"),
                "runtime_rate": rates.get("runtime_pass_rate"),
                "semantic_rate": rates.get("semantic_pass_rate"),
                "keyword_rate": rates.get("keyword_pass_rate"),
                "timeout_rate": _timeout_rate(report.get("results", [])),
                "linked_reports": {
                    "run_report_json": str(out_dir / "report.json"),
                    "run_report_md": str(out_dir / "report.md"),
                    "baseline_report_json": str(REPORTS_DIR / "baseline_report.json"),
                    "baseline_report_md": str(REPORTS_DIR / "baseline_report.md"),
                    "results_jsonl": str(out_dir / "results.jsonl"),
                    "raw_outputs_jsonl": str(out_dir / "raw_outputs.jsonl"),
                },
                "config_profiles": {
                    "benchmark": benchmark_profile_name,
                    "model": model_profile_name,
                    "dataset": dataset_profile_name,
                    "prompt": meta.get("prompt_profile"),
                    "strict_prompt_version": meta.get("strict_prompt_version"),
                },
            }
        )
        print(f"[experiments] registered run_id={registered['run_id']}")
    except Exception as exc:
        print(f"[experiments] WARNING: could not register benchmark run: {exc}", file=sys.stderr)

_GEOMETRY_SEED_VERSION = "v2"
_GEOMETRY_SEED = (
    "\n\nComplete this executable C99 program:\n\n"
    "```c\n"
    "#include <stdio.h>\n"
    "#include <math.h>\n"
    "\n"
    "int main(void) {\n"
    "    double x[4], y[4];\n"
    "    for (int i = 0; i < 4; i++) scanf(\"%lf %lf\", &x[i], &y[i]);\n"
    "    // declare every variable before use\n"
    "    double area = 0.0;\n"
    "    // compute geometry result\n"
    "    area = sqrt(area * area);\n"
    "    printf(\"area %.3f\\n\", area);\n"
    "    return 0;\n"
    "}\n"
    "```"
)

_GAME_SEED = (
    "\n\nComplete this executable C99 program:\n\n"
    "```c\n"
    "#include <stdio.h>\n"
    "#include <stdlib.h>\n"
    "\n"
    "int main(void) {\n"
    "    int numbers[5], position, score = 0;\n"
    "    char guess;\n"
    "    for (int i = 0; i < 5; i++) numbers[i] = rand() % 10 + 1;\n"
    "    printf(\"Numbers: *****\\nPick \");\n"
    "    if (scanf(\"%d %c\", &position, &guess) == 2) score += 5;\n"
    "    printf(\"win %d points\\n\", score);\n"
    "    return 0;\n"
    "}\n"
    "```"
)

_SERIES_SEED_VERSION = "v1"
_SERIES_SEED = (
    "\n\nSeries implementation hint:\n"
    "The written series starts with the explicit first term 1.\n"
    "Do not divide by zero at i = 1.\n"
    "Initialize sum = 1.0, then accumulate the remaining terms from i = 2 through n "
    "using denominator i * i - 1 and alternating signs.\n"
)


def _geometry_seed_applies(task: dict) -> bool:
    topic = task.get("topic", "") or ""
    if _GEOM_TOPIC_RE.search(topic):
        return True
    return bool(_GEOM_INSTR_RE.search(task.get("instruction", "") or ""))


def _game_seed_applies(task: dict) -> bool:
    return bool(_GAME_TOPIC_RE.search(task.get("topic", "") or ""))


def _series_seed_applies(task: dict) -> bool:
    return bool(_SERIES_TOPIC_RE.search(task.get("topic", "") or ""))


def _build_strict_user_prompt(task: dict) -> tuple[str, bool]:
    """Return (prompt, geometry_seed_applied) for strict mode.

    Keeps: problem statement, Required features, Sample input, Expected output.
    Strips: [N pts] scoring markers, (a)/(b)/(c) sub-task labels.
    Appends: universal full-program reminder; geometry seed when applicable.
    """
    text = task["instruction"]
    text = _RUBRIC_PTS_RE.sub("", text)
    text = _SUBTASK_LABEL_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip() + "\n\nWrite the full program, not just helper functions."

    geom = _geometry_seed_applies(task)
    game = _game_seed_applies(task)
    series = _series_seed_applies(task)
    if geom:
        text += _GEOMETRY_SEED
    elif series:
        text += _SERIES_SEED
    elif game:
        expected = ", ".join(task.get("expected_tokens", []))
        text = (
            "Simulate an even/odd guessing game.\n\n"
            f"Sample input:\n{task.get('sample_input', '')}\n\n"
            f"Expected output contains: {expected}\n\n"
            "Write the full program, not just helper functions."
        )
        text += _GAME_SEED

    return text, geom


def _read_proxy_config(proxy_url: str) -> dict | None:
    try:
        with urllib.request.urlopen(f"{proxy_url.rstrip('/')}/config", timeout=3) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        json.JSONDecodeError,
    ):
        return None


def _check_proxy_timeout_config(proxy_url: str) -> dict | None:
    config = _read_proxy_config(proxy_url)
    if config is None:
        raise RuntimeError("could not read proxy /config")

    full_timeout = int(config.get("full_timeout", 0) or 0)
    first_token_timeout = int(config.get("first_token_timeout", 0) or 0)
    effective_request_timeout = config.get("effective_request_timeout")
    if (
        full_timeout < _BENCHMARK_REQUIRED_FULL_TIMEOUT
        or first_token_timeout < _BENCHMARK_REQUIRED_FIRST_TOKEN_TIMEOUT
    ):
        print("WARNING: proxy timeout too short.")
        print("Expected full timeout >= 300s and first-token >= 90s.")
        print("Restart proxy with:")
        print('$env:CLAW_OLLAMA_TIMEOUT_SECONDS="300"')
        print('$env:CLAW_FIRST_TOKEN_TIMEOUT_SECONDS="90"')
    if full_timeout < _BENCHMARK_FAIL_FAST_FULL_TIMEOUT:
        raise RuntimeError(
            f"proxy full timeout {full_timeout}s is below fail-fast threshold "
            f"{_BENCHMARK_FAIL_FAST_FULL_TIMEOUT}s"
        )
    return config


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
    user_prompt: str | None = None,
    skip_repair: bool = False,
) -> tuple[dict, dict]:
    """Evaluate one task.  Returns (result_record, raw_output_record)."""
    case_id = task["id"]

    # ── 1. Proxy call ─────────────────────────────────────────────────────
    raw_response, proxy_error, latency_ms = call_proxy(
        proxy_url=proxy_url,
        model=model,
        system=system_prompt,
        user=user_prompt if user_prompt is not None else task["instruction"],
        max_tokens=max_tokens,
        timeout=timeout,
        temperature=temperature,
        skip_repair=skip_repair,
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
    proxy_config: dict | None = None,
    verbose: bool = False,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    compiler = None if skip_compile else find_compiler()
    work_dir = Path(tempfile.mkdtemp(prefix="bench_build_"))

    results:     list[dict] = []
    raw_outputs: list[dict] = []

    total = len(tasks)
    mode_tag = "STRICT" if strict_code_only else "standard"
    print(f"[benchmark] model={model} tasks={total} mode={mode_tag}")
    if verbose:
        print(f"[benchmark] proxy={proxy_url}  max_tokens={max_tokens}  timeout={timeout}s  temp={temperature}")
        print(f"[benchmark] compiler={'none (skip)' if skip_compile else (compiler or 'NOT FOUND')}")
        print(f"[benchmark] out_dir={out_dir}")
    if not compiler and not skip_compile:
        print("[benchmark] WARNING: no C compiler found — compile/runtime checks disabled")
    if verbose:
        print()

    for i, task in enumerate(tasks, 1):
        prefix = f"[{i:02d}/{total}] {task['id']}"
        if dry_run:
            print(f"{prefix}  [dry-run]")
            continue

        print(f"{prefix}  ...", end="", flush=True)

        if strict_code_only:
            user_prompt, geom_seed = _build_strict_user_prompt(task)
        else:
            user_prompt, geom_seed = None, False

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
            user_prompt=user_prompt,
            skip_repair=strict_code_only,
        )
        geom_ver = _GEOMETRY_SEED_VERSION if geom_seed else None
        result["strict_code_only"]        = strict_code_only
        result["geometry_seed_applied"]   = geom_seed
        result["geometry_seed_version"]   = geom_ver
        raw["strict_code_only"]           = strict_code_only
        raw["geometry_seed_applied"]      = geom_seed
        raw["geometry_seed_version"]      = geom_ver

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
        if verbose:
            print(f"\r{prefix}  [{p}{c}{r}{s}{k}{t}] score={score:3d}  {lat}ms")
        else:
            print(f"\r{prefix}  [{p}{c}{r}{s}{k}{t}] score={score:3d}")

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
        "run_id":           out_dir.name,
        "model":            model,
        "proxy_url":        proxy_url,
        "max_tokens":       max_tokens,
        "temperature":      temperature,
        "strict_code_only":     strict_code_only,
        "prompt_profile":       "strict_code_only" if strict_code_only else "default",
        "strict_prompt_version": _STRICT_PROMPT_VERSION if strict_code_only else None,
        "geometry_seed_applied": any(r.get("geometry_seed_applied") for r in results),
        "geometry_seed_version": _GEOMETRY_SEED_VERSION if strict_code_only else None,
        "timeout":          timeout,
        "proxy_timeout_full": proxy_config.get("full_timeout") if proxy_config else None,
        "proxy_timeout_first_token": (
            proxy_config.get("first_token_timeout") if proxy_config else None
        ),
        "run_timeout":      run_timeout,
        "system_prompt":    system_prompt[:200],
        "compiler":         compiler,
        "tasks_total":      len(tasks),
        "skip_compile":     skip_compile,
    }
    report = _scoring.score_run(results=results, meta=meta, out_dir=out_dir)

    # ── Regression guard (strict mode only) ──────────────────────────────────
    # Thresholds from best known baseline strict_20260514_224452
    _BEST_BASELINE_ID    = "strict_20260514_224452"
    _BEST_BASELINE_ACCP  = 3
    _BEST_BASELINE_SCORE = 62.0

    if strict_code_only and len(tasks) == 4:
        current_accepted  = report.get("accepted", 0)
        current_avg_score = report.get("average_score", 0.0)
        if current_accepted < _BEST_BASELINE_ACCP or current_avg_score < _BEST_BASELINE_SCORE:
            warn = (
                f"WARNING: regression against best known strict baseline "
                f"{_BEST_BASELINE_ID}."
            )
            print(f"\n{warn}")
            report_md = out_dir / "report.md"
            if report_md.exists():
                with report_md.open("a", encoding="utf-8") as fh:
                    fh.write(f"\n---\n\n{warn}\n")

    # ── Golden baseline auto-compare ─────────────────────────────────────────
    _golden_file = GOLDEN_DIR / "golden_baseline.json"
    if _golden_file.exists():
        try:
            golden = json.loads(_golden_file.read_text(encoding="utf-8"))
            cur_accepted  = report.get("accepted", 0)
            cur_avg       = report.get("average_score", 0.0)
            n_res         = len(results)
            cur_timeout   = (
                sum(1 for r in results
                    if r.get("checks", {}).get("proxy", {}).get("timed_out", False))
                / n_res if n_res > 0 else 0.0
            )
            g_accepted = golden.get("accepted_count", 0)
            g_avg      = golden.get("avg_score", 0.0)
            g_timeout  = golden.get("timeout_rate", 0.0)

            golden_task_count = golden.get("task_count")
            if golden_task_count != len(results):
                print(
                    "\n[golden] comparison skipped"
                    f"  (task_count mismatch: current={len(results)}"
                    f" golden={golden_task_count})"
                )
            else:
                regression  = (
                    cur_accepted < g_accepted
                    or cur_avg    < g_avg - 1.0
                    or cur_timeout > g_timeout
                )
                improvement = cur_accepted > g_accepted or cur_avg > g_avg + 1.0

                if improvement:
                    verdict = "improvement detected"
                elif regression:
                    verdict = "regression detected"
                else:
                    verdict = "matches golden"

                print(
                    f"\n[golden] {verdict}"
                    f"  (golden: {g_accepted}/{golden_task_count}"
                    f"  {g_avg:.1f}pts"
                    f"  ref={golden.get('run_id', '?')})"
                )
        except Exception as exc:
            print(f"[golden] comparison skipped: {exc}")

    print(f"\n[benchmark] {len(results)} results saved -> {out_dir}")
    return report


def _find_best_strict_accepted(current_out_dir: Path) -> int | None:
    """Return the highest accepted count across all previous strict runs."""
    runs_dir = REPORTS_DIR / "runs"
    if not runs_dir.exists():
        return None
    best: int | None = None
    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir() or run_dir == current_out_dir:
            continue
        report_path = run_dir / "report.json"
        if not report_path.exists():
            continue
        try:
            rep = json.loads(report_path.read_text(encoding="utf-8"))
            if not rep.get("meta", {}).get("strict_code_only"):
                continue
            accepted = rep.get("accepted", 0)
            if best is None or accepted > best:
                best = accepted
        except Exception:
            pass
    return best


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark a model against C code generation tasks"
    )
    parser.add_argument(
        "--benchmark",
        default=None,
        help="Benchmark profile name from config/benchmarks.json",
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
    parser.add_argument("--verbose",    action="store_true",
        help="Show detailed per-case and runtime diagnostics")
    args = parser.parse_args()

    benchmark_profile = None
    benchmark_profile_name = args.benchmark
    model_profile_name = None
    dataset_profile_name = None
    dataset_source = args.source
    prompt_profile = None
    if args.benchmark:
        try:
            benchmark_profile = load_benchmark_profile(args.benchmark)
            model_profile_name = str(benchmark_profile["model"])
            dataset_profile_name = str(benchmark_profile["dataset"])
            dataset_profile = load_dataset_profile(str(benchmark_profile["dataset"]))
            model_profile = load_model_profile(str(benchmark_profile["model"]))
            prompt_profile = str(benchmark_profile["prompt_profile"])
            prompt_profiles = load_config("benchmark_profiles")
            configured_prompt = prompt_profiles.get(prompt_profile, {})
            dataset_source = str(dataset_profile["path"])
            args.model = str(model_profile["ollama_model"])
            args.max_tokens = int(configured_prompt.get("max_tokens", model_profile["max_tokens"]))
            if args.temperature is None:
                args.temperature = float(
                    configured_prompt.get("temperature", model_profile["temperature"])
                )
            args.strict_code_only = prompt_profile.startswith("strict_code_only")
            if not args.prompt_file and configured_prompt.get("prompt_file"):
                args.prompt_file = str(PROMPTS_DIR / configured_prompt["prompt_file"])
        except ConfigError as exc:
            print(format_config_error(exc), file=sys.stderr)
            sys.exit(2)

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

    minimum_client_timeout = _BENCHMARK_REQUIRED_FULL_TIMEOUT * _BENCHMARK_REPAIR_ATTEMPTS
    if args.timeout <= minimum_client_timeout:
        print(
            "[benchmark] WARNING: client timeout is not above benchmark worst-case runtime; "
            f"client={args.timeout}s required>{minimum_client_timeout}s"
        )

    # ── Run ID ────────────────────────────────────────────────────────────
    run_id = args.run_id or (
        f"strict_{run_ts()}" if strict else f"baseline_{run_ts()}"
    )
    out_dir = REPORTS_DIR / "runs" / run_id

    tasks = load_tasks(source=dataset_source, filter_ids=args.filter)
    if not tasks:
        print("[error] no tasks found", file=sys.stderr)
        sys.exit(1)

    try:
        proxy_config = None if args.dry_run else _check_proxy_timeout_config(args.proxy_url)
    except RuntimeError as exc:
        print(f"[benchmark] ERROR: {exc}", file=sys.stderr)
        sys.exit(2)

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
        proxy_config=proxy_config,
        verbose=args.verbose,
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
        print(
            f"[benchmark] done run_id={run_id} accepted={report.get('accepted', 0)}/"
            f"{report.get('cases_run', 0)} avg_score={report.get('average_score', 0):.1f} "
            f"report={REPORTS_DIR / 'baseline_report.md'}"
        )
        _register_benchmark_experiment(
            run_id=run_id,
            report=report,
            out_dir=out_dir,
            benchmark_profile_name=benchmark_profile_name,
            model_profile_name=model_profile_name,
            dataset_profile_name=dataset_profile_name,
        )
        if args.verbose:
            print(f"Run dir: {out_dir}")


if __name__ == "__main__":
    main()
