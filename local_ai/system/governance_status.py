#!/usr/bin/env python3
"""Unified governance observability (roadmap #7).

Read-only cross-layer aggregator. It answers a single question — "what is
promoted / safe / rejected / awaiting review across every governed resource?" —
by reading the registries and reports the governance layers already produce:

  - Adapters : local_ai/sft/adapters/*.json
  - Models   : local_ai/model_eval/models/approved_models.json
  - Datasets : local_ai/dataset_scaling/reports/generated_dataset_promotion_report.json
  - Regression: local_ai/benchmark/reports/regression/regression_report.json
               local_ai/benchmark/reports/trend/benchmark_trend.json

It does not promote, train, run models, or change any policy — it only observes.

Outputs:
  local_ai/system/reports/governance_status.json
  local_ai/system/reports/governance_status.md

Usage:
  python local_ai/system/governance_status.py
  python local_ai/system/governance_status.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_REPORT_DIR = _HERE / "reports"
_OUT_JSON = _REPORT_DIR / "governance_status.json"
_OUT_MD = _REPORT_DIR / "governance_status.md"

_ADAPTER_DIR = _LOCAL_AI / "sft" / "adapters"
_APPROVED_MODELS = _LOCAL_AI / "model_eval" / "models" / "approved_models.json"
_DATASET_REPORT = _LOCAL_AI / "dataset_scaling" / "reports" / "generated_dataset_promotion_report.json"
_REGRESSION_REPORT = _LOCAL_AI / "benchmark" / "reports" / "regression" / "regression_report.json"
_TREND_REPORT = _LOCAL_AI / "benchmark" / "reports" / "trend" / "benchmark_trend.json"
_RELIABILITY_REPORT = _LOCAL_AI / "benchmark" / "reports" / "reliability" / "eval_reliability.json"
_PROFILE_REPORT = _LOCAL_AI / "config" / "profile_governance_report.json"
_GOLDENS_REGISTRY = _LOCAL_AI / "goldens" / "approved_goldens.json"
_ROUTING_REPORT = _LOCAL_AI / "routing" / "reports" / "routing_governance_report.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _adapters_section() -> dict[str, Any]:
    files = {
        "default": _ADAPTER_DIR / "default_adapter.json",
        "safe_no_change": _ADAPTER_DIR / "safe_adapters.json",
        "ablation_only": _ADAPTER_DIR / "ablation_adapters.json",
        "reject": _ADAPTER_DIR / "rejected_adapters.json",
    }
    entries: list[dict[str, Any]] = []
    default_adapter = None
    for status, path in files.items():
        data = _load(path)
        if not data:
            continue
        if status == "default":
            active = data.get("active")
            if active:
                default_adapter = active.get("adapter_path")
                entries.append({"adapter_path": active.get("adapter_path"), "status": "default"})
            continue
        for row in data.get("adapters", []):
            entries.append({"adapter_path": row.get("adapter_path"), "status": status})
    return {
        "default_adapter": default_adapter,
        "count": len(entries),
        "entries": entries,
    }


def _models_section() -> dict[str, Any]:
    data = _load(_APPROVED_MODELS)
    models = [
        {"model_alias": m.get("model_alias"), "decision": m.get("decision")}
        for m in data.get("models", [])
        if isinstance(m, dict)
    ]
    return {
        "baseline": data.get("baseline"),
        "default_model": data.get("default_model"),
        "count": len(models),
        "entries": models,
    }


def _datasets_section() -> dict[str, Any]:
    data = _load(_DATASET_REPORT)
    if not data:
        return {"count": 0, "entries": []}
    return {
        "count": 1,
        "entries": [
            {
                "dataset_id": data.get("dataset_id"),
                "decision": data.get("decision"),
                "candidate_training_ready": data.get("candidate_training_ready"),
            }
        ],
    }


def _regression_section() -> dict[str, Any]:
    latest = _load(_REGRESSION_REPORT)
    trend = _load(_TREND_REPORT)
    trend_summary = [
        {"model": m.get("model"), "trend": m.get("trend"),
         "latest_regression": (m.get("latest_regression") or {}).get("verdict")}
        for m in trend.get("models", [])
    ]
    return {
        "latest_report": {
            "base_run_id": latest.get("base_run_id"),
            "new_run_id": latest.get("new_run_id"),
            "verdict": latest.get("verdict"),
        } if latest else None,
        "trend": trend_summary,
    }


def _reliability_section() -> dict[str, Any]:
    data = _load(_RELIABILITY_REPORT)
    if not data:
        return {}
    return {
        "verdict": data.get("verdict"),
        "stamp_rate": data.get("stamp_rate"),
        "flaky_task_count": data.get("flaky_task_count"),
        "total_runs": data.get("total_runs"),
    }


def _profiles_section() -> dict[str, Any]:
    data = _load(_PROFILE_REPORT)
    if not data:
        return {}
    return {
        "decision": data.get("decision"),
        "approved": data.get("profiles_approved"),
        "total": data.get("profiles_total"),
        "warnings": len(data.get("warnings", [])),
    }


def _goldens_section() -> dict[str, Any]:
    data = _load(_GOLDENS_REGISTRY)
    if not data:
        return {}
    return {
        "approved": data.get("approved_count"),
        "human_verified": data.get("human_verified_count"),
    }


def _routing_section() -> dict[str, Any]:
    data = _load(_ROUTING_REPORT)
    if not data:
        return {}
    return {
        "verdict": data.get("verdict"),
        "violations": len(data.get("violations", [])),
    }


def build_status() -> dict[str, Any]:
    adapters = _adapters_section()
    models = _models_section()
    datasets = _datasets_section()
    regression = _regression_section()
    reliability = _reliability_section()
    profiles = _profiles_section()
    goldens = _goldens_section()
    routing = _routing_section()

    # Cross-layer headline: what is actually promoted to default anywhere, and
    # what is awaiting human review.
    promoted = []
    if adapters["default_adapter"]:
        promoted.append({"layer": "adapter", "resource": adapters["default_adapter"]})
    if models["default_model"]:
        promoted.append({"layer": "model", "resource": models["default_model"]})

    awaiting_review = [
        {"layer": "model", "resource": m["model_alias"]}
        for m in models["entries"] if m["decision"] == "manual_review"
    ]

    return {
        "timestamp": _now(),
        "promoted_to_default": promoted,
        "awaiting_manual_review": awaiting_review,
        "adapters": adapters,
        "models": models,
        "datasets": datasets,
        "regression": regression,
        "reliability": reliability,
        "profiles": profiles,
        "goldens": goldens,
        "routing": routing,
    }


def _markdown(status: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append
    a("# Governance Status")
    a("")
    a(f"Generated: `{status['timestamp']}`")
    a("")
    a("## Cross-Layer Headline")
    a("")
    promoted = status["promoted_to_default"]
    if promoted:
        for p in promoted:
            a(f"- Promoted to default — {p['layer']}: `{p['resource']}`")
    else:
        a("- No resource promoted to default in any layer.")
    review = status["awaiting_manual_review"]
    if review:
        for r in review:
            a(f"- Awaiting manual review — {r['layer']}: `{r['resource']}`")
    a("")
    a("## Adapters")
    a("")
    a(f"- Default: `{status['adapters']['default_adapter']}`")
    if status["adapters"]["entries"]:
        a("")
        a("| Adapter | Status |")
        a("|---------|--------|")
        for e in status["adapters"]["entries"]:
            a(f"| `{e['adapter_path']}` | {e['status']} |")
    a("")
    a("## Models")
    a("")
    a(f"- Baseline: `{status['models']['baseline']}`")
    a(f"- Default: `{status['models']['default_model']}`")
    if status["models"]["entries"]:
        a("")
        a("| Model | Decision |")
        a("|-------|----------|")
        for e in status["models"]["entries"]:
            a(f"| `{e['model_alias']}` | {e['decision']} |")
    a("")
    a("## Datasets")
    a("")
    if status["datasets"]["entries"]:
        a("| Dataset | Decision | Candidate-ready |")
        a("|---------|----------|:---------------:|")
        for e in status["datasets"]["entries"]:
            a(f"| `{e['dataset_id']}` | {e['decision']} | {e['candidate_training_ready']} |")
    else:
        a("No dataset promotion report found.")
    a("")
    a("## Regression")
    a("")
    latest = status["regression"]["latest_report"]
    if latest:
        a(f"- Latest detector verdict: **{latest['verdict']}** "
          f"(`{latest['base_run_id']}` → `{latest['new_run_id']}`)")
    else:
        a("- No regression report found.")
    for t in status["regression"]["trend"]:
        a(f"- Trend `{t['model']}`: {t['trend']} (latest-pair {t['latest_regression']})")
    a("")
    a("## Evaluation Reliability")
    a("")
    rel = status.get("reliability") or {}
    if rel:
        a(f"- Verdict: **{rel.get('verdict')}** "
          f"(stamp rate {rel.get('stamp_rate')}, flaky tasks {rel.get('flaky_task_count')}, "
          f"runs {rel.get('total_runs')})")
    else:
        a("- No reliability report found.")
    a("")
    a("## Prompt / Profile Governance")
    a("")
    prof = status.get("profiles") or {}
    if prof:
        a(f"- Decision: **{prof.get('decision')}** "
          f"(approved {prof.get('approved')}/{prof.get('total')}, warnings {prof.get('warnings')})")
    else:
        a("- No profile governance report found.")
    a("")
    a("## Goldens")
    a("")
    gold = status.get("goldens") or {}
    if gold:
        a(f"- Approved goldens: {gold.get('approved')} (human-verified: {gold.get('human_verified')})")
    else:
        a("- No goldens registry found.")
    a("")
    a("## Routing Governance")
    a("")
    rt = status.get("routing") or {}
    if rt:
        a(f"- Verdict: **{rt.get('verdict')}** (violations {rt.get('violations')})")
    else:
        a("- No routing governance report found.")
    a("")
    a("## Guardrails")
    a("")
    a("- Read-only observability; promotes nothing, trains nothing, runs no models.")
    a("- Reflects the registries/reports produced by the governed promotion gates.")
    return "\n".join(lines) + "\n"


def write_reports(status: dict[str, Any]) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _OUT_JSON.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _OUT_MD.write_text(_markdown(status), encoding="utf-8")


def _self_test() -> bool:
    status = build_status()
    required = {"adapters", "models", "datasets", "regression", "promoted_to_default"}
    missing = required - set(status)
    if missing:
        print(f"[governance-status] self-test FAIL: missing sections {missing}")
        return False
    print("[governance-status] self-test ok: all sections present")
    return True


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified governance status aggregator")
    parser.add_argument("--self-test", action="store_true", help="Verify aggregation shape (read-only)")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.self_test:
        ok = _self_test()
        print(f"[governance-status] self-test {'PASS' if ok else 'FAIL'}")
        sys.exit(0 if ok else 1)

    status = build_status()
    write_reports(status)
    promoted = status["promoted_to_default"]
    review = status["awaiting_manual_review"]
    print(f"[governance-status] promoted_to_default={len(promoted)} awaiting_review={len(review)}")
    print(f"[governance-status] adapters={status['adapters']['count']} "
          f"models={status['models']['count']} datasets={status['datasets']['count']}")
    print(f"[governance-status] report >> {_OUT_MD}")


if __name__ == "__main__":
    main()
