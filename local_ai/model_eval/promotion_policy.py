#!/usr/bin/env python3
"""Model promotion policy for model_comparison.json reports.

This module is the governance layer for model replacement decisions. It mirrors
the adapter promotion policy (`local_ai/sft/promotion_policy.py`) and the dataset
promotion gate (`local_ai/dataset_scaling/promote_generated_dataset.py`).

It decides whether a larger / alternative model should be promoted over the
baseline by weighing BOTH the strict benchmark and the generated benchmark — it
must never recommend "stay on 3B" purely because of a strict-benchmark
regression. A strict regression combined with a material generated-benchmark
improvement is a *conflict* and resolves to `manual_review`, not an automatic
rejection.

The recommendation is derived entirely from the policy; nothing is hard-coded.

Decision states:
  - reject                  clear regression / negative weighted gain
  - candidate               positive but mixed/minor gain; not yet default
  - safe_no_change          negligible change, all guardrails held
  - promote_default         material weighted gain with no regression anywhere
  - manual_review           conflicting strict vs generated signals
  - invalid_model_override  override not honoured; evaluation untrustworthy

The ladder in `promotion_levels` is: reject < candidate < safe < default.
`manual_review` and `invalid_model_override` are off-ladder governance states.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent

# ── Policy ────────────────────────────────────────────────────────────────────
# Weights and thresholds are data, not code. Adjust here (or pass a policy dict)
# rather than editing the decision logic.

DEFAULT_POLICY: dict[str, Any] = {
    "strict_weight": 0.6,
    "generated_weight": 0.4,
    "require_override_valid": True,
    "promotion_levels": ["reject", "candidate", "safe", "default"],
    # Thresholds (tunable):
    "material_score_gain": 3.0,        # weighted avg-score points to count as material
    "negligible_score_delta": 0.5,     # |weighted delta| <= this is "no material change"
    "score_regression_tolerance": 0.5, # per-benchmark avg-score drop tolerated before "regressed"
    "rate_regression_tolerance": 0.0,  # per-benchmark rate drop tolerated before "regressed"
}

# Off-ladder governance states.
DECISION_INVALID_OVERRIDE = "invalid_model_override"
DECISION_MANUAL_REVIEW = "manual_review"

# Maps each decision to its place on the promotion ladder (or off-ladder marker).
_DECISION_TO_LEVEL = {
    "reject": "reject",
    "candidate": "candidate",
    "safe_no_change": "safe",
    "promote_default": "default",
    DECISION_MANUAL_REVIEW: "off_ladder",
    DECISION_INVALID_OVERRIDE: "off_ladder",
}

# Headline priority when several candidate models are evaluated: the most
# governance-significant outcome surfaces as the report recommendation.
_HEADLINE_PRIORITY = {
    DECISION_INVALID_OVERRIDE: 5,
    "promote_default": 4,
    DECISION_MANUAL_REVIEW: 3,
    "candidate": 2,
    "safe_no_change": 1,
    "reject": 0,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# ── Benchmark classification ──────────────────────────────────────────────────

def _benchmarks_from(comparison: dict[str, Any]) -> list[str]:
    benchmarks = comparison.get("benchmarks")
    if benchmarks:
        return list(benchmarks)
    seen: list[str] = []
    for row in comparison.get("results", []):
        b = row.get("benchmark")
        if b and b not in seen:
            seen.append(b)
    return seen


def _classify_benchmarks(benchmarks: list[str]) -> tuple[str | None, str | None]:
    """Return (strict_benchmark_id, generated_benchmark_id).

    Classified by name substring; falls back to positional order so the policy
    still functions on renamed benchmark profiles.
    """
    strict = next((b for b in benchmarks if "strict" in b.lower()), None)
    generated = next((b for b in benchmarks if "generated" in b.lower()), None)
    remaining = [b for b in benchmarks if b not in {strict, generated}]
    if strict is None and remaining:
        strict = remaining.pop(0)
    if generated is None and remaining:
        generated = remaining.pop(0)
    return strict, generated


# ── Row lookup and deltas ─────────────────────────────────────────────────────

def _row(results: list[dict[str, Any]], alias: str, benchmark: str | None) -> dict[str, Any] | None:
    if not benchmark:
        return None
    for r in results:
        if r.get("model_alias") == alias and r.get("benchmark") == benchmark:
            return r
    return None


def _is_completed(row: dict[str, Any] | None) -> bool:
    return bool(row) and row.get("status") == "completed"


def _override_ok(rows: list[dict[str, Any] | None]) -> bool:
    """True only if every present row honoured the model override."""
    present = [r for r in rows if r]
    if not present:
        return False
    return all(bool(r.get("model_override_valid", False)) for r in present)


def _bench_delta(cand: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    def f(row: dict[str, Any], key: str) -> float:
        return float(row.get(key) or 0.0)

    return {
        "benchmark": cand.get("benchmark"),
        "candidate_avg_score": f(cand, "avg_score"),
        "baseline_avg_score": f(base, "avg_score"),
        "accepted_delta": int(cand.get("accepted") or 0) - int(base.get("accepted") or 0),
        "avg_score_delta": round(f(cand, "avg_score") - f(base, "avg_score"), 3),
        "compile_delta": round(f(cand, "compile_rate") - f(base, "compile_rate"), 3),
        "runtime_delta": round(f(cand, "runtime_rate") - f(base, "runtime_rate"), 3),
        "semantic_delta": round(f(cand, "semantic_rate") - f(base, "semantic_rate"), 3),
    }


def _regressed(delta: dict[str, Any], policy: dict[str, Any]) -> bool:
    score_tol = float(policy["score_regression_tolerance"])
    rate_tol = float(policy["rate_regression_tolerance"])
    return (
        delta["avg_score_delta"] < -score_tol
        or delta["accepted_delta"] < 0
        or delta["compile_delta"] < -rate_tol
        or delta["runtime_delta"] < -rate_tol
        or delta["semantic_delta"] < -rate_tol
    )


def _materially_improved(delta: dict[str, Any], policy: dict[str, Any]) -> bool:
    return (
        delta["avg_score_delta"] >= float(policy["material_score_gain"])
        and delta["accepted_delta"] >= 0
    )


def _regression_reasons(label: str, delta: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    score_tol = float(policy["score_regression_tolerance"])
    rate_tol = float(policy["rate_regression_tolerance"])
    out: list[str] = []
    if delta["avg_score_delta"] < -score_tol:
        out.append(f"{label} avg_score_delta {delta['avg_score_delta']:+}")
    if delta["accepted_delta"] < 0:
        out.append(f"{label} accepted_delta {delta['accepted_delta']:+d}")
    if delta["compile_delta"] < -rate_tol:
        out.append(f"{label} compile_delta {delta['compile_delta']:+}")
    if delta["runtime_delta"] < -rate_tol:
        out.append(f"{label} runtime_delta {delta['runtime_delta']:+}")
    if delta["semantic_delta"] < -rate_tol:
        out.append(f"{label} semantic_delta {delta['semantic_delta']:+}")
    return out


# ── Per-candidate evaluation ──────────────────────────────────────────────────

def _evaluate_candidate(
    alias: str,
    results: list[dict[str, Any]],
    baseline_alias: str,
    strict_bench: str | None,
    generated_bench: str | None,
    policy: dict[str, Any],
) -> dict[str, Any]:
    cand_strict = _row(results, alias, strict_bench)
    cand_generated = _row(results, alias, generated_bench)
    base_strict = _row(results, baseline_alias, strict_bench)
    base_generated = _row(results, baseline_alias, generated_bench)

    override_valid = _override_ok([cand_strict, cand_generated, base_strict, base_generated])

    cand_meta = next((r for r in results if r.get("model_alias") == alias), {})
    base_entry: dict[str, Any] = {
        "model_alias": alias,
        "ollama_model": cand_meta.get("ollama_model", ""),
        "model": cand_meta.get("model", ""),
        "override_valid": override_valid,
        "strict": None,
        "generated": None,
        "weighted_score_delta": None,
        "reasons": [],
    }

    # Guardrail 1: override must be honoured.
    if policy["require_override_valid"] and not override_valid:
        base_entry["decision"] = DECISION_INVALID_OVERRIDE
        base_entry["promotion_level"] = _DECISION_TO_LEVEL[DECISION_INVALID_OVERRIDE]
        base_entry["reasons"] = ["model_override_valid is false; benchmark cannot be trusted"]
        return base_entry

    # Guardrail 2: need both benchmarks completed to weigh them.
    if not (_is_completed(cand_strict) and _is_completed(cand_generated)
            and _is_completed(base_strict) and _is_completed(base_generated)):
        base_entry["decision"] = DECISION_MANUAL_REVIEW
        base_entry["promotion_level"] = _DECISION_TO_LEVEL[DECISION_MANUAL_REVIEW]
        base_entry["reasons"] = [
            "strict and/or generated benchmark did not complete for both models; "
            "cannot decide on both axes"
        ]
        return base_entry

    strict = _bench_delta(cand_strict, base_strict)        # type: ignore[arg-type]
    generated = _bench_delta(cand_generated, base_generated)  # type: ignore[arg-type]
    base_entry["strict"] = strict
    base_entry["generated"] = generated

    weighted = round(
        float(policy["strict_weight"]) * strict["avg_score_delta"]
        + float(policy["generated_weight"]) * generated["avg_score_delta"],
        3,
    )
    base_entry["weighted_score_delta"] = weighted

    strict_regressed = _regressed(strict, policy)
    generated_regressed = _regressed(generated, policy)
    strict_improved = _materially_improved(strict, policy)
    generated_improved = _materially_improved(generated, policy)

    material = float(policy["material_score_gain"])
    negligible = float(policy["negligible_score_delta"])
    reasons: list[str] = []

    # Conflict: one axis regresses while the other materially improves.
    if (strict_regressed and generated_improved) or (generated_regressed and strict_improved):
        decision = DECISION_MANUAL_REVIEW
        if strict_regressed and generated_improved:
            reasons.append(
                f"strict benchmark regressed ({strict['avg_score_delta']:+} avg) while generated "
                f"benchmark materially improved ({generated['avg_score_delta']:+} avg)"
            )
        if generated_regressed and strict_improved:
            reasons.append(
                f"generated benchmark regressed ({generated['avg_score_delta']:+} avg) while strict "
                f"benchmark materially improved ({strict['avg_score_delta']:+} avg)"
            )
        reasons.append("conflicting evidence requires human decision")
    # Both axes regress, or weighted gain is materially negative → reject.
    elif (strict_regressed and generated_regressed) or weighted <= -material:
        decision = "reject"
        reasons.extend(_regression_reasons("strict", strict, policy))
        reasons.extend(_regression_reasons("generated", generated, policy))
        if not reasons:
            reasons.append(f"weighted score delta {weighted:+} is materially negative")
    # Clean material gain with no regression on either axis → promote to default.
    elif weighted >= material and not strict_regressed and not generated_regressed:
        decision = "promote_default"
        reasons.append(
            f"weighted score delta {weighted:+} >= {material} with no benchmark regression"
        )
    # Negligible change, all guardrails held → safe but no reason to switch.
    elif abs(weighted) <= negligible and not strict_regressed and not generated_regressed:
        decision = "safe_no_change"
        reasons.append(f"weighted score delta {weighted:+} within +/-{negligible}; guardrails held")
    # Positive but mixed/minor → candidate.
    else:
        decision = "candidate"
        reasons.append(
            f"weighted score delta {weighted:+} is positive but below promotion bar "
            f"or carries a minor trade-off"
        )
        reasons.extend(_regression_reasons("strict", strict, policy))
        reasons.extend(_regression_reasons("generated", generated, policy))

    base_entry["decision"] = decision
    base_entry["promotion_level"] = _DECISION_TO_LEVEL[decision]
    base_entry["reasons"] = reasons
    return base_entry


# ── Recommendation phrasing ───────────────────────────────────────────────────

def _recommendation(headline: dict[str, Any] | None, baseline_alias: str) -> tuple[str, str]:
    if not headline:
        return (
            f"stay on {baseline_alias}",
            "no candidate models present in comparison",
        )
    alias = headline["model_alias"]
    decision = headline["decision"]
    reason = "; ".join(headline.get("reasons") or []) or decision
    if decision == "promote_default":
        return f"promote {alias} to default", reason
    if decision == "candidate":
        return f"hold {alias} as candidate", reason
    if decision == "safe_no_change":
        return f"stay on {baseline_alias}", reason
    if decision == DECISION_MANUAL_REVIEW:
        return f"manual review required for {alias}", reason
    if decision == DECISION_INVALID_OVERRIDE:
        return f"invalid model override for {alias}; promotion blocked", reason
    # reject
    return f"stay on {baseline_alias}", reason


def _pick_headline(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda c: (
            _HEADLINE_PRIORITY.get(c.get("decision"), -1),
            c.get("weighted_score_delta") if c.get("weighted_score_delta") is not None else -1e9,
        ),
    )


# ── Public API ────────────────────────────────────────────────────────────────

def evaluate_comparison(
    comparison: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate a model_comparison payload and return a governance decision."""
    pol = dict(DEFAULT_POLICY)
    if policy:
        pol.update(policy)

    results = comparison.get("results", [])
    aggregates = comparison.get("models", [])
    baseline_alias = comparison.get("baseline_model") or ""
    benchmarks = _benchmarks_from(comparison)
    strict_bench, generated_bench = _classify_benchmarks(benchmarks)

    candidate_aliases = [
        row.get("model_alias")
        for row in aggregates
        if row.get("model_alias") and row.get("model_alias") != baseline_alias
    ]
    if not candidate_aliases:
        # Fall back to result rows if aggregates are absent.
        seen: list[str] = []
        for r in results:
            a = r.get("model_alias")
            if a and a != baseline_alias and a not in seen:
                seen.append(a)
        candidate_aliases = seen

    candidates = [
        _evaluate_candidate(alias, results, baseline_alias, strict_bench, generated_bench, pol)
        for alias in candidate_aliases
    ]

    headline = _pick_headline(candidates)
    recommendation, reason = _recommendation(headline, baseline_alias)
    headline_decision = headline["decision"] if headline else "safe_no_change"

    return {
        "timestamp": _now(),
        "baseline_model": baseline_alias,
        "policy": pol,
        "strict_benchmark": strict_bench,
        "generated_benchmark": generated_bench,
        "decision": headline_decision,
        "promotion_level": _DECISION_TO_LEVEL.get(headline_decision, "off_ladder"),
        "recommendation": recommendation,
        "recommendation_reason": reason,
        "override_valid": all(c.get("override_valid", False) for c in candidates) if candidates else True,
        "candidates": candidates,
        "comparison_timestamp": comparison.get("timestamp"),
    }


def evaluate_file(path: Path, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    return evaluate_comparison(_load_json(path), policy)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate model promotion policy")
    parser.add_argument(
        "--comparison",
        default=str(_HERE / "reports" / "model_comparison.json"),
        help="Path to model_comparison.json",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        decision = evaluate_file(Path(args.comparison))
    except Exception as exc:  # noqa: BLE001
        print(f"[model-promotion-policy] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(decision, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
