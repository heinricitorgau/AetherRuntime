#!/usr/bin/env python3
"""Lock a benchmark run as the golden baseline reference.

Reads:  reports/runs/<run_id>/report.json
Writes: golden/golden_baseline.json   (overwrites any existing golden)

Usage:
  python local_ai/benchmark/lock_golden_baseline.py --run-id strict_20260515_043031
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from _bench_common import GOLDEN_DIR, REPORTS_DIR, now_iso, write_json

GOLDEN_FILE = GOLDEN_DIR / "golden_baseline.json"


def lock_golden(run_id: str) -> dict:
    report_path = REPORTS_DIR / "runs" / run_id / "report.json"
    if not report_path.exists():
        print(f"[golden] report not found: {report_path}", file=sys.stderr)
        sys.exit(1)

    rep   = json.loads(report_path.read_text(encoding="utf-8"))
    meta  = rep.get("meta", {})
    rates = rep.get("rates", {})

    results = rep.get("results", [])
    n = len(results)
    timeout_count = sum(
        1 for r in results
        if r.get("checks", {}).get("proxy", {}).get("timed_out", False)
    )
    timeout_rate = round(timeout_count / n, 3) if n > 0 else 0.0

    golden = {
        "run_id":             run_id,
        "model":              meta.get("model", rep.get("model", "?")),
        "prompt_profile":     meta.get("prompt_profile", "default"),
        "strict_code_only":   bool(meta.get("strict_code_only", False)),
        "prompt_version":     meta.get("strict_prompt_version"),
        "max_tokens":         meta.get("max_tokens"),
        "temperature":        meta.get("temperature"),
        "task_count":         rep.get("cases_run", n),
        "accepted_count":     rep.get("accepted", 0),
        "avg_score":          rep.get("average_score", 0.0),
        "compile_pass_rate":  rates.get("compile_pass_rate", 0.0),
        "runtime_pass_rate":  rates.get("runtime_pass_rate", 0.0),
        "semantic_pass_rate": rates.get("semantic_pass_rate", 0.0),
        "keyword_pass_rate":  rates.get("keyword_pass_rate", 0.0),
        "timeout_rate":       timeout_rate,
        "created_at":         now_iso(),
    }

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    write_json(golden, GOLDEN_FILE)
    return golden


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lock a benchmark run as the golden baseline"
    )
    parser.add_argument("--run-id", required=True, help="Run ID to lock as golden baseline")
    args = parser.parse_args()

    golden = lock_golden(args.run_id)

    print(f"\nGolden baseline locked: {GOLDEN_FILE}")
    print(f"  run_id:          {golden['run_id']}")
    print(f"  model:           {golden['model']}")
    print(f"  prompt_profile:  {golden['prompt_profile']}")
    print(f"  prompt_version:  {golden['prompt_version']}")
    print(f"  max_tokens:      {golden['max_tokens']}")
    print(f"  temperature:     {golden['temperature']}")
    print(f"  accepted:        {golden['accepted_count']}/{golden['task_count']}")
    print(f"  avg score:       {golden['avg_score']:.1f}")
    print(f"  compile rate:    {golden['compile_pass_rate']:.0%}")
    print(f"  runtime rate:    {golden['runtime_pass_rate']:.0%}")
    print(f"  semantic rate:   {golden['semantic_pass_rate']:.0%}")
    print(f"  keyword rate:    {golden['keyword_pass_rate']:.0%}")
    print(f"  timeout rate:    {golden['timeout_rate']:.0%}")
    print(f"  created_at:      {golden['created_at']}")


if __name__ == "__main__":
    main()