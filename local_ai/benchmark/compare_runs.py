#!/usr/bin/env python3
"""Compare two benchmark runs side-by-side.

Reads:  reports/runs/<base>/results.jsonl
        reports/runs/<new>/results.jsonl
Writes: reports/comparison_report.md
        reports/comparison_report.json

Usage:
  python local_ai/benchmark/compare_runs.py --base <run_id> --new <run_id>
  python local_ai/benchmark/compare_runs.py --base strict_20260514_222958 --new strict_20260514_223526
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from _bench_common import REPORTS_DIR, load_jsonl, now_iso, write_json


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_run(run_id: str) -> tuple[list[dict], dict, dict]:
    """Return (results, meta, aggregate_rates) for a run."""
    run_dir      = REPORTS_DIR / "runs" / run_id
    results_path = run_dir / "results.jsonl"
    report_path  = run_dir / "report.json"

    if not results_path.exists():
        print(f"[compare] results not found: {results_path}", file=sys.stderr)
        sys.exit(1)

    results = load_jsonl(results_path)
    meta    = {}
    rates   = {}
    if report_path.exists():
        rep   = json.loads(report_path.read_text(encoding="utf-8"))
        meta  = rep.get("meta", {})
        rates = rep.get("rates", {})
        meta.setdefault("accepted",      rep.get("accepted", 0))
        meta.setdefault("average_score", rep.get("average_score", 0.0))
    return results, meta, rates


# ── Comparison logic ──────────────────────────────────────────────────────────

def _check_rate(results: list[dict], key: str) -> float:
    if not results:
        return 0.0
    return sum(
        1 for r in results
        if r.get("checks", {}).get(key, {}).get("passed")
    ) / len(results)


def compare(base_id: str, new_id: str) -> dict:
    base_results, base_meta, base_rates = _load_run(base_id)
    new_results,  new_meta,  new_rates  = _load_run(new_id)

    base_by_id = {r["id"]: r for r in base_results}
    new_by_id  = {r["id"]: r for r in new_results}
    all_ids    = sorted(set(base_by_id) | set(new_by_id))

    newly_broken:   list[dict] = []
    newly_fixed:    list[dict] = []
    unchanged_pass: list[str]  = []
    unchanged_fail: list[str]  = []

    for case_id in all_ids:
        b     = base_by_id.get(case_id)
        n     = new_by_id.get(case_id)
        b_acc = b.get("accepted", False) if b else False
        n_acc = n.get("accepted", False) if n else False

        entry = {
            "id":         case_id,
            "base_score": b.get("score", 0) if b else 0,
            "new_score":  n.get("score", 0) if n else 0,
            "base_compile": b.get("checks", {}).get("compile", {}).get("passed", False) if b else False,
            "new_compile":  n.get("checks", {}).get("compile", {}).get("passed", False) if n else False,
            "base_runtime": b.get("checks", {}).get("runtime", {}).get("passed", False) if b else False,
            "new_runtime":  n.get("checks", {}).get("runtime", {}).get("passed", False) if n else False,
        }
        if b_acc and not n_acc:
            newly_broken.append(entry)
        elif not b_acc and n_acc:
            newly_fixed.append(entry)
        elif b_acc:
            unchanged_pass.append(case_id)
        else:
            unchanged_fail.append(case_id)

    base_scores    = [r.get("score", 0) for r in base_results]
    new_scores     = [r.get("score", 0) for r in new_results]
    base_accepted  = sum(1 for r in base_results if r.get("accepted"))
    new_accepted   = sum(1 for r in new_results  if r.get("accepted"))
    base_avg       = sum(base_scores) / len(base_scores) if base_scores else 0.0
    new_avg        = sum(new_scores)  / len(new_scores)  if new_scores  else 0.0

    return {
        "timestamp":   now_iso(),
        "base_run_id": base_id,
        "new_run_id":  new_id,
        "accepted": {
            "base":  base_accepted,
            "new":   new_accepted,
            "delta": new_accepted - base_accepted,
        },
        "avg_score": {
            "base":  round(base_avg, 1),
            "new":   round(new_avg, 1),
            "delta": round(new_avg - base_avg, 1),
        },
        "compile_pass_rate": {
            "base":  round(_check_rate(base_results, "compile"), 3),
            "new":   round(_check_rate(new_results,  "compile"), 3),
        },
        "runtime_pass_rate": {
            "base":  round(_check_rate(base_results, "runtime"), 3),
            "new":   round(_check_rate(new_results,  "runtime"), 3),
        },
        "newly_broken":   newly_broken,
        "newly_fixed":    newly_fixed,
        "unchanged_pass": unchanged_pass,
        "unchanged_fail": unchanged_fail,
    }


# ── Markdown report ───────────────────────────────────────────────────────────

def _sign(d: int | float) -> str:
    return f"+{d}" if d > 0 else str(d)


def write_comparison_markdown(comp: dict, path: Path) -> None:
    lines: list[str] = []
    a = lines.append

    a("# Benchmark Comparison Report")
    a("")
    a(f"**Base**: `{comp['base_run_id']}`  ")
    a(f"**New**:  `{comp['new_run_id']}`  ")
    a(f"**Generated**: {comp['timestamp']}")
    a("")
    a("---")
    a("")
    a("## Summary")
    a("")
    a("| Metric | Base | New | Delta |")
    a("|--------|-----:|----:|------:|")

    acc = comp["accepted"]
    avg = comp["avg_score"]
    cr  = comp["compile_pass_rate"]
    rr  = comp["runtime_pass_rate"]

    a(f"| Accepted | {acc['base']} | {acc['new']} | {_sign(acc['delta'])} |")
    a(f"| Avg score | {avg['base']:.1f} | {avg['new']:.1f} | {_sign(avg['delta'])} |")
    a(f"| Compile pass | {cr['base']:.0%} | {cr['new']:.0%} | — |")
    a(f"| Runtime pass | {rr['base']:.0%} | {rr['new']:.0%} | — |")
    a("")

    if comp["newly_broken"]:
        a("## Newly Broken (was accepted → now failed)")
        a("")
        a("| Case | Base Score | New Score | Base C | New C | Base R | New R |")
        a("|------|----------:|----------:|:------:|:-----:|:------:|:-----:|")
        for c in comp["newly_broken"]:
            bc = "✓" if c["base_compile"] else "✗"
            nc = "✓" if c["new_compile"]  else "✗"
            br = "✓" if c["base_runtime"] else "✗"
            nr = "✓" if c["new_runtime"]  else "✗"
            a(f"| `{c['id']}` | {c['base_score']} | {c['new_score']} | {bc} | {nc} | {br} | {nr} |")
        a("")

    if comp["newly_fixed"]:
        a("## Newly Fixed (was failed → now accepted)")
        a("")
        a("| Case | Base Score | New Score | Base C | New C | Base R | New R |")
        a("|------|----------:|----------:|:------:|:-----:|:------:|:-----:|")
        for c in comp["newly_fixed"]:
            bc = "✓" if c["base_compile"] else "✗"
            nc = "✓" if c["new_compile"]  else "✗"
            br = "✓" if c["base_runtime"] else "✗"
            nr = "✓" if c["new_runtime"]  else "✗"
            a(f"| `{c['id']}` | {c['base_score']} | {c['new_score']} | {bc} | {nc} | {br} | {nr} |")
        a("")

    if comp["unchanged_pass"]:
        items = ", ".join(f"`{x}`" for x in comp["unchanged_pass"])
        a(f"## Unchanged — still passing: {items}")
        a("")

    if comp["unchanged_fail"]:
        items = ", ".join(f"`{x}`" for x in comp["unchanged_fail"])
        a(f"## Unchanged — still failing: {items}")
        a("")

    if acc["delta"] < 0:
        a("---")
        a("")
        a(f"> **REGRESSION**: accepted count dropped by {abs(acc['delta'])}.")
        a("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two benchmark runs")
    parser.add_argument("--base", required=True, help="Base run ID")
    parser.add_argument("--new",  required=True, help="New run ID to compare against base")
    parser.add_argument(
        "--out-dir", default=None,
        help="Output directory for report files (default: reports/)",
    )
    args = parser.parse_args()

    comp    = compare(args.base, args.new)
    out_dir = Path(args.out_dir) if args.out_dir else REPORTS_DIR

    md_path   = out_dir / "comparison_report.md"
    json_path = out_dir / "comparison_report.json"

    write_comparison_markdown(comp, md_path)
    write_json(comp, json_path)

    acc = comp["accepted"]
    avg = comp["avg_score"]
    cr  = comp["compile_pass_rate"]
    rr  = comp["runtime_pass_rate"]

    print(f"\nComparison: {args.base}  →  {args.new}")
    print(f"  accepted:  {acc['base']} → {acc['new']}  ({acc['delta']:+d})")
    print(f"  avg score: {avg['base']:.1f} → {avg['new']:.1f}  ({avg['delta']:+.1f})")
    print(f"  compile:   {cr['base']:.0%} → {cr['new']:.0%}")
    print(f"  runtime:   {rr['base']:.0%} → {rr['new']:.0%}")

    if comp["newly_broken"]:
        print(f"\n  NEWLY BROKEN ({len(comp['newly_broken'])}):")
        for c in comp["newly_broken"]:
            print(f"    {c['id']}  score: {c['base_score']} → {c['new_score']}")

    if comp["newly_fixed"]:
        print(f"\n  NEWLY FIXED ({len(comp['newly_fixed'])}):")
        for c in comp["newly_fixed"]:
            print(f"    {c['id']}  score: {c['base_score']} → {c['new_score']}")

    print(f"\nReport: {md_path}")

    if acc["delta"] < 0:
        print(f"\nWARNING: regression — accepted dropped by {abs(acc['delta'])}")
        sys.exit(1)


if __name__ == "__main__":
    main()
