#!/usr/bin/env python3
"""Load benchmark tasks from SFT training JSONL files.

Primary source: local_ai/ingest/output/training/splits/test_code_generation.jsonl
Fallback source: local_ai/training_quality/reports/semantic_accepted_filled.jsonl

Each task record contains:
  id                  str    "2025_midterm_001"
  instruction         str    full problem prompt (sent verbatim to the model)
  expected_keywords   list   C constructs the solution must use (from eval_cases)
  expected_tokens     list   strings that must appear in program output
  sample_input        str    stdin to feed the compiled binary
  metadata            dict   {year, exam, topic, difficulty, points, source_file}
  points              int    exam point value
  difficulty          str    "easy" | "medium" | "hard"
  topic               str    e.g. "Series Calculation"
  year                int

Usage:
    python local_ai/benchmark/benchmark_cases.py
    python local_ai/benchmark/benchmark_cases.py --source accepted
    python local_ai/benchmark/benchmark_cases.py --filter 2025
    python local_ai/benchmark/benchmark_cases.py --list
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from _bench_common import LOCAL_AI_ROOT

# ── Source paths ─────────────────────────────────────────────────────────────

_SOURCES: dict[str, Path] = {
    "test": (
        LOCAL_AI_ROOT / "ingest" / "output" / "training"
        / "splits" / "test_code_generation.jsonl"
    ),
    "accepted": (
        LOCAL_AI_ROOT / "training_quality" / "reports"
        / "semantic_accepted_filled.jsonl"
    ),
    "all": (
        LOCAL_AI_ROOT / "ingest" / "output" / "training"
        / "splits" / "accepted" / "combined.jsonl"
    ),
}

_EVAL_CASES_ROOT = LOCAL_AI_ROOT / "eval_cases"

# ── Eval-case keyword lookup ──────────────────────────────────────────────────

_KEYWORD_CACHE: dict[str, list[str]] = {}


def _keywords_for(case_id: str) -> list[str]:
    """Return required C keywords from the eval case JSON.  Empty list on miss."""
    if case_id in _KEYWORD_CACHE:
        return _KEYWORD_CACHE[case_id]
    if _EVAL_CASES_ROOT.exists():
        for path in _EVAL_CASES_ROOT.rglob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                cases = payload if isinstance(payload, list) else [payload]
                for d in cases:
                    if d.get("id") == case_id:
                        kw = d.get("checker_rules", {}).get("keywords", [])
                        _KEYWORD_CACHE[case_id] = kw
                        return kw
            except Exception:
                pass
    _KEYWORD_CACHE[case_id] = []
    return []


# ── Instruction parser ────────────────────────────────────────────────────────

_SAMPLE_INPUT_RE  = re.compile(
    r'Sample input:\s*\n(.*?)(?:\n\nExpected output|\Z)', re.DOTALL | re.IGNORECASE
)
_EXPECTED_TOKENS_RE = re.compile(
    r'Expected output contains:\s*(.+?)(?:\n|\Z)', re.IGNORECASE
)


def _parse_instruction(instruction: str) -> tuple[str, list[str]]:
    """Extract (sample_input, expected_tokens) embedded in the instruction text."""
    sample_input = ""
    m = _SAMPLE_INPUT_RE.search(instruction)
    if m:
        sample_input = m.group(1).strip()

    expected_tokens: list[str] = []
    m = _EXPECTED_TOKENS_RE.search(instruction)
    if m:
        raw = m.group(1).strip()
        expected_tokens = [t.strip() for t in raw.split(",") if t.strip()]

    return sample_input, expected_tokens


# ── Record → Task ─────────────────────────────────────────────────────────────

def _record_to_task(rec: dict) -> dict | None:
    """Convert a JSONL record to a benchmark task dict. Returns None to skip."""
    if rec.get("type") != "code_generation":
        return None

    case_id     = rec.get("id", "")
    instruction = rec.get("instruction", "").strip()
    if not case_id or not instruction:
        return None

    meta = rec.get("metadata") or {}

    sample_input, expected_tokens = _parse_instruction(instruction)
    expected_keywords              = _keywords_for(case_id)

    year = meta.get("year", 0)
    if not year and case_id and case_id[0].isdigit():
        try:
            year = int(case_id.split("_")[0])
        except ValueError:
            pass

    return {
        "id":                case_id,
        "instruction":       instruction,
        "expected_keywords": expected_keywords,
        "expected_tokens":   expected_tokens,
        "sample_input":      sample_input,
        "metadata":          meta,
        "points":            meta.get("points", 0),
        "difficulty":        meta.get("difficulty", "unknown"),
        "topic":             meta.get("topic", "unknown"),
        "year":              year,
        "exam":              meta.get("exam", ""),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def load_tasks(
    source: str = "test",
    filter_ids: list[str] | None = None,
) -> list[dict]:
    """Load code_generation benchmark tasks from a JSONL source.

    source:     "test"     -> test_code_generation.jsonl (2025 only, default)
                "accepted" -> semantic_accepted_filled.jsonl (all years, SFT corpus)
                "all"      -> accepted/combined.jsonl
    filter_ids: only include tasks whose ID starts with or exactly matches
                any of the given strings.
    """
    path = _SOURCES.get(source)
    if path is None:
        # Allow a raw file path as source
        path = Path(source)

    if not path.exists():
        # Fall back: test → accepted → all
        fallback_order = ["accepted", "all"]
        for fb in fallback_order:
            fb_path = _SOURCES[fb]
            if fb_path.exists():
                print(
                    f"[cases] {path.name} not found, falling back to {fb_path.name}",
                    file=sys.stderr,
                )
                path = fb_path
                break
        else:
            print(f"[cases] no usable source found (tried: {path})", file=sys.stderr)
            return []

    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    tasks: list[dict] = []
    for rec in records:
        task = _record_to_task(rec)
        if task is None:
            continue
        if filter_ids:
            if not any(
                task["id"].startswith(f) or task["id"] == f for f in filter_ids
            ):
                continue
        tasks.append(task)

    tasks.sort(key=lambda t: (t["year"], t["id"]))
    return tasks


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="List benchmark tasks")
    parser.add_argument(
        "--source", "-s", default="test",
        choices=["test", "accepted", "all"],
        help="JSONL source (default: test)",
    )
    parser.add_argument(
        "--filter", "-f", nargs="*",
        help="Only include tasks whose ID starts with these strings",
    )
    parser.add_argument(
        "--list", "-l", action="store_true",
        help="Print one-line summary per task (default when no --filter)",
    )
    parser.add_argument(
        "--show-prompt", action="store_true",
        help="Print full instruction for each task",
    )
    args = parser.parse_args()

    tasks = load_tasks(source=args.source, filter_ids=args.filter)

    if not tasks:
        print("[cases] no tasks found", file=sys.stderr)
        sys.exit(1)

    if args.show_prompt:
        for t in tasks:
            print(f"=== {t['id']} ===")
            print(t["instruction"])
            print(f"  sample_input:     {t['sample_input']!r}")
            print(f"  expected_tokens:  {t['expected_tokens']}")
            print(f"  expected_keywords:{t['expected_keywords']}")
            print()
    else:
        print(f"{'ID':<30} {'Topic':<38} {'Diff':<8} {'Pts':>4}  {'KW':>3}  {'Tok':>3}")
        print("-" * 92)
        for t in tasks:
            kw  = len(t["expected_keywords"])
            tok = len(t["expected_tokens"])
            print(
                f"{t['id']:<30} {t['topic']:<38} {t['difficulty']:<8} "
                f"{t['points']:>4}  {kw:>3}  {tok:>3}"
            )
        print(f"\nSource: {args.source}  Total: {len(tasks)}")


if __name__ == "__main__":
    main()
