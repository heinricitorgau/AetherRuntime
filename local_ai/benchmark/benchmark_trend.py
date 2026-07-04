#!/usr/bin/env python3
"""Continuous benchmark trend + automatic regression over run history (roadmap #9).

Read-only aggregator over existing `reports/runs/*/report.json`. It groups runs
by model, builds a score/accepted time series, and — for each model with at least
two runs that have per-task results — automatically runs the canonical regression
detector (`detect_regression.detect`) on the two most recent runs. It does NOT
run models, call the proxy, or change scoring.

Outputs:
  reports/trend/benchmark_trend.json
  reports/trend/benchmark_trend.md

Usage:
  python local_ai/benchmark/benchmark_trend.py
  python local_ai/benchmark/benchmark_trend.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_HERE))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from _bench_common import REPORTS_DIR, now_iso, write_json  # noqa: E402

_RUNS_DIR = REPORTS_DIR / "runs"
_TREND_DIR = REPORTS_DIR / "trend"
_OUT_JSON = _TREND_DIR / "benchmark_trend.json"
_OUT_MD = _TREND_DIR / "benchmark_trend.md"


def _load_runs() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    if not _RUNS_DIR.exists():
        return runs
    for d in _RUNS_DIR.iterdir():
        report = d / "report.json"
        if not d.is_dir() or not report.exists():
            continue
        try:
            rep = json.loads(report.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        rates = rep.get("rates") or {}
        runs.append(
            {
                "run_id": d.name,  # dir name is the canonical id detect_regression uses
                "model": (rep.get("meta") or {}).get("model") or rep.get("model") or "unknown",
                "timestamp": rep.get("timestamp") or "",
                "accepted": rep.get("accepted", 0),
                "avg_score": round(float(rep.get("average_score", 0.0) or 0.0), 1),
                "compile_rate": round(float(rates.get("compile_pass_rate", 0.0) or 0.0), 3),
                "runtime_rate": round(float(rates.get("runtime_pass_rate", 0.0) or 0.0), 3),
                "has_results": (d / "results.jsonl").exists(),
            }
        )
    return runs


def _trend_direction(series: list[dict[str, Any]]) -> str:
    """Compare the latest run's avg score to the first in the series."""
    if len(series) < 2:
        return "insufficient_history"
    delta = series[-1]["avg_score"] - series[0]["avg_score"]
    if delta > 1.0:
        return "improving"
    if delta < -1.0:
        return "declining"
    return "flat"


def _latest_regression(series: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Auto-run the regression detector on the two most recent runs with results."""
    with_results = [r for r in series if r["has_results"]]
    if len(with_results) < 2:
        return None
    prev, latest = with_results[-2], with_results[-1]
    try:
        from detect_regression import detect  # noqa: PLC0415  (lazy; heavy import chain)
        result = detect(prev["run_id"], latest["run_id"])
        return {
            "base_run_id": result["base_run_id"],
            "new_run_id": result["new_run_id"],
            "verdict": result["verdict"],
            "regression_reasons": result["regression_reasons"],
            "improvement_reasons": result["improvement_reasons"],
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:200]}


def build_trend() -> dict[str, Any]:
    runs = _load_runs()
    by_model: dict[str, list[dict[str, Any]]] = {}
    for r in runs:
        by_model.setdefault(r["model"], []).append(r)

    models: list[dict[str, Any]] = []
    for model in sorted(by_model):
        series = sorted(by_model[model], key=lambda r: r["timestamp"])
        models.append(
            {
                "model": model,
                "run_count": len(series),
                "first": {"run_id": series[0]["run_id"], "avg_score": series[0]["avg_score"]},
                "latest": {"run_id": series[-1]["run_id"], "avg_score": series[-1]["avg_score"]},
                "trend": _trend_direction(series),
                "latest_regression": _latest_regression(series),
                "runs": series,
            }
        )

    return {
        "timestamp": now_iso(),
        "total_runs": len(runs),
        "models_tracked": len(models),
        "models": models,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append
    a("# Benchmark Trend Report")
    a("")
    a(f"Generated: `{report['timestamp']}`  ")
    a(f"Total runs: {report['total_runs']}  ")
    a(f"Models tracked: {report['models_tracked']}")
    a("")
    for m in report["models"]:
        a(f"## `{m['model']}`")
        a("")
        a(f"- Runs: {m['run_count']}")
        a(f"- Trend: **{m['trend']}** "
          f"(first {m['first']['avg_score']} → latest {m['latest']['avg_score']})")
        reg = m.get("latest_regression")
        if reg and "verdict" in reg:
            a(f"- Latest-pair regression verdict: **{reg['verdict']}** "
              f"(`{reg['base_run_id']}` → `{reg['new_run_id']}`)")
            for r in reg.get("regression_reasons", []):
                a(f"  - regression: {r}")
        elif reg and "error" in reg:
            a(f"- Latest-pair regression: error ({reg['error']})")
        else:
            a("- Latest-pair regression: n/a (need 2 runs with per-task results)")
        a("")
        a("| Run | Timestamp | Accepted | Avg | Compile | Runtime |")
        a("|-----|-----------|---------:|----:|--------:|--------:|")
        for r in m["runs"][-8:]:
            a(f"| `{r['run_id']}` | {r['timestamp']} | {r['accepted']} | {r['avg_score']} "
              f"| {r['compile_rate']} | {r['runtime_rate']} |")
        a("")
    a("## Guardrails")
    a("")
    a("- Read-only over existing run reports; does not run models or change scoring.")
    a("- Regression verdicts come from the canonical `regression_policy`.")
    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any]) -> None:
    _TREND_DIR.mkdir(parents=True, exist_ok=True)
    write_json(report, _OUT_JSON)
    _OUT_MD.write_text(_markdown(report), encoding="utf-8")


def _self_test() -> bool:
    ok = True
    cases = [
        ([{"avg_score": 80.0}], "insufficient_history"),
        ([{"avg_score": 80.0}, {"avg_score": 85.0}], "improving"),
        ([{"avg_score": 85.0}, {"avg_score": 80.0}], "declining"),
        ([{"avg_score": 80.0}, {"avg_score": 80.5}], "flat"),
    ]
    for series, expected in cases:
        got = _trend_direction(series)
        status = "ok" if got == expected else "FAIL"
        if got != expected:
            ok = False
        print(f"[benchmark-trend] self-test {status}: expected={expected} got={got}")
    return ok


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark trend + auto-regression over run history")
    parser.add_argument("--self-test", action="store_true", help="Model-free trend-logic self-test")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.self_test:
        ok = _self_test()
        print(f"[benchmark-trend] self-test {'PASS' if ok else 'FAIL'}")
        sys.exit(0 if ok else 1)

    report = build_trend()
    write_reports(report)
    print(f"[benchmark-trend] runs={report['total_runs']} models={report['models_tracked']}")
    for m in report["models"]:
        reg = m.get("latest_regression") or {}
        verdict = reg.get("verdict", "n/a")
        print(f"  {m['model']}: trend={m['trend']} latest_regression={verdict}")
    print(f"[benchmark-trend] report >> {_OUT_MD}")


if __name__ == "__main__":
    main()
