"""Canonical regression policy — single source of truth for regression verdicts.

Pure (stdlib only) so every governance layer can import it without pulling in the
benchmark I/O stack:
  - `benchmark/detect_regression.py`     run-vs-run regression detection
  - `sft/promote_adapter.py`             adapter promotion guard
  - `model_eval/promote_model.py`        model promotion guard

Thresholds are data (`DEFAULT_REGRESSION_POLICY`); the verdict is derived from
them and never hard-coded. Verdicts: pass | improvement | regression |
manual_review (regression AND improvement signals both present).
"""
from __future__ import annotations

from typing import Any

DEFAULT_REGRESSION_POLICY: dict[str, Any] = {
    "accepted_drop_tolerance": 0,        # accepted count may drop by at most this
    "avg_score_drop_tolerance": 1.0,     # avg score may drop by at most this
    "rate_drop_tolerance": 0.0,          # compile/runtime pass-rate drop tolerated
    "per_task_drop_tolerance": 20,       # any single-task score drop beyond this flags
    "max_newly_broken": 0,               # accepted->failed tasks allowed before regression
    "improvement_avg_score_gain": 1.0,   # avg-score gain to qualify as improvement
    "verdicts": ["pass", "improvement", "regression", "manual_review", "no_reference"],
}


def classify_deltas(
    metrics: dict[str, Any],
    task_deltas: list[dict[str, Any]] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify a set of aggregate deltas (+ optional per-task deltas) into a verdict.

    metrics keys (all optional, default 0):
      accepted_delta, avg_score_delta, compile_delta, runtime_delta,
      newly_broken_count
    task_deltas: list of {"id", "delta", ...} for per-task drop detection.
    """
    pol = {**DEFAULT_REGRESSION_POLICY, **(policy or {})}
    task_deltas = task_deltas or []

    accepted_delta = int(metrics.get("accepted_delta", 0) or 0)
    avg_delta = float(metrics.get("avg_score_delta", 0.0) or 0.0)
    compile_delta = float(metrics.get("compile_delta", 0.0) or 0.0)
    runtime_delta = float(metrics.get("runtime_delta", 0.0) or 0.0)
    newly_broken_count = int(metrics.get("newly_broken_count", 0) or 0)

    big_drops = [
        t for t in task_deltas
        if float(t.get("delta", 0.0) or 0.0) < -float(pol["per_task_drop_tolerance"])
    ]

    # ── Regression signals ────────────────────────────────────────────────────
    reg_reasons: list[str] = []
    if accepted_delta < -int(pol["accepted_drop_tolerance"]):
        reg_reasons.append(f"accepted dropped by {abs(accepted_delta)}")
    if avg_delta < -float(pol["avg_score_drop_tolerance"]):
        reg_reasons.append(f"avg score dropped by {abs(avg_delta):.1f}")
    if compile_delta < -float(pol["rate_drop_tolerance"]):
        reg_reasons.append(f"compile pass-rate dropped by {abs(compile_delta):.3f}")
    if runtime_delta < -float(pol["rate_drop_tolerance"]):
        reg_reasons.append(f"runtime pass-rate dropped by {abs(runtime_delta):.3f}")
    if newly_broken_count > int(pol["max_newly_broken"]):
        reg_reasons.append(f"{newly_broken_count} task(s) newly broken")
    if big_drops:
        ids = ", ".join(str(t.get("id")) for t in big_drops)
        reg_reasons.append(
            f"{len(big_drops)} task(s) dropped > {pol['per_task_drop_tolerance']} pts ({ids})"
        )
    regressed = bool(reg_reasons)

    # ── Improvement signals ───────────────────────────────────────────────────
    imp_reasons: list[str] = []
    if newly_broken_count == 0:
        if accepted_delta > 0:
            imp_reasons.append(f"accepted improved by {accepted_delta}")
        if avg_delta >= float(pol["improvement_avg_score_gain"]):
            imp_reasons.append(f"avg score improved by {avg_delta:.1f}")
    improved = bool(imp_reasons)

    # ── Verdict (policy-derived) ──────────────────────────────────────────────
    if regressed and improved:
        verdict = "manual_review"
    elif regressed:
        verdict = "regression"
    elif improved:
        verdict = "improvement"
    else:
        verdict = "pass"

    largest_drop = min(task_deltas, key=lambda t: float(t.get("delta", 0.0) or 0.0), default=None)

    return {
        "verdict": verdict,
        "regressed": regressed,
        "improved": improved,
        "regression_reasons": reg_reasons,
        "improvement_reasons": imp_reasons,
        "largest_drop": largest_drop,
        "big_task_drops": big_drops,
    }


def regression_verdict(
    metrics: dict[str, Any],
    task_deltas: list[dict[str, Any]] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Public alias for classify_deltas — the entry point governance gates call."""
    return classify_deltas(metrics, task_deltas, policy)
