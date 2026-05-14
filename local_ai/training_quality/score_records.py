#!/usr/bin/env python3
"""Aggregate validator reports into a per-record quality score.

Score weights:
  compile   40 pts  (binary: compiles or not)
  runtime   30 pts  (match_score * 30)
  keyword   15 pts  (combined_score * 15)
  structure 15 pts  (score * 15)
  ─────────────────
  total    100 pts

Accept threshold: >= 60 pts  (configurable with --threshold)

When compile_report.json is absent (no compiler), compile score is
imputed at 0 and a warning is shown.

Writes reports/score_report.json.

Usage:
    python local_ai/training_quality/score_records.py
    python local_ai/training_quality/score_records.py --threshold 70
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import (
    load_code_gen_records,
    load_report,
    now_iso,
    write_report,
)


_WEIGHTS = {"compile": 40, "runtime": 30, "keyword": 15, "structure": 15}
_DEFAULT_THRESHOLD = 60


def _index(report: dict, key: str = "id") -> dict:
    return {r[key]: r for r in report.get("results", [])}


def score_one(
    rec_id: str,
    compile_idx: dict,
    runtime_idx: dict,
    keyword_idx: dict,
    structure_idx: dict,
    no_compiler: bool,
) -> dict:
    # ── compile (40 pts) ──
    if no_compiler:
        compile_pts = 0
        compile_note = "no_compiler"
    else:
        cr = compile_idx.get(rec_id, {})
        compile_pts = _WEIGHTS["compile"] if cr.get("ok") else 0
        compile_note = "ok" if cr.get("ok") else cr.get("message", "missing")

    # ── runtime (30 pts) ──
    rr = runtime_idx.get(rec_id, {})
    rt_score = rr.get("match", {}).get("match_score", 0.0) if rr.get("ok") else 0.0
    runtime_pts = round(_WEIGHTS["runtime"] * rt_score)
    runtime_note = f"match={rt_score:.2f}"

    # ── keyword (15 pts) ──
    kr = keyword_idx.get(rec_id, {})
    kw_score = kr.get("combined_score", 0.0)
    keyword_pts = round(_WEIGHTS["keyword"] * kw_score)
    keyword_note = f"score={kw_score:.2f}"

    # ── structure (15 pts) ──
    sr = structure_idx.get(rec_id, {})
    st_score = sr.get("score", 0.0)
    structure_pts = round(_WEIGHTS["structure"] * st_score)
    structure_note = f"score={st_score:.2f}  issues={sr.get('issues', [])}"

    total = compile_pts + runtime_pts + keyword_pts + structure_pts
    return {
        "id": rec_id,
        "total": total,
        "breakdown": {
            "compile":   {"pts": compile_pts,   "note": compile_note},
            "runtime":   {"pts": runtime_pts,   "note": runtime_note},
            "keyword":   {"pts": keyword_pts,   "note": keyword_note},
            "structure": {"pts": structure_pts, "note": structure_note},
        },
    }


def run(threshold: int = _DEFAULT_THRESHOLD) -> dict:
    compile_report   = load_report("compile_report.json")
    runtime_report   = load_report("runtime_report.json")
    keyword_report   = load_report("keyword_report.json")
    structure_report = load_report("structure_report.json")

    no_compiler = not compile_report or compile_report.get("compiler") is None

    if no_compiler:
        print("[score] compile_report absent or compiler=null — compile score will be 0", file=sys.stderr)
    if not keyword_report:
        print("[score] keyword_report absent — keyword score will be 0", file=sys.stderr)
    if not structure_report:
        print("[score] structure_report absent — structure score will be 0", file=sys.stderr)

    compile_idx   = _index(compile_report)
    runtime_idx   = _index(runtime_report)
    keyword_idx   = _index(keyword_report)
    structure_idx = _index(structure_report)

    records = load_code_gen_records()
    scores = []

    for rec in records:
        s = score_one(
            rec["id"],
            compile_idx, runtime_idx, keyword_idx, structure_idx,
            no_compiler=no_compiler,
        )
        accepted = s["total"] >= threshold
        s["accepted"] = accepted
        s["threshold"] = threshold
        scores.append(s)

    scores.sort(key=lambda x: x["total"], reverse=True)

    accepted_n = sum(1 for s in scores if s["accepted"])

    # ── print leaderboard ──
    print(f"\n{'ID':<30} {'Total':>6}  {'C':>4} {'R':>4} {'K':>4} {'S':>4}  Accept")
    print("─" * 65)
    for s in scores:
        bd = s["breakdown"]
        marker = "YES" if s["accepted"] else "no"
        print(
            f"  {s['id']:<28} {s['total']:>6}  "
            f"{bd['compile']['pts']:>4} {bd['runtime']['pts']:>4} "
            f"{bd['keyword']['pts']:>4} {bd['structure']['pts']:>4}  {marker}"
        )
    print(f"\nAccepted: {accepted_n}/{len(scores)}  (threshold={threshold})")

    report = {
        "validator": "score",
        "timestamp": now_iso(),
        "threshold": threshold,
        "weights": _WEIGHTS,
        "total_records": len(scores),
        "accepted": accepted_n,
        "rejected": len(scores) - accepted_n,
        "no_compiler": no_compiler,
        "scores": scores,
    }
    path = write_report(report, "score_report.json")
    print(f"[score] report -> {path}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate validator scores per training record")
    parser.add_argument("--threshold", type=int, default=_DEFAULT_THRESHOLD,
                        help=f"Minimum score to accept a record (default: {_DEFAULT_THRESHOLD})")
    args = parser.parse_args()
    run(threshold=args.threshold)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
