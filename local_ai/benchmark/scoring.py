#!/usr/bin/env python3
"""Compute aggregate benchmark metrics from a completed run.

Reads:  reports/runs/<run_id>/results.jsonl
Writes: reports/runs/<run_id>/report.json
        reports/runs/<run_id>/report.md
        reports/runs/<run_id>/passed_cases.jsonl
        reports/runs/<run_id>/failed_cases.jsonl

Metrics produced:
  compile_pass_rate     fraction that compiled successfully
  runtime_pass_rate     fraction with correct output (> 0 tokens matched)
  semantic_pass_rate    fraction with no static-analysis errors
  keyword_pass_rate     fraction with keyword score >= 0.5
  truncation_pass_rate  fraction with complete (non-truncated) code
  proxy_pass_rate       fraction where the proxy responded without error
  average_score         mean score across all cases (0–100)
  accepted_rate         fraction with score >= 60

Also produces per-dimension tables and a by-topic breakdown.

Usage:
    python local_ai/benchmark/scoring.py
    python local_ai/benchmark/scoring.py --run-id baseline_20260514_120000
    python local_ai/benchmark/scoring.py --results-file path/to/results.jsonl
    python local_ai/benchmark/scoring.py --compare run_a run_b
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from _bench_common import REPORTS_DIR, load_jsonl, now_iso, write_json, write_jsonl


# ── Metric computation ───────────────────────────────────────────────────────

def _rate(results: list[dict], check_key: str, sub_key: str = "passed") -> float:
    if not results:
        return 0.0
    return sum(1 for r in results if r.get("checks", {}).get(check_key, {}).get(sub_key)) / len(results)


def _score_bucket(score: int) -> str:
    if score >= 90: return "90-100"
    if score >= 70: return "70-89"
    if score >= 60: return "60-69"
    return "0-59"


def compute_metrics(results: list[dict]) -> dict:
    if not results:
        return {}

    n = len(results)
    scores = [r.get("score", 0) for r in results]

    by_bucket: dict[str, int] = {"90-100": 0, "70-89": 0, "60-69": 0, "0-59": 0}
    for s in scores:
        by_bucket[_score_bucket(s)] += 1

    by_topic: dict[str, dict] = {}
    for r in results:
        topic = r.get("task_meta", {}).get("topic", "unknown")
        if topic not in by_topic:
            by_topic[topic] = {"count": 0, "accepted": 0, "scores": []}
        by_topic[topic]["count"] += 1
        if r.get("accepted"):
            by_topic[topic]["accepted"] += 1
        by_topic[topic]["scores"].append(r.get("score", 0))

    topic_summary = {}
    for topic, data in sorted(by_topic.items()):
        s = data["scores"]
        topic_summary[topic] = {
            "count":    data["count"],
            "accepted": data["accepted"],
            "avg_score": round(sum(s) / len(s), 1) if s else 0.0,
        }

    by_difficulty: dict[str, dict] = {}
    for r in results:
        diff = r.get("task_meta", {}).get("difficulty", "unknown")
        if diff not in by_difficulty:
            by_difficulty[diff] = {"count": 0, "accepted": 0, "scores": []}
        by_difficulty[diff]["count"] += 1
        if r.get("accepted"):
            by_difficulty[diff]["accepted"] += 1
        by_difficulty[diff]["scores"].append(r.get("score", 0))

    diff_summary = {}
    for diff, data in sorted(by_difficulty.items()):
        s = data["scores"]
        diff_summary[diff] = {
            "count":     data["count"],
            "accepted":  data["accepted"],
            "avg_score": round(sum(s) / len(s), 1) if s else 0.0,
        }

    latencies = [r.get("latency_ms", 0) for r in results if r.get("latency_ms", 0) > 0]

    return {
        "cases_run":   n,
        "accepted":    sum(1 for r in results if r.get("accepted")),
        "average_score": round(sum(scores) / n, 1),
        "min_score":   min(scores),
        "max_score":   max(scores),
        "rates": {
            "proxy_pass_rate":      _rate(results, "proxy"),
            "truncation_pass_rate": _rate(results, "truncation"),
            "compile_pass_rate":    _rate(results, "compile"),
            "runtime_pass_rate":    _rate(results, "runtime"),
            "semantic_pass_rate":   _rate(results, "semantic"),
            "keyword_pass_rate":    _rate(results, "keyword"),
            "accepted_rate":        sum(1 for r in results if r.get("accepted")) / n,
        },
        "score_distribution": by_bucket,
        "by_topic":      topic_summary,
        "by_difficulty": diff_summary,
        "latency_ms": {
            "avg": round(sum(latencies) / len(latencies)) if latencies else 0,
            "min": min(latencies) if latencies else 0,
            "max": max(latencies) if latencies else 0,
        },
    }


# ── Markdown report ──────────────────────────────────────────────────────────

def write_markdown(report: dict, path: Path) -> None:
    meta    = report.get("meta", {})
    metrics = report

    lines: list[str] = []
    a = lines.append

    a("# Benchmark Report")
    a("")
    a(f"**Run ID**: `{report.get('run_id', '?')}`  ")
    a(f"**Model**: `{meta.get('model', report.get('model', '?'))}`  ")
    a(f"**Timestamp**: {report.get('timestamp', '?')}  ")
    a(f"**Prompt file**: `{Path(meta.get('system_prompt','?')[:60]).name if meta.get('system_prompt') else '?'}`")
    a("")
    a("---")
    a("")
    a("## Pass Rates")
    a("")
    a("| Dimension | Rate | Count |")
    a("|-----------|-----:|------:|")

    rates   = metrics.get("rates", {})
    n       = metrics.get("cases_run", 0)

    def _row(label: str, key: str) -> None:
        rate  = rates.get(key, 0.0)
        count = round(rate * n)
        a(f"| {label} | {rate:.0%} | {count}/{n} |")

    _row("Proxy response (no timeout/error)", "proxy_pass_rate")
    _row("Code not truncated", "truncation_pass_rate")
    _row("Compile pass", "compile_pass_rate")
    _row("Runtime pass (output matches)", "runtime_pass_rate")
    _row("Semantic pass (no static errors)", "semantic_pass_rate")
    _row("Keyword pass (required constructs)", "keyword_pass_rate")
    _row("**Accepted** (score ≥ 60)", "accepted_rate")
    a("")
    a(f"Average score: **{metrics.get('average_score', 0):.1f}/100**  ")
    a(f"Score range: {metrics.get('min_score', 0)}–{metrics.get('max_score', 0)}")
    a("")
    a("## Score Distribution")
    a("")
    a("| Bucket | Count |")
    a("|--------|------:|")
    for bucket, cnt in sorted(metrics.get("score_distribution", {}).items(), reverse=True):
        a(f"| {bucket} | {cnt} |")
    a("")

    if metrics.get("by_topic"):
        a("## By Topic")
        a("")
        a("| Topic | Count | Accepted | Avg Score |")
        a("|-------|------:|---------:|----------:|")
        for topic, data in sorted(metrics["by_topic"].items()):
            a(f"| {topic} | {data['count']} | {data['accepted']} | {data['avg_score']} |")
        a("")

    if metrics.get("by_difficulty"):
        a("## By Difficulty")
        a("")
        a("| Difficulty | Count | Accepted | Avg Score |")
        a("|------------|------:|---------:|----------:|")
        for diff, data in sorted(metrics["by_difficulty"].items()):
            a(f"| {diff} | {data['count']} | {data['accepted']} | {data['avg_score']} |")
        a("")

    a("## Per-Case Results")
    a("")
    a("| ID | Score | C | R | S | K | T | Accept |")
    a("|----|------:|---|---|---|---|---|--------|")
    for r in sorted(report.get("results", []), key=lambda x: x.get("score", 0), reverse=True):
        chk = r.get("checks", {})
        c   = "✓" if chk.get("compile",   {}).get("passed") else "✗"
        rv  = "✓" if chk.get("runtime",   {}).get("passed") else "✗"
        s   = "✓" if chk.get("semantic",  {}).get("passed") else "✗"
        k   = "✓" if chk.get("keyword",   {}).get("passed") else "✗"
        t   = "✓" if chk.get("truncation",{}).get("passed") else "✗"
        acc = "YES" if r.get("accepted") else "no"
        a(f"| `{r['id']}` | {r.get('score',0)} | {c} | {rv} | {s} | {k} | {t} | {acc} |")
    a("")

    if metrics.get("latency_ms", {}).get("avg"):
        lat = metrics["latency_ms"]
        a(f"*Latency: avg {lat['avg']}ms  min {lat['min']}ms  max {lat['max']}ms*")
        a("")

    a("---")
    a("")
    a("**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# ── score_run (called from run_baseline.py) ───────────────────────────────────

def score_run(results: list[dict], meta: dict, out_dir: Path) -> dict:
    metrics = compute_metrics(results)
    report  = {
        **metrics,
        "run_id":    meta.get("run_id", "?"),
        "model":     meta.get("model", "?"),
        "timestamp": now_iso(),
        "meta":      meta,
        "results":   results,
    }

    write_json(report, out_dir / "report.json")
    write_markdown(report, out_dir / "report.md")

    passed = [r for r in results if r.get("accepted")]
    failed = [r for r in results if not r.get("accepted")]
    write_jsonl(passed, out_dir / "passed_cases.jsonl")
    write_jsonl(failed, out_dir / "failed_cases.jsonl")

    print(f"[score] report -> {out_dir / 'report.md'}")
    return report


# ── compare_runs ─────────────────────────────────────────────────────────────

def compare_runs(run_ids: list[str]) -> None:
    reports: list[dict] = []
    for rid in run_ids:
        report_path = REPORTS_DIR / "runs" / rid / "report.json"
        if not report_path.exists():
            print(f"[compare] not found: {report_path}", file=sys.stderr)
            continue
        rep = json.loads(report_path.read_text(encoding="utf-8"))
        rep["_run_id"] = rid
        reports.append(rep)

    if not reports:
        print("[compare] no valid runs found", file=sys.stderr)
        return

    rate_keys = [
        ("compile_pass_rate",    "Compile"),
        ("runtime_pass_rate",    "Runtime"),
        ("semantic_pass_rate",   "Semantic"),
        ("keyword_pass_rate",    "Keyword"),
        ("truncation_pass_rate", "Not-Truncated"),
        ("accepted_rate",        "Accepted"),
    ]

    # Header
    col_w = 22
    header = f"{'Metric':<22}" + "".join(f"  {r['_run_id']:<18}" for r in reports)
    print(header)
    print("-" * len(header))

    for key, label in rate_keys:
        row = f"{label:<22}"
        for rep in reports:
            val = rep.get("rates", {}).get(key, 0.0)
            row += f"  {val:>6.0%}            "
        print(row)

    # Avg score
    row = f"{'Avg Score':<22}"
    for rep in reports:
        row += f"  {rep.get('average_score', 0):>6.1f}            "
    print(row)

    # Model
    row = f"{'Model':<22}"
    for rep in reports:
        model = rep.get("model", "?")[:18]
        row += f"  {model:<18}"
    print(row)


# ── CLI ──────────────────────────────────────────────────────────────────────

def _latest_run_id() -> str | None:
    runs_dir = REPORTS_DIR / "runs"
    if not runs_dir.exists():
        return None
    dirs = sorted(
        (d for d in runs_dir.iterdir() if d.is_dir() and (d / "results.jsonl").exists()),
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    return dirs[0].name if dirs else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Score a benchmark run")
    group  = parser.add_mutually_exclusive_group()
    group.add_argument("--run-id",      default=None, help="Run ID under reports/runs/")
    group.add_argument("--results-file", default=None, help="Path to a results.jsonl file")
    group.add_argument("--compare",     nargs="+",   help="Compare two or more run IDs")
    args = parser.parse_args()

    if args.compare:
        compare_runs(args.compare)
        return

    if args.results_file:
        results_path = Path(args.results_file)
        run_id       = results_path.parent.name
    else:
        run_id = args.run_id or _latest_run_id()
        if not run_id:
            print("[score] no run found in reports/runs/", file=sys.stderr)
            sys.exit(1)
        results_path = REPORTS_DIR / "runs" / run_id / "results.jsonl"

    if not results_path.exists():
        print(f"[score] results not found: {results_path}", file=sys.stderr)
        sys.exit(1)

    meta_path = results_path.parent / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    results = load_jsonl(results_path)
    out_dir = results_path.parent

    report = score_run(results=results, meta=meta, out_dir=out_dir)
    r      = report.get("rates", {})

    print(f"\nRun:          {run_id}")
    print(f"Model:        {meta.get('model', '?')}")
    print(f"Cases run:    {report.get('cases_run', 0)}")
    print(f"  compile:    {r.get('compile_pass_rate', 0):.0%}")
    print(f"  runtime:    {r.get('runtime_pass_rate', 0):.0%}")
    print(f"  semantic:   {r.get('semantic_pass_rate', 0):.0%}")
    print(f"  keyword:    {r.get('keyword_pass_rate', 0):.0%}")
    print(f"  not-trunc:  {r.get('truncation_pass_rate', 0):.0%}")
    print(f"  avg score:  {report.get('average_score', 0):.1f}")
    print(f"  accepted:   {report.get('accepted', 0)}/{report.get('cases_run', 0)}")


if __name__ == "__main__":
    main()
