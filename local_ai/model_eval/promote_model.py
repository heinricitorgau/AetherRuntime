#!/usr/bin/env python3
"""Apply the model promotion policy and update model governance registries.

This is the model-governance executor, parallel to `sft/promote_adapter.py` and
`dataset_scaling/promote_generated_dataset.py`. It:

  1. Loads a model_comparison.json report.
  2. Calls the promotion policy (no hard-coded recommendation).
  3. Writes model_promotion_report.json / .md.
  4. Updates models/approved_models.json (records every candidate by decision;
     sets default_model only on promote_default).

Guardrails: it does not train, change benchmark scoring, modify datasets, touch
routing, or alter adapter governance. It only writes governance reports and the
approved-models registry.

Usage:
    python local_ai/model_eval/promote_model.py \\
        --comparison local_ai/model_eval/reports/model_comparison.json
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
_REPORT_DIR = _HERE / "reports"
_MODELS_DIR = _HERE / "models"
_APPROVED = _MODELS_DIR / "approved_models.json"

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from promotion_policy import (  # noqa: E402
    evaluate_file,
    _pick_headline,
    _recommendation,
    _DECISION_TO_LEVEL,
)
from local_ai.shared.regression_policy import regression_verdict  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


# ── Registry update ───────────────────────────────────────────────────────────

def _registry_entry(candidate: dict[str, Any], comparison_timestamp: str | None) -> dict[str, Any]:
    return {
        "model_alias": candidate.get("model_alias"),
        "ollama_model": candidate.get("ollama_model", ""),
        "decision": candidate.get("decision"),
        "promotion_level": candidate.get("promotion_level"),
        "weighted_score_delta": candidate.get("weighted_score_delta"),
        "override_valid": candidate.get("override_valid"),
        "strict": candidate.get("strict"),
        "generated": candidate.get("generated"),
        "reasons": candidate.get("reasons"),
        "regression_guard": candidate.get("regression_guard"),
        "comparison_timestamp": comparison_timestamp,
        "timestamp": _now(),
    }


def _update_registry(decision: dict[str, Any]) -> Path:
    data = _load_json(
        _APPROVED,
        {"baseline": decision.get("baseline_model"), "default_model": None, "models": []},
    )
    if not isinstance(data.get("models"), list):
        data["models"] = []

    data["baseline"] = decision.get("baseline_model")

    candidates = decision.get("candidates") or []
    comparison_ts = decision.get("comparison_timestamp")
    by_alias = {row.get("model_alias"): row for row in data["models"] if isinstance(row, dict)}

    promoted_default: str | None = None
    for cand in candidates:
        entry = _registry_entry(cand, comparison_ts)
        by_alias[entry["model_alias"]] = entry
        if cand.get("decision") == "promote_default":
            promoted_default = cand.get("model_alias")

    data["models"] = [by_alias[k] for k in sorted(by_alias)]
    # default_model is only ever set by a clean promote_default; never demoted here.
    if promoted_default:
        data["default_model"] = promoted_default
    elif "default_model" not in data:
        data["default_model"] = None
    data["updated_at"] = _now()

    _write_json(_APPROVED, data)
    return _APPROVED


# ── Reports ───────────────────────────────────────────────────────────────────

def _fmt_delta_table(delta: dict[str, Any] | None) -> list[str]:
    if not delta:
        return ["_no completed benchmark data_", ""]
    lines = [
        "| Metric | Delta |",
        "|--------|------:|",
    ]
    for key in ("avg_score_delta", "accepted_delta", "compile_delta", "runtime_delta", "semantic_delta"):
        lines.append(f"| {key} | {delta.get(key)} |")
    lines.append("")
    return lines


def _markdown(decision: dict[str, Any], registry_path: Path) -> str:
    lines: list[str] = []
    a = lines.append
    a("# Model Promotion Report")
    a("")
    a(f"Generated: `{decision.get('timestamp')}`  ")
    a(f"Baseline: `{decision.get('baseline_model')}`  ")
    a(f"Decision: **{decision.get('decision')}**  ")
    a(f"Promotion level: `{decision.get('promotion_level')}`  ")
    a(f"Recommendation: **{decision.get('recommendation')}**  ")
    a(f"Reason: {decision.get('recommendation_reason')}  ")
    a(f"Registry updated: `{registry_path}`")
    a("")
    a("## Policy")
    a("")
    pol = decision.get("policy") or {}
    a("| Setting | Value |")
    a("|---------|------:|")
    for key in ("strict_weight", "generated_weight", "require_override_valid", "material_score_gain"):
        a(f"| {key} | {pol.get(key)} |")
    a(f"| promotion_levels | {', '.join(pol.get('promotion_levels', []))} |")
    a("")
    a(f"Strict benchmark: `{decision.get('strict_benchmark')}`  ")
    a(f"Generated benchmark: `{decision.get('generated_benchmark')}`")
    a("")
    a("## Candidate Decisions")
    a("")
    for cand in decision.get("candidates") or []:
        a(f"### `{cand.get('model_alias')}` → {cand.get('decision')}")
        a("")
        a(f"- Promotion level: `{cand.get('promotion_level')}`")
        a(f"- Weighted score delta: {cand.get('weighted_score_delta')}")
        a(f"- Override valid: {cand.get('override_valid')}")
        a("")
        a("**Strict benchmark**")
        a("")
        lines.extend(_fmt_delta_table(cand.get("strict")))
        a("**Generated benchmark**")
        a("")
        lines.extend(_fmt_delta_table(cand.get("generated")))
        a("**Reasons**")
        a("")
        for r in cand.get("reasons") or []:
            a(f"- {r}")
        a("")
    a("## Guardrails")
    a("")
    a("- Recommendation comes from `promotion_policy.py`; nothing is hard-coded.")
    a("- A strict regression with a material generated gain resolves to `manual_review`.")
    a("- `invalid_model_override` blocks promotion entirely.")
    a("- This script does not train, change benchmark scoring, datasets, routing, or adapters.")
    return "\n".join(lines) + "\n"


def _apply_regression_guard(decision: dict[str, Any]) -> dict[str, Any]:
    """Monotonic safety overlay across candidates: can only BLOCK a promotion.

    Runs the canonical regression policy on each candidate's per-benchmark deltas.
    If any benchmark shows a hard regression, a `promote_default` candidate is
    downgraded to `manual_review`. The headline decision/recommendation is then
    recomputed with the policy's own helpers, so a blocked promotion can never
    remain the headline.
    """
    for cand in decision.get("candidates", []):
        per_benchmark: dict[str, str] = {}
        worst = "pass"
        for axis in ("strict", "generated"):
            d = cand.get(axis)
            if not d:
                continue
            g = regression_verdict(
                {
                    "accepted_delta": d.get("accepted_delta", 0),
                    "avg_score_delta": d.get("avg_score_delta", 0.0),
                    "compile_delta": d.get("compile_delta", 0.0),
                    "runtime_delta": d.get("runtime_delta", 0.0),
                    "newly_broken_count": 0,
                }
            )
            per_benchmark[axis] = g["verdict"]
            if g["verdict"] == "regression":
                worst = "regression"
            elif g["verdict"] == "manual_review" and worst != "regression":
                worst = "manual_review"
        cand["regression_guard"] = {"per_benchmark": per_benchmark, "verdict": worst}
        # Block a default promotion on a hard regression OR conflicting evidence.
        if cand.get("decision") == "promote_default" and worst in ("regression", "manual_review"):
            cand["regression_guard"]["override"] = "promote_default -> manual_review"
            cand["decision"] = "manual_review"
            cand["promotion_level"] = _DECISION_TO_LEVEL.get("manual_review", "off_ladder")
            cand.setdefault("reasons", []).append(
                f"regression guard blocked promotion (benchmark verdict: {worst})"
            )

    # Recompute the headline with the policy's own helpers (monotonic — guard only
    # downgrades candidates, so the headline can only become less promotional).
    headline = _pick_headline(decision.get("candidates") or [])
    headline_decision = headline["decision"] if headline else decision.get("decision")
    decision["decision"] = headline_decision
    decision["promotion_level"] = _DECISION_TO_LEVEL.get(headline_decision, "off_ladder")
    rec, reason = _recommendation(headline, decision.get("baseline_model") or "")
    decision["recommendation"] = rec
    decision["recommendation_reason"] = reason
    return decision


def promote_model(comparison_path: Path, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    decision = evaluate_file(comparison_path, policy)
    decision = _apply_regression_guard(decision)
    registry_path = _update_registry(decision)

    report = dict(decision)
    report["comparison_path"] = str(comparison_path)
    report["registry_updated"] = str(registry_path)

    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(_REPORT_DIR / "model_promotion_report.json", report)
    (_REPORT_DIR / "model_promotion_report.md").write_text(
        _markdown(decision, registry_path), encoding="utf-8"
    )
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply the model promotion policy")
    parser.add_argument(
        "--comparison",
        default=str(_REPORT_DIR / "model_comparison.json"),
        help="Path to model_comparison.json",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        report = promote_model(Path(args.comparison))
    except Exception as exc:  # noqa: BLE001
        print(f"[promote-model] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"[promote-model] decision={report['decision']}")
    print(f"[promote-model] recommendation={report['recommendation']}")
    print(f"[promote-model] registry={report['registry_updated']}")
    print(f"[promote-model] report={_REPORT_DIR / 'model_promotion_report.md'}")


if __name__ == "__main__":
    main()
