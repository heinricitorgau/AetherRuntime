"""generate_retry_dataset.py — build a retry training dataset from failed cases.

Reads:
    local_ai/benchmark/reports/failed_cases.jsonl  (consolidated)
    local_ai/benchmark/reports/runs/*/failed_cases.jsonl  (per-run)
    local_ai/ingest/output/training/splits/  (prompt lookup)
    local_ai/eval_cases/  (eval case prompt lookup)

Writes:
    local_ai/analysis/reports/retry_training_dataset.jsonl

Output record format:
    {
        "failure_type": str,
        "original_prompt": str,
        "bad_output": str,
        "expected_behavior": str,
        "improvement_hint": str,
        "meta": {task_id, model, topic, year, score, checks_summary}
    }
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
if str(_LOCAL_AI.parent) not in sys.path:
    sys.path.insert(0, str(_LOCAL_AI.parent))

from local_ai.shared.jsonl import read_jsonl, write_jsonl
from local_ai.analysis.failure_taxonomy import primary, classify

BENCHMARK_DIR = _LOCAL_AI / "benchmark"
INGEST_DIR    = _LOCAL_AI / "ingest"
EVAL_DIR      = _LOCAL_AI / "eval_cases"
REPORTS_DIR   = _HERE / "reports"

OUTPUT_PATH   = REPORTS_DIR / "retry_training_dataset.jsonl"

# ── prompt lookup ─────────────────────────────────────────────────────────────

def _build_prompt_index() -> dict[str, dict[str, Any]]:
    """Map task_id → {instruction, output, expected_tokens, topic}."""
    index: dict[str, dict[str, Any]] = {}

    # 1. Training splits (highest quality — include reference output)
    for split_file in sorted((INGEST_DIR / "output" / "training" / "splits").glob("*.jsonl")):
        try:
            for r in read_jsonl(split_file):
                tid = r.get("id", "")
                if tid and tid not in index:
                    index[tid] = {
                        "instruction": r.get("instruction", ""),
                        "reference_output": r.get("output", ""),
                        "topic": r.get("metadata", {}).get("topic", ""),
                        "year": r.get("metadata", {}).get("year", 0),
                    }
        except Exception:
            pass

    # 2. accepted/ combined
    combined = INGEST_DIR / "output" / "training" / "splits" / "accepted" / "combined.jsonl"
    if combined.exists():
        try:
            for r in read_jsonl(combined):
                tid = r.get("id", "")
                if tid and tid not in index:
                    index[tid] = {
                        "instruction": r.get("instruction", ""),
                        "reference_output": r.get("output", ""),
                        "topic": r.get("metadata", {}).get("topic", ""),
                        "year": r.get("metadata", {}).get("year", 0),
                    }
        except Exception:
            pass

    # 3. eval_cases JSON files (fallback)
    for ec_file in sorted(EVAL_DIR.rglob("*.json")):
        try:
            data = json.loads(ec_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                cases = data
            elif isinstance(data, dict) and "cases" in data:
                cases = data["cases"]
            elif isinstance(data, dict) and "id" in data:
                cases = [data]
            else:
                continue
            for c in cases:
                tid = c.get("id", "")
                if tid and tid not in index:
                    index[tid] = {
                        "instruction": c.get("prompt", ""),
                        "reference_output": "",
                        "topic": c.get("topic", ""),
                        "year": c.get("year", 0),
                    }
        except Exception:
            pass

    return index


# ── improvement hints ─────────────────────────────────────────────────────────

_HINTS: dict[str, str] = {
    "partial_generation": (
        "The model returned an empty or cut-off response. "
        "Output a complete, self-contained C99 program from the first token. "
        "Do not start with prose — begin immediately with `#include`."
    ),
    "truncation": (
        "The previous output was truncated before the closing `}` of main(). "
        "Produce a shorter, more concise solution that fits within the output budget. "
        "Prioritise correctness of the algorithm over comments or helper functions."
    ),
    "missing_entrypoint": (
        "The previous output was missing `int main()`. "
        "Every submission must include a complete `int main(void) { ... return 0; }` "
        "that reads input from stdin and writes to stdout."
    ),
    "syntax_error": (
        "The previous output contained C syntax errors (stray characters, unclosed blocks, "
        "or markdown fences). Output raw C code only — no ``` fences, no prose. "
        "Verify all braces are balanced and all statements end with `;`."
    ),
    "hallucinated_function": (
        "The previous output called functions or used macros that are not declared "
        "(e.g. `DBL_MAX` without `<float.h>`). "
        "Include every required `#include` and only call standard-library functions "
        "that exist in C99."
    ),
    "array_bounds": (
        "The previous output had an array sizing or indexing error. "
        "Declare arrays with explicit maximum sizes. Use loop indices that stay "
        "strictly within [0, size-1]."
    ),
    "runtime_error": (
        "The code compiled but crashed or produced wrong output. "
        "Trace the expected output step-by-step before writing code. "
        "Make sure all variables are initialised before use."
    ),
    "logic_error": (
        "The output was partially correct but contained an algorithmic mistake. "
        "Re-read the problem statement carefully, focusing on the formula or "
        "termination condition. Write a dry-run example by hand first."
    ),
    "algorithm_mismatch": (
        "The algorithm chosen does not match the problem requirements. "
        "Identify the correct algorithm (search, sort, recursion, simulation) "
        "from the problem description and implement it exactly."
    ),
    "geometry_reasoning": (
        "The previous output failed on a geometry/distance problem. "
        "Include `<math.h>` and use `sqrt()` for distances. "
        "Pay attention to coordinate parsing (`%lf` for `double`), "
        "loop bounds for pairs of points, and the exact output format (%.4f)."
    ),
    "io_format_error": (
        "The output format did not match expectations (wrong precision, missing newlines, "
        "or wrong separators). Check the expected output examples exactly: "
        "use `%.4f` or the specified precision, include all required labels."
    ),
}


def _make_hint(failure_type: str, record: dict) -> str:
    base = _HINTS.get(failure_type, "Review the problem requirements and produce a correct C99 solution.")
    checks = record.get("checks", {})
    runtime = checks.get("runtime", {})
    missing = runtime.get("missing", [])
    comp_errs = checks.get("compile", {}).get("errors", [])

    extras: list[str] = []
    if missing:
        extras.append(f"Expected output tokens not produced: {missing[:3]}")
    if comp_errs:
        extras.append(f"Compiler errors included: {comp_errs[0][:120]}")

    if extras:
        return base + " Additional context: " + "; ".join(extras) + "."
    return base


def _expected_behavior(record: dict) -> str:
    checks = record.get("checks", {})
    runtime = checks.get("runtime", {})
    parts: list[str] = []

    missing = runtime.get("missing", [])
    if missing:
        parts.append(f"Output must contain: {missing}")
    topic = (record.get("task_meta", {}) or {}).get("topic", "")
    if topic:
        parts.append(f"Task: {topic}")
    points = (record.get("task_meta", {}) or {}).get("points", 0)
    if points:
        parts.append(f"Worth {points} points")
    parts.append("Must compile with gcc -std=c99 without errors.")
    parts.append("Must produce correct output on the sample input.")
    return " | ".join(parts)


# ── load + deduplicate failed cases ───────────────────────────────────────────

def _load_all_failed() -> list[dict]:
    records: list[dict] = []

    # consolidated
    cp = BENCHMARK_DIR / "reports" / "failed_cases.jsonl"
    if cp.exists():
        try:
            records.extend(read_jsonl(cp))
        except Exception:
            pass

    # per-run
    runs_dir = BENCHMARK_DIR / "reports" / "runs"
    if runs_dir.exists():
        for run_dir in sorted(runs_dir.iterdir()):
            fc = run_dir / "failed_cases.jsonl"
            if fc.exists():
                try:
                    records.extend(read_jsonl(fc))
                except Exception:
                    pass

    # deduplicate: keep the record with the highest score for each (id, model)
    best: dict[tuple, dict] = {}
    for r in records:
        key = (r.get("id", ""), r.get("model", ""))
        prev = best.get(key)
        if prev is None or (r.get("score", 0) or 0) > (prev.get("score", 0) or 0):
            best[key] = r
    return list(best.values())


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("[generate_retry_dataset] Building prompt index …")
    prompt_index = _build_prompt_index()
    print(f"  {len(prompt_index)} tasks indexed")

    print("[generate_retry_dataset] Loading failed cases …")
    failed = _load_all_failed()
    print(f"  {len(failed)} unique (id, model) failures")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    dataset: list[dict] = []
    skipped_no_prompt = 0

    for r in failed:
        task_id = r.get("id", "")
        model   = r.get("model", "")
        score   = r.get("score", 0) or 0

        prompt_info = prompt_index.get(task_id, {})
        instruction = prompt_info.get("instruction", "")

        if not instruction:
            skipped_no_prompt += 1
            continue

        ftype    = primary(r)
        all_cats = classify(r)
        bad_out  = (r.get("extracted_code") or "").strip()
        if not bad_out:
            bad_out = r.get("checks", {}).get("proxy", {}).get("note", "(no output)")

        checks   = r.get("checks", {})
        entry = {
            "failure_type":       ftype,
            "all_failure_types":  all_cats,
            "original_prompt":    instruction,
            "bad_output":         bad_out,
            "expected_behavior":  _expected_behavior(r),
            "improvement_hint":   _make_hint(ftype, r),
            "meta": {
                "task_id":  task_id,
                "model":    model,
                "topic":    (r.get("task_meta", {}) or {}).get("topic", ""),
                "year":     (r.get("task_meta", {}) or {}).get("year", 0),
                "score":    score,
                "compile_passed":  (checks.get("compile", {}) or {}).get("passed"),
                "runtime_passed":  (checks.get("runtime", {}) or {}).get("match_ratio", 0),
                "truncated":       not (checks.get("truncation", {}) or {}).get("passed", True),
            },
        }
        dataset.append(entry)

    write_jsonl(OUTPUT_PATH, dataset)

    print(f"\n[generate_retry_dataset] Done.")
    print(f"  Records written:    {len(dataset)}")
    print(f"  Skipped (no prompt): {skipped_no_prompt}")
    print(f"  Output: {OUTPUT_PATH}")

    # breakdown
    from collections import Counter
    dist: Counter[str] = Counter(d["failure_type"] for d in dataset)
    print("\n  Failure type distribution in dataset:")
    for ft, cnt in dist.most_common():
        pct = cnt / len(dataset) * 100 if dataset else 0
        print(f"    {ft:<30} {cnt:>4}  ({pct:.1f}%)")


if __name__ == "__main__":
    main()
