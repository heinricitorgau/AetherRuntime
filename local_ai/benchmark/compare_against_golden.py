#!/usr/bin/env python3
"""Compare a benchmark run against the locked golden baseline.

Reads:  golden/golden_baseline.json
        reports/runs/<run_id>/report.json
Writes: reports/runs/<run_id>/comparison_report.json
        reports/runs/<run_id>/comparison_report.md

Regression if:  accepted_count drops  OR  avg_score drops > 1.0pt  OR  timeout_rate rises
Improvement if: accepted_count rises  OR  avg_score rises > 1.0pt

Usage:
  python local_ai/benchmark/compare_against_golden.py --run-id strict_20260515_043031
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_HERE))

from _bench_common import GOLDEN_DIR, REPORTS_DIR, now_iso, write_json
from local_ai.experiments.register_run import register_run

GOLDEN_FILE = GOLDEN_DIR / "golden_baseline.json"


# ── Data helpers ──────────────────────────────────────────────────────────────

def _load_golden() -> dict:
    if not GOLDEN_FILE.exists():
        print(f"[golden] golden_baseline.json not found at {GOLDEN_FILE}", file=sys.stderr)
        print("[golden] Run: python local_ai/benchmark/lock_golden_baseline.py --run-id <run_id>",
              file=sys.stderr)
        sys.exit(1)
    return json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))


def _load_run_metrics(run_id: str) -> dict:
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
    return {
        "run_id":             run_id,
        "model":              meta.get("model", rep.get("model", "?")),
        "task_count":         rep.get("cases_run", n),
        "accepted_count":     rep.get("accepted", 0),
        "avg_score":          rep.get("average_score", 0.0),
        "compile_pass_rate":  rates.get("compile_pass_rate", 0.0),
        "runtime_pass_rate":  rates.get("runtime_pass_rate", 0.0),
        "semantic_pass_rate": rates.get("semantic_pass_rate", 0.0),
        "keyword_pass_rate":  rates.get("keyword_pass_rate", 0.0),
        "timeout_rate":       round(timeout_count / n, 3) if n > 0 else 0.0,
    }


# ── Comparison logic ──────────────────────────────────────────────────────────

def compare(run_id: str) -> dict:
    golden  = _load_golden()
    current = _load_run_metrics(run_id)

    regression = (
        current["accepted_count"] < golden["accepted_count"]
        or current["avg_score"]   < golden["avg_score"] - 1.0
        or current["timeout_rate"] > golden["timeout_rate"]
    )
    improvement = (
        current["accepted_count"] > golden["accepted_count"]
        or current["avg_score"]   > golden["avg_score"] + 1.0
    )

    verdict = (
        "improvement"    if improvement
        else "regression" if regression
        else "matches_golden"
    )

    def _metric(key: str) -> dict:
        g = golden.get(key, 0)
        c = current[key]
        return {"golden": g, "current": c, "delta": round(c - g, 3)}

    return {
        "timestamp":      now_iso(),
        "golden_run_id":  golden["run_id"],
        "current_run_id": run_id,
        "verdict":        verdict,
        "regression":     regression,
        "improvement":    improvement,
        "metrics": {
            "accepted_count":     _metric("accepted_count"),
            "avg_score":          _metric("avg_score"),
            "compile_pass_rate":  _metric("compile_pass_rate"),
            "runtime_pass_rate":  _metric("runtime_pass_rate"),
            "semantic_pass_rate": _metric("semantic_pass_rate"),
            "keyword_pass_rate":  _metric("keyword_pass_rate"),
            "timeout_rate":       _metric("timeout_rate"),
        },
    }


# ── Markdown report ───────────────────────────────────────────────────────────

def _sign(v: float | int) -> str:
    if isinstance(v, float):
        return f"+{v:.1f}" if v > 0 else f"{v:.1f}"
    return f"+{v}" if v > 0 else str(v)


def write_markdown(comp: dict, path: Path) -> None:
    lines: list[str] = []
    a = lines.append

    verdict_label = {
        "matches_golden": "MATCHES GOLDEN",
        "regression":     "REGRESSION DETECTED",
        "improvement":    "IMPROVEMENT DETECTED",
    }.get(comp["verdict"], comp["verdict"].upper())

    a("# Golden Baseline Comparison")
    a("")
    a(f"**Golden run**: `{comp['golden_run_id']}`  ")
    a(f"**Current run**: `{comp['current_run_id']}`  ")
    a(f"**Generated**: {comp['timestamp']}")
    a("")
    a(f"## Verdict: {verdict_label}")
    a("")
    a("| Metric | Golden | Current | Delta |")
    a("|--------|-------:|--------:|------:|")

    m = comp["metrics"]

    def _row(label: str, key: str, fmt: str = ".1f") -> None:
        g = m[key]["golden"]
        c = m[key]["current"]
        d = m[key]["delta"]
        if fmt == "%":
            a(f"| {label} | {g:.0%} | {c:.0%} | {_sign(d * 100)}% |")
        elif fmt == "d":
            a(f"| {label} | {g} | {c} | {_sign(d)} |")
        else:
            a(f"| {label} | {g:.1f} | {c:.1f} | {_sign(d)} |")

    _row("Accepted count",    "accepted_count",     "d")
    _row("Avg score",         "avg_score",          ".1f")
    _row("Compile pass rate", "compile_pass_rate",  "%")
    _row("Runtime pass rate", "runtime_pass_rate",  "%")
    _row("Semantic pass rate","semantic_pass_rate", "%")
    _row("Keyword pass rate", "keyword_pass_rate",  "%")
    _row("Timeout rate",      "timeout_rate",       "%")
    a("")

    if comp["regression"]:
        a("---")
        a("")
        a("> **Regression**: accepted count dropped, avg score dropped > 1.0pt, "
          "or timeout rate increased vs golden.")
        a("")
    elif comp["improvement"]:
        a("---")
        a("")
        a("> **Improvement**: accepted count rose or avg score rose > 1.0pt vs golden.")
        a("")

    a("---")
    a("")
    a("*Regression if: accepted drops, avg_score drops > 1.0pt, or timeout_rate rises.*  ")
    a("*Improvement if: accepted rises or avg_score rises > 1.0pt.*")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _register_comparison(comp: dict, run_dir: Path) -> None:
    try:
        metrics = comp.get("metrics", {})
        current = {key: value.get("current") for key, value in metrics.items()}
        registered = register_run(
            {
                "run_id": f"golden_compare_{comp.get('current_run_id')}",
                "timestamp": comp.get("timestamp"),
                "run_type": "golden_comparison",
                "benchmark_profile": None,
                "model_profile": None,
                "accepted": current.get("accepted_count"),
                "avg_score": current.get("avg_score"),
                "compile_rate": current.get("compile_pass_rate"),
                "runtime_rate": current.get("runtime_pass_rate"),
                "semantic_rate": current.get("semantic_pass_rate"),
                "keyword_rate": current.get("keyword_pass_rate"),
                "timeout_rate": current.get("timeout_rate"),
                "golden_run_id": comp.get("golden_run_id"),
                "current_run_id": comp.get("current_run_id"),
                "verdict": comp.get("verdict"),
                "regression": comp.get("regression"),
                "improvement": comp.get("improvement"),
                "metrics": metrics,
                "linked_reports": {
                    "comparison_report_json": str(run_dir / "comparison_report.json"),
                    "comparison_report_md": str(run_dir / "comparison_report.md"),
                    "current_report_json": str(run_dir / "report.json"),
                    "golden_baseline_json": str(GOLDEN_FILE),
                },
            }
        )
        print(f"[experiments] registered run_id={registered['run_id']}")
    except Exception as exc:
        print(f"[experiments] WARNING: could not register golden comparison: {exc}", file=sys.stderr)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare a benchmark run against the golden baseline"
    )
    parser.add_argument("--run-id", required=True, help="Run ID to compare")
    args = parser.parse_args()

    comp    = compare(args.run_id)
    run_dir = REPORTS_DIR / "runs" / args.run_id

    md_path   = run_dir / "comparison_report.md"
    json_path = run_dir / "comparison_report.json"

    write_markdown(comp, md_path)
    write_json(comp, json_path)
    _register_comparison(comp, run_dir)

    m = comp["metrics"]
    print(f"\nGolden comparison: {args.run_id}")
    print(f"  verdict:   {comp['verdict']}")
    print(f"  accepted:  {m['accepted_count']['golden']} → {m['accepted_count']['current']}  "
          f"({_sign(m['accepted_count']['delta'])})")
    print(f"  avg score: {m['avg_score']['golden']:.1f} → {m['avg_score']['current']:.1f}  "
          f"({_sign(m['avg_score']['delta'])})")
    print(f"  compile:   {m['compile_pass_rate']['golden']:.0%} → "
          f"{m['compile_pass_rate']['current']:.0%}")
    print(f"  runtime:   {m['runtime_pass_rate']['golden']:.0%} → "
          f"{m['runtime_pass_rate']['current']:.0%}")
    print(f"  timeout:   {m['timeout_rate']['golden']:.0%} → "
          f"{m['timeout_rate']['current']:.0%}")
    print(f"\nReport: {md_path}")

    if comp["regression"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
