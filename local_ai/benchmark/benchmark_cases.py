#!/usr/bin/env python3
"""Load benchmark tasks from the eval_cases directory.

Each task is a self-contained evaluation unit with:
  - A natural-language prompt (sent to the model)
  - Expected C keywords (for keyword validation)
  - Expected output tokens (for runtime validation)
  - Sample input to feed the compiled binary
  - Metadata (year, difficulty, points, topic)

Usage:
    python local_ai/benchmark/benchmark_cases.py
    python local_ai/benchmark/benchmark_cases.py --filter 2021
    python local_ai/benchmark/benchmark_cases.py --list
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from _bench_common import LOCAL_AI_ROOT

EVAL_CASES_DIR = LOCAL_AI_ROOT / "eval_cases" / "c_exam"


# ── Task schema ──────────────────────────────────────────────────────────────

# A Task is a plain dict with these keys (all strings/lists, no nesting):
#
#   id                str     "2021_exam1_001"
#   prompt            str     full natural-language problem statement
#   expected_keywords list    C constructs the solution must use
#   expected_tokens   list    strings that must appear in program output
#   sample_input      str     stdin fed to the compiled binary
#   points            int     exam point value
#   difficulty        str     "easy" | "medium" | "hard"
#   topic             str     e.g. "Series Calculation"
#   year              int
#   exam              str     e.g. "exam1"


def _build_prompt(case: dict) -> str:
    """Construct a concise prompt from an eval case."""
    lines: list[str] = []

    desc = case.get("description", "").strip()
    if desc:
        lines.append(desc)

    features = case.get("required_features", [])
    if features:
        lines.append("\nRequired features:")
        for f in features:
            lines.append(f"  - {f}")

    behavior = case.get("expected_behavior", {})
    sample = case.get("sample_input", "")
    if sample:
        lines.append(f"\nExample input:\n  {sample!r}")

    output_desc = behavior.get("description", "").strip()
    if output_desc:
        lines.append(f"\nExpected behavior:\n  {output_desc}")

    return "\n".join(lines).strip()


def load_from_eval_cases(filter_ids: list[str] | None = None) -> list[dict]:
    """Load all tasks from eval_cases/c_exam/*.json.

    filter_ids: if provided, only include cases whose ID starts with or equals
                any of the given strings. Example: ["2021", "2024_exam1_001"].
    """
    if not EVAL_CASES_DIR.exists():
        print(f"[cases] eval_cases dir not found: {EVAL_CASES_DIR}", file=sys.stderr)
        return []

    tasks: list[dict] = []
    for path in sorted(EVAL_CASES_DIR.glob("*.json")):
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[cases] skip {path.name}: {exc}", file=sys.stderr)
            continue

        case_id = case.get("id", "")
        if not case_id:
            continue

        # Apply filter
        if filter_ids:
            if not any(case_id.startswith(f) or case_id == f for f in filter_ids):
                continue

        behavior   = case.get("expected_behavior", {})
        checker    = case.get("checker_rules", {})

        task: dict = {
            "id":                case_id,
            "prompt":            _build_prompt(case),
            "expected_keywords": checker.get("keywords", []),
            "expected_tokens":   behavior.get("output_contains", []),
            "sample_input":      str(case.get("sample_input", "")),
            "points":            case.get("points", 0),
            "difficulty":        case.get("difficulty", "unknown"),
            "topic":             case.get("topic", "unknown"),
            "year":              int(case_id.split("_")[0]) if case_id[0].isdigit() else 0,
            "exam":              case.get("exam", ""),
        }
        tasks.append(task)

    return tasks


def load_tasks(
    filter_ids: list[str] | None = None,
) -> list[dict]:
    """Public entry point. Returns a list of benchmark tasks."""
    tasks = load_from_eval_cases(filter_ids=filter_ids)
    tasks.sort(key=lambda t: (t["year"], t["id"]))
    return tasks


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="List benchmark tasks")
    parser.add_argument(
        "--filter", "-f", nargs="*",
        help="Only include tasks whose ID starts with these strings",
    )
    parser.add_argument(
        "--list", "-l", action="store_true",
        help="Print one-line summary per task",
    )
    args = parser.parse_args()

    tasks = load_tasks(filter_ids=args.filter)

    if args.list or not args.filter:
        print(f"{'ID':<30} {'Topic':<36} {'Diff':<8} {'Pts':>4}  {'KW':>3}  {'Tokens':>6}")
        print("-" * 90)
        for t in tasks:
            kw  = len(t["expected_keywords"])
            tok = len(t["expected_tokens"])
            print(f"{t['id']:<30} {t['topic']:<36} {t['difficulty']:<8} {t['points']:>4}  {kw:>3}  {tok:>6}")
        print(f"\nTotal tasks: {len(tasks)}")
    else:
        print(json.dumps(tasks, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
