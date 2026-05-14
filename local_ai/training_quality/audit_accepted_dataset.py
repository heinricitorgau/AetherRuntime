#!/usr/bin/env python3
"""Semantic audit of the accepted training dataset.

Reads : splits/accepted/combined.jsonl
Runs  : semantic_validator on every code_generation record
Writes: reports/semantic_report.json
        reports/semantic_report.md
        reports/semantic_accepted.jsonl
        reports/semantic_rejected.jsonl

Usage:
    python local_ai/training_quality/audit_accepted_dataset.py
    python local_ai/training_quality/audit_accepted_dataset.py --strict
    python local_ai/training_quality/audit_accepted_dataset.py \\
        --input local_ai/ingest/output/training/splits/accepted/combined.jsonl \\
        --out-dir local_ai/training_quality/reports
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from semantic_validator import validate
from _common import load_jsonl, now_iso, training_dir


# ── I/O helpers ────────────────────────────────────────────────────────────

def _write_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _write_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Markdown report ────────────────────────────────────────────────────────

def _build_md(report: dict) -> str:
    lines: list[str] = []
    a = lines.append

    a("# Semantic Audit Report")
    a("")
    a(f"Generated: {report['timestamp']}")
    a(f"Input: `{report['input']}`")
    a("")
    a("## Summary")
    a("")
    a(f"| Metric | Count |")
    a(f"|--------|-------|")
    a(f"| code_generation records checked | {report['checked']} |")
    a(f"| Semantic accepted | {report['semantic_accepted']} |")
    a(f"| Semantic rejected | {report['semantic_rejected']} |")
    a(f"| Skipped (non-code_gen) | {report['skipped']} |")
    a(f"| Max warnings threshold | {report['max_warnings']} |")
    a(f"| Strict mode | {report['strict']} |")
    a("")

    if report["top_warning_categories"]:
        a("## Top Warning Categories")
        a("")
        for cat, count in report["top_warning_categories"]:
            a(f"- {cat}: {count}")
        a("")

    if report["top_error_categories"]:
        a("## Top Error Categories")
        a("")
        for cat, count in report["top_error_categories"]:
            a(f"- {cat}: {count}")
        a("")

    rejected = [r for r in report["results"] if not r["semantic_accepted"] and not r.get("skipped")]
    if rejected:
        a("## Rejected Records")
        a("")
        for r in rejected:
            a(f"### `{r['id']}`")
            a("")
            a(f"**Reason:** {r['rejection_reason']}")
            a("")
            analysis = r.get("analysis") or {}
            if analysis.get("errors"):
                a("**Errors:**")
                for e in analysis["errors"]:
                    a(f"- {e}")
                a("")
            if analysis.get("warnings"):
                a("**Warnings:**")
                for w in analysis["warnings"][:5]:
                    a(f"- {w}")
                if len(analysis["warnings"]) > 5:
                    a(f"- ... ({len(analysis['warnings']) - 5} more)")
                a("")
    else:
        a("## Rejected Records")
        a("")
        a("None. All code_generation records passed semantic validation.")
        a("")

    a("## Why Compile Pass Is Not Enough")
    a("")
    a("A program can compile and even produce output while still containing semantic bugs:")
    a("")
    a("- `scanf(\"%s\", &intVar)` — writes string bytes into an int, silent memory corruption")
    a("- `strcmp(intVar, ...)` — compares memory addresses, not string content")
    a("- `rand()` without `srand()` — always returns the same sequence")
    a("- `while(1)` without break — program hangs on interactive input in a non-interactive test")
    a("- `array[i-1]` in a loop starting at i=0 — reads before the array")
    a("")
    a("These bugs produce wrong answers or undefined behavior even when compilation succeeds.")
    a("")
    a("## Next Steps")
    a("")
    a("1. Manually review `semantic_rejected.jsonl` — some rejections may be false positives")
    a("2. Fix or regenerate rejected records with a better model or prompt")
    a("3. Use `semantic_accepted.jsonl` as the clean fine-tuning corpus")
    a("")
    a("## Limitations")
    a("")
    a("- Analysis is heuristic, not a full C parser — may miss some bugs or flag false positives")
    a("- Does not check algorithmic correctness (wrong formula, wrong logic)")
    a("- Does not verify that the output matches the exam problem specification")
    a("- Manual review of rejected records is always recommended")

    return "\n".join(lines)


# ── Main audit ─────────────────────────────────────────────────────────────

def _categorise(messages: list[str]) -> list[str]:
    """Extract the first N words of each message as a category label."""
    cats = []
    for msg in messages:
        words = msg.split()
        cats.append(" ".join(words[:6]) if len(words) >= 6 else msg[:60])
    return cats


def audit(
    input_path: Path,
    out_dir: Path,
    strict: bool,
    max_warnings: int | None,
) -> dict:
    if not input_path.exists():
        print(f"[audit] input not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    all_records = load_jsonl(input_path)
    results = []

    for rec in all_records:
        r = validate(rec, strict=strict, max_warnings=max_warnings)
        results.append({**r, "_original": rec})

    code_gen_results = [r for r in results if not r.get("skipped") and r["type"] == "code_generation"]
    accepted_results = [r for r in code_gen_results if r["semantic_accepted"]]
    rejected_results = [r for r in code_gen_results if not r["semantic_accepted"]]
    skipped_count    = sum(1 for r in results if r.get("skipped"))

    # Category counters
    all_warnings = []
    all_errors   = []
    for r in code_gen_results:
        analysis = r.get("analysis") or {}
        all_warnings.extend(_categorise(analysis.get("warnings", [])))
        all_errors.extend(_categorise(analysis.get("errors", [])))

    top_warnings = Counter(all_warnings).most_common(10)
    top_errors   = Counter(all_errors).most_common(10)

    # Determine effective max_warnings
    from semantic_validator import _env_max_warnings
    eff_mw = max_warnings if max_warnings is not None else _env_max_warnings(strict)

    report = {
        "timestamp":              now_iso(),
        "input":                  str(input_path),
        "checked":                len(code_gen_results),
        "semantic_accepted":      len(accepted_results),
        "semantic_rejected":      len(rejected_results),
        "skipped":                skipped_count,
        "strict":                 strict,
        "max_warnings":           eff_mw,
        "top_warning_categories": top_warnings,
        "top_error_categories":   top_errors,
        "results": [
            {k: v for k, v in r.items() if k != "_original"}
            for r in results
        ],
    }

    out_dir.mkdir(parents=True, exist_ok=True)

    _write_json(report, out_dir / "semantic_report.json")
    (out_dir / "semantic_report.md").write_text(
        _build_md(report), encoding="utf-8"
    )
    _write_jsonl(
        [r["_original"] for r in results if r["semantic_accepted"]],
        out_dir / "semantic_accepted.jsonl",
    )
    _write_jsonl(
        [r["_original"] for r in results if not r["semantic_accepted"] and not r.get("skipped")],
        out_dir / "semantic_rejected.jsonl",
    )

    return report


# ── CLI ────────────────────────────────────────────────────────────────────

def main() -> None:
    default_input = (
        Path(__file__).resolve().parent.parent
        / "ingest" / "output" / "training" / "splits" / "accepted" / "combined.jsonl"
    )
    default_out = Path(__file__).resolve().parent / "reports"

    parser = argparse.ArgumentParser(description="Semantic audit of accepted training dataset")
    parser.add_argument("--input",   default=str(default_input))
    parser.add_argument("--out-dir", default=str(default_out))
    parser.add_argument("--strict",  action="store_true",
                        help="Tighter threshold (max 2 warnings instead of 4)")
    parser.add_argument("--max-warnings", type=int, default=None,
                        help="Override max warnings threshold")
    args = parser.parse_args()

    report = audit(
        input_path   = Path(args.input),
        out_dir      = Path(args.out_dir),
        strict       = args.strict,
        max_warnings = args.max_warnings,
    )

    print(f"\nSemantic audit complete")
    print(f"Checked code_generation records: {report['checked']}")
    print(f"Semantic accepted: {report['semantic_accepted']}")
    print(f"Semantic rejected: {report['semantic_rejected']}")
    print(f"Report written to {Path(args.out_dir) / 'semantic_report.md'}")


if __name__ == "__main__":
    main()
