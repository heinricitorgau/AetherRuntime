#!/usr/bin/env python3
"""Split combined.jsonl into train/val/test by year and type.

Split strategy (year-based holdout — natural for exam data):
  train : years 2021–2023
  val   : year  2024
  test  : year  2025

Each split is also written per-type:
  *_code_generation.jsonl  — instruction-tuning records (need output filled)
  *_concept_summary.jsonl  — RAG / reading-context records

Output in local_ai/ingest/output/training/splits/:
  train.jsonl
  val.jsonl
  test.jsonl
  train_code_generation.jsonl
  train_concept_summary.jsonl
  val_code_generation.jsonl
  val_concept_summary.jsonl
  test_code_generation.jsonl
  test_concept_summary.jsonl
  split_summary.json

Usage:
    python local_ai/ingest/split_training.py
    python local_ai/ingest/split_training.py --input path/to/combined.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_TRAIN_YEARS = {2021, 2022, 2023}
_VAL_YEARS   = {2024}
_TEST_YEARS  = {2025}


def _split_label(year: int | None) -> str:
    if year in _TRAIN_YEARS:
        return "train"
    if year in _VAL_YEARS:
        return "val"
    if year in _TEST_YEARS:
        return "test"
    return "train"  # unknown year defaults to train


def _write_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"  wrote {path.name} ({len(records)} records)")


def split_training(input_path: Path) -> dict:
    raw = input_path.read_text(encoding="utf-8")
    records = [json.loads(line) for line in raw.splitlines() if line.strip()]

    buckets: dict[str, list] = {"train": [], "val": [], "test": []}
    for rec in records:
        year = rec.get("metadata", {}).get("year")
        label = _split_label(year)
        buckets[label].append(rec)

    out_dir = input_path.parent / "splits"

    for split, recs in buckets.items():
        _write_jsonl(recs, out_dir / f"{split}.jsonl")

        for rtype in ("code_generation", "concept_summary"):
            subset = [r for r in recs if r.get("type") == rtype]
            if subset:
                _write_jsonl(subset, out_dir / f"{split}_{rtype}.jsonl")

    answered = {
        split: sum(1 for r in recs if r.get("output", "").strip())
        for split, recs in buckets.items()
    }

    summary = {
        "input": str(input_path),
        "output_dir": str(out_dir),
        "split_years": {
            "train": sorted(_TRAIN_YEARS),
            "val":   sorted(_VAL_YEARS),
            "test":  sorted(_TEST_YEARS),
        },
        "counts": {s: len(r) for s, r in buckets.items()},
        "answered": answered,
        "total": len(records),
        "ready_for_sft": sum(answered.values()) > 0,
    }
    summary_path = out_dir / "split_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  wrote split_summary.json")
    return summary


def _print_summary(s: dict) -> None:
    print("\n── Split summary ───────────────────────────────────────────")
    for split in ("train", "val", "test"):
        years = s["split_years"][split]
        n = s["counts"][split]
        ans = s["answered"][split]
        print(f"  {split:<6} years={years}  records={n}  answered={ans}/{n}")
    print(f"  total={s['total']}")
    if not s["ready_for_sft"]:
        print()
        print("  [!] No output fields filled -- not ready for supervised fine-tuning.")
        print("    Run prepare_training.py --fill-answers <dir> to add reference answers,")
        print("    or use the proxy AI eval to generate them.")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Split training JSONL by year into train/val/test")
    parser.add_argument(
        "--input",
        default=str(Path(__file__).resolve().parent / "output" / "training" / "combined.jsonl"),
        help="Path to combined.jsonl (default: output/training/combined.jsonl)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Splitting {input_path.name} ...", file=sys.stderr)
    summary = split_training(input_path)
    _print_summary(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
