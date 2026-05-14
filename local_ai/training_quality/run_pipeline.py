#!/usr/bin/env python3
"""Run the full dataset validation pipeline in order.

Steps:
  1. structure_validator  (no compiler needed)
  2. keyword_validator    (no compiler needed)
  3. compile_validator    (requires gcc/cc/clang)
  4. runtime_validator    (requires compile step)
  5. score_records        (aggregates all reports)
  6. accepted_only        (filters splits)

Usage:
    python local_ai/training_quality/run_pipeline.py
    python local_ai/training_quality/run_pipeline.py --threshold 70 --skip-compile
    python local_ai/training_quality/run_pipeline.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import structure_validator
import keyword_validator
import compile_validator
import runtime_validator
import score_records
import accepted_only


def run_pipeline(
    threshold: int = 60,
    skip_compile: bool = False,
    dry_run: bool = False,
) -> None:
    print("\n== Step 1: Structure validation ==")
    structure_validator.run()

    print("\n== Step 2: Keyword validation ==")
    keyword_validator.run()

    if skip_compile:
        print("\n== Step 3: Compile validation  [SKIPPED] ==")
        print("== Step 4: Runtime validation  [SKIPPED] ==")
    else:
        print("\n== Step 3: Compile validation ==")
        compile_report = compile_validator.run()

        if compile_report.get("passed", 0) > 0:
            print("\n== Step 4: Runtime validation ==")
            runtime_validator.run()
        else:
            print("\n== Step 4: Runtime validation  [SKIPPED — no compiled executables] ==")

    print("\n== Step 5: Scoring ==")
    score_records.run(threshold=threshold)

    print("\n== Step 6: Filter accepted records ==")
    accepted_only.run(threshold=threshold, dry_run=dry_run)

    print("\n== Pipeline complete ==")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full dataset validation pipeline")
    parser.add_argument("--threshold", type=int, default=60,
                        help="Minimum score to accept a record (default: 60)")
    parser.add_argument("--skip-compile", action="store_true",
                        help="Skip compile and runtime steps (faster, no compiler needed)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show accepted counts without writing filtered splits")
    args = parser.parse_args()
    run_pipeline(
        threshold=args.threshold,
        skip_compile=args.skip_compile,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
