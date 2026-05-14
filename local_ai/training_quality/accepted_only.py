#!/usr/bin/env python3
"""Filter training splits to accepted records only.

Reads reports/score_report.json and rewrites the training splits,
keeping only records whose score >= threshold.

Writes filtered JSONL files to:
  output/training/splits/accepted/
    train.jsonl
    val.jsonl
    test.jsonl
    train_code_generation.jsonl
    accepted_summary.json

Usage:
    python local_ai/training_quality/accepted_only.py
    python local_ai/training_quality/accepted_only.py --threshold 70
    python local_ai/training_quality/accepted_only.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _common import (
    load_jsonl,
    load_report,
    now_iso,
    reports_dir,
    training_dir,
    write_report,
)


_DEFAULT_THRESHOLD = 60


def _write_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run(threshold: int = _DEFAULT_THRESHOLD, dry_run: bool = False) -> dict:
    score_report = load_report("score_report.json")
    if not score_report:
        print("[accepted] score_report.json not found — run score_records.py first", file=sys.stderr)
        sys.exit(1)

    accepted_ids = {
        s["id"] for s in score_report.get("scores", [])
        if s.get("total", 0) >= threshold
    }
    print(f"[accepted] {len(accepted_ids)} records accepted at threshold={threshold}")

    splits_dir  = training_dir() / "splits"
    out_dir     = splits_dir / "accepted"

    split_files = {
        "train": splits_dir / "train.jsonl",
        "val":   splits_dir / "val.jsonl",
        "test":  splits_dir / "test.jsonl",
    }

    summary_counts: dict[str, int] = {}
    all_accepted: list[dict] = []

    for split_name, split_path in split_files.items():
        if not split_path.exists():
            print(f"  [skip] {split_path.name} not found", file=sys.stderr)
            continue

        records = load_jsonl(split_path)
        accepted = [r for r in records if r["id"] in accepted_ids or r.get("type") != "code_generation"]
        summary_counts[split_name] = len(accepted)
        all_accepted.extend(accepted)

        if not dry_run:
            _write_jsonl(accepted, out_dir / f"{split_name}.jsonl")
            code_gen = [r for r in accepted if r.get("type") == "code_generation"]
            if code_gen:
                _write_jsonl(code_gen, out_dir / f"{split_name}_code_generation.jsonl")
            print(f"  {split_name:<6}  {len(records)} -> {len(accepted)} records")
        else:
            print(f"  [dry] {split_name:<6}  {len(records)} -> {len(accepted)} records")

    # Per-record detail
    detail = []
    for s in score_report.get("scores", []):
        detail.append({
            "id": s["id"],
            "score": s["total"],
            "accepted": s["id"] in accepted_ids,
        })

    summary = {
        "timestamp": now_iso(),
        "threshold": threshold,
        "accepted_ids": sorted(accepted_ids),
        "counts": summary_counts,
        "detail": detail,
    }

    if not dry_run:
        _write_jsonl(all_accepted, out_dir / "combined.jsonl")
        (out_dir / "accepted_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n[accepted] wrote {out_dir}")
    else:
        print(f"\n[dry-run] would write {out_dir}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter training splits to accepted records")
    parser.add_argument("--threshold", type=int, default=_DEFAULT_THRESHOLD)
    parser.add_argument("--dry-run", action="store_true", help="Show counts without writing files")
    args = parser.parse_args()
    run(threshold=args.threshold, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
