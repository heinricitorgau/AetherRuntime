#!/usr/bin/env python3
"""Automatic regression detection across benchmark runs.

This is governed regression infrastructure (roadmap #8). It does NOT run models,
change benchmark scoring, or alter evaluation rules. It reads existing run
reports, reuses `compare_runs.compare()` for the structural diff, and applies a
tunable regression *policy* (thresholds as data) to produce a governed verdict
that promotion gates and CI can consume.

Verdicts (derived from policy, never hard-coded per case):
  - pass           no regression and no material improvement
  - improvement    material improvement, no regression
  - regression     one or more regression signals tripped
  - manual_review  regression AND improvement signals both present (conflict)
  - no_reference   no comparable prior run found (nothing to compare; not a fail)

Modes:
  --base <id> --new <id>   compare two explicit runs
  --new <id>               auto-resolve the previous run of the same model
  --self-test              run verdict logic on synthetic data (model-free; for smoke test)

Exit codes:
  0  pass | improvement | manual_review | no_reference | self-test
  1  regression (so automation can gate)

Reports:
  reports/regression/regression_report.json
  reports/regression/regression_report.md
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_HERE))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from _bench_common import REPORTS_DIR, load_jsonl, now_iso, write_json  # noqa: E402
from compare_runs import compare  # noqa: E402  (reused structural diff)
from local_ai.shared.regression_policy import (  # noqa: E402  (canonical policy)
    DEFAULT_REGRESSION_POLICY,
    classify_deltas,
)

_REGRESSION_DIR = REPORTS_DIR / "regression"
_OUT_JSON = _REGRESSION_DIR / "regression_report.json"
_OUT_MD = _REGRESSION_DIR / "regression_report.md"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _runs_dir() -> Path:
    return REPORTS_DIR / "runs"


def _load_report(run_id: str) -> dict[str, Any]:
    path = _runs_dir() / run_id / "report.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _model_of(report: dict[str, Any]) -> str | None:
    return (report.get("meta") or {}).get("model") or report.get("model")


def _resolve_previous_run(new_id: str) -> str | None:
    """Auto-pick the most recent prior run of the same model as the reference."""
    runs_dir = _runs_dir()
    if not runs_dir.exists():
        return None
    new_report = _load_report(new_id)
    new_model = _model_of(new_report)
    new_ts = new_report.get("timestamp") or ""

    candidates: list[tuple[str, str]] = []
    for d in runs_dir.iterdir():
        if not d.is_dir() or d.name == new_id:
            continue
        rep = _load_report(d.name)
        if not rep:
            continue
        if new_model and _model_of(rep) != new_model:
            continue
        ts = rep.get("timestamp") or ""
        if new_ts and ts and ts >= new_ts:
            continue
        candidates.append((ts, d.name))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


def _per_task_deltas(base_results: list[dict], new_results: list[dict]) -> list[dict]:
    base_by_id = {r.get("id"): r for r in base_results}
    new_by_id = {r.get("id"): r for r in new_results}
    rows: list[dict] = []
    for task_id in sorted(set(base_by_id) & set(new_by_id)):
        b = base_by_id[task_id]
        n = new_by_id[task_id]
        base_score = float(b.get("score", 0) or 0)
        new_score = float(n.get("score", 0) or 0)
        rows.append(
            {
                "id": task_id,
                "base_score": base_score,
                "new_score": new_score,
                "delta": round(new_score - base_score, 3),
            }
        )
    return rows


def _classify(
    comp: dict[str, Any],
    task_deltas: list[dict],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Adapt a compare_runs diff into the canonical regression policy + report shape."""
    newly_broken = comp.get("newly_broken", [])
    metrics = {
        "accepted_delta": int(comp["accepted"]["delta"]),
        "avg_score_delta": float(comp["avg_score"]["delta"]),
        "compile_delta": round(
            float(comp["compile_pass_rate"]["new"]) - float(comp["compile_pass_rate"]["base"]), 3
        ),
        "runtime_delta": round(
            float(comp["runtime_pass_rate"]["new"]) - float(comp["runtime_pass_rate"]["base"]), 3
        ),
        "newly_broken_count": len(newly_broken),
    }
    core = classify_deltas(metrics, task_deltas, policy)

    return {
        "verdict": core["verdict"],
        "regressed": core["regressed"],
        "improved": core["improved"],
        "regression_reasons": core["regression_reasons"],
        "improvement_reasons": core["improvement_reasons"],
        "metrics": {
            "accepted_delta": metrics["accepted_delta"],
            "avg_score_delta": round(metrics["avg_score_delta"], 3),
            "compile_delta": metrics["compile_delta"],
            "runtime_delta": metrics["runtime_delta"],
            "newly_broken_count": metrics["newly_broken_count"],
            "newly_fixed_count": len(comp.get("newly_fixed", [])),
            "tasks_compared": len(task_deltas),
        },
        "newly_broken": newly_broken,
        "newly_fixed": comp.get("newly_fixed", []),
        "largest_drop": core["largest_drop"],
        "big_task_drops": core["big_task_drops"],
    }


def detect(
    base_id: str,
    new_id: str,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pol = dict(DEFAULT_REGRESSION_POLICY)
    if policy:
        pol.update(policy)

    comp = compare(base_id, new_id)  # reused structural diff (loads results)
    base_results = load_jsonl(_runs_dir() / base_id / "results.jsonl")
    new_results = load_jsonl(_runs_dir() / new_id / "results.jsonl")
    task_deltas = _per_task_deltas(base_results, new_results)

    analysis = _classify(comp, task_deltas, pol)

    return {
        "timestamp": now_iso(),
        "base_run_id": base_id,
        "new_run_id": new_id,
        "policy": pol,
        "verdict": analysis["verdict"],
        "regressed": analysis["regressed"],
        "improved": analysis["improved"],
        "regression_reasons": analysis["regression_reasons"],
        "improvement_reasons": analysis["improvement_reasons"],
        "metrics": analysis["metrics"],
        "newly_broken": analysis["newly_broken"],
        "newly_fixed": analysis["newly_fixed"],
        "largest_drop": analysis["largest_drop"],
        "big_task_drops": analysis["big_task_drops"],
        "task_deltas": task_deltas,
    }


# ── Reporting ─────────────────────────────────────────────────────────────────

def _markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append
    a("# Benchmark Regression Report")
    a("")
    a(f"Generated: `{report['timestamp']}`  ")
    a(f"Base run: `{report['base_run_id']}`  ")
    a(f"New run: `{report['new_run_id']}`  ")
    a(f"Verdict: **{report['verdict']}**")
    a("")
    a("## Policy")
    a("")
    pol = report["policy"]
    a("| Threshold | Value |")
    a("|-----------|------:|")
    for key in (
        "accepted_drop_tolerance",
        "avg_score_drop_tolerance",
        "rate_drop_tolerance",
        "per_task_drop_tolerance",
        "max_newly_broken",
        "improvement_avg_score_gain",
    ):
        a(f"| {key} | {pol.get(key)} |")
    a("")
    a("## Metrics")
    a("")
    m = report["metrics"]
    a("| Metric | Delta |")
    a("|--------|------:|")
    for key in ("accepted_delta", "avg_score_delta", "compile_delta", "runtime_delta"):
        a(f"| {key} | {m.get(key)} |")
    a(f"| newly_broken | {m.get('newly_broken_count')} |")
    a(f"| newly_fixed | {m.get('newly_fixed_count')} |")
    a(f"| tasks_compared | {m.get('tasks_compared')} |")
    a("")
    a("## Regression Reasons")
    a("")
    if report["regression_reasons"]:
        for r in report["regression_reasons"]:
            a(f"- {r}")
    else:
        a("None.")
    a("")
    a("## Improvement Reasons")
    a("")
    if report["improvement_reasons"]:
        for r in report["improvement_reasons"]:
            a(f"- {r}")
    else:
        a("None.")
    a("")
    if report["newly_broken"]:
        a("## Newly Broken")
        a("")
        a("| Task | Base | New |")
        a("|------|-----:|----:|")
        for c in report["newly_broken"]:
            a(f"| `{c['id']}` | {c.get('base_score')} | {c.get('new_score')} |")
        a("")
    largest = report.get("largest_drop")
    if largest:
        a("## Largest Single-Task Drop")
        a("")
        a(f"- Task: `{largest['id']}`")
        a(f"- Base: {largest['base_score']} → New: {largest['new_score']} (delta {largest['delta']})")
        a("")
    a("## Guardrails")
    a("")
    a("- Verdict derived from the regression policy; nothing hard-coded.")
    a("- Read-only over existing run reports; does not run models or change scoring.")
    a("- `regression` exits non-zero so promotion gates and CI can block automatically.")
    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any]) -> None:
    _REGRESSION_DIR.mkdir(parents=True, exist_ok=True)
    write_json(report, _OUT_JSON)
    _OUT_MD.write_text(_markdown(report), encoding="utf-8")


def _register(report: dict[str, Any]) -> None:
    """Best-effort observability record; never fails the detector."""
    try:
        from local_ai.experiments.register_run import register_run  # noqa: PLC0415
        m = report["metrics"]
        register_run(
            {
                "run_id": f"regression_{report['new_run_id']}",
                "timestamp": report["timestamp"],
                "run_type": "regression_detection",
                "accepted": None,
                "avg_score": None,
            }
        )
        _ = m  # metrics are already persisted in the report itself
    except Exception:  # noqa: BLE001
        pass


# ── Self-test (model-free; used by smoke test) ────────────────────────────────

def _self_test() -> bool:
    """Validate verdict logic on synthetic comparisons without touching real runs."""
    pol = dict(DEFAULT_REGRESSION_POLICY)

    def synth(accepted_delta, avg_delta, compile_d, runtime_d, broken, deltas):
        comp = {
            "accepted": {"base": 10, "new": 10 + accepted_delta, "delta": accepted_delta},
            "avg_score": {"base": 80.0, "new": 80.0 + avg_delta, "delta": avg_delta},
            "compile_pass_rate": {"base": 1.0, "new": 1.0 + compile_d},
            "runtime_pass_rate": {"base": 1.0, "new": 1.0 + runtime_d},
            "newly_broken": [{"id": f"b{i}", "base_score": 70, "new_score": 0} for i in range(broken)],
            "newly_fixed": [],
        }
        return _classify(comp, deltas, pol)["verdict"]

    cases = [
        # (accepted_d, avg_d, compile_d, runtime_d, broken, task_deltas, expected)
        (0, 0.0, 0.0, 0.0, 0, [{"id": "t", "base_score": 80, "new_score": 80, "delta": 0.0}], "pass"),
        (2, 5.0, 0.0, 0.0, 0, [{"id": "t", "base_score": 80, "new_score": 85, "delta": 5.0}], "improvement"),
        (-1, -5.0, 0.0, 0.0, 1, [{"id": "t", "base_score": 80, "new_score": 0, "delta": -80.0}], "regression"),
        # conflict: aggregate avg up + accepted up, but one task collapses badly and is newly broken=0
        (1, 2.0, 0.0, 0.0, 0, [{"id": "t", "base_score": 90, "new_score": 30, "delta": -60.0}], "manual_review"),
    ]
    ok = True
    for accepted_d, avg_d, compile_d, runtime_d, broken, deltas, expected in cases:
        got = synth(accepted_d, avg_d, compile_d, runtime_d, broken, deltas)
        status = "ok" if got == expected else "FAIL"
        if got != expected:
            ok = False
        print(f"[detect-regression] self-test {status}: expected={expected} got={got}")
    return ok


# ── CLI ───────────────────────────────────────────────────────────────────────

def _load_policy(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automatic benchmark regression detection")
    parser.add_argument("--base", help="Base/reference run ID (default: auto-resolve previous run)")
    parser.add_argument("--new", help="New run ID to check for regression")
    parser.add_argument("--policy", help="Optional JSON file overriding regression thresholds")
    parser.add_argument("--self-test", action="store_true", help="Run verdict logic on synthetic data")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.self_test:
        ok = _self_test()
        print(f"[detect-regression] self-test {'PASS' if ok else 'FAIL'}")
        sys.exit(0 if ok else 1)

    if not args.new:
        print("[detect-regression] ERROR: --new is required (or use --self-test)", file=sys.stderr)
        sys.exit(2)

    policy = _load_policy(args.policy)
    base_id = args.base or _resolve_previous_run(args.new)

    if not base_id:
        report = {
            "timestamp": now_iso(),
            "base_run_id": None,
            "new_run_id": args.new,
            "policy": {**DEFAULT_REGRESSION_POLICY, **(policy or {})},
            "verdict": "no_reference",
            "regressed": False,
            "improved": False,
            "regression_reasons": [],
            "improvement_reasons": [],
            "metrics": {},
            "newly_broken": [],
            "newly_fixed": [],
            "largest_drop": None,
            "big_task_drops": [],
            "task_deltas": [],
        }
        write_reports(report)
        print(f"[detect-regression] verdict=no_reference (no prior run found for {args.new})")
        print(f"[detect-regression] report >> {_OUT_MD}")
        sys.exit(0)

    report = detect(base_id, args.new, policy)
    write_reports(report)
    _register(report)

    print(f"[detect-regression] {base_id} -> {args.new}")
    print(f"[detect-regression] verdict={report['verdict']}")
    if report["regression_reasons"]:
        for r in report["regression_reasons"]:
            print(f"  regression: {r}")
    if report["improvement_reasons"]:
        for r in report["improvement_reasons"]:
            print(f"  improvement: {r}")
    print(f"[detect-regression] report >> {_OUT_MD}")

    sys.exit(1 if report["verdict"] == "regression" else 0)


if __name__ == "__main__":
    main()
