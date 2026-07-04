#!/usr/bin/env python3
"""Apply adapter promotion policy and update adapter governance registries."""
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
_ADAPTER_DIR = _HERE / "adapters"

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from promotion_policy import evaluate_file  # noqa: E402
from local_ai.shared.regression_policy import regression_verdict  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm_path(value: str | None) -> str:
    if not value:
        return ""
    return str(value).replace("\\", "/").rstrip("/")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _decision_entry(adapter_path: str, decision: dict[str, Any]) -> dict[str, Any]:
    metrics = decision.get("metrics") or {}
    return {
        "adapter_path": adapter_path,
        "status": decision.get("status"),
        "comparison_run_id": decision.get("comparison_run_id"),
        "avg_delta": metrics.get("avg_score_delta"),
        "accepted_delta": metrics.get("accepted_delta"),
        "runtime_delta": metrics.get("runtime_delta"),
        "notes": decision.get("reason"),
        "timestamp": _now(),
    }


def _upsert_adapter_list(path: Path, entry: dict[str, Any]) -> None:
    data = _load_json(path, {"adapters": []})
    adapters = data.get("adapters")
    if not isinstance(adapters, list):
        adapters = []
    key = _norm_path(entry.get("adapter_path"))
    adapters = [row for row in adapters if _norm_path(row.get("adapter_path")) != key]
    adapters.append(entry)
    data["adapters"] = adapters
    data["updated_at"] = _now()
    _write_json(path, data)


def _update_default_adapter(path: Path, entry: dict[str, Any]) -> None:
    data = _load_json(path, {"active": None, "history": []})
    history = data.get("history")
    if not isinstance(history, list):
        history = []
    active = data.get("active")
    if active:
        history.append(active)
    data["active"] = entry
    data["history"] = history
    data["updated_at"] = _now()
    _write_json(path, data)


def _registry_for_status(status: str) -> Path:
    if status == "promote":
        return _ADAPTER_DIR / "default_adapter.json"
    if status == "safe_no_change":
        return _ADAPTER_DIR / "safe_adapters.json"
    if status == "ablation_only":
        return _ADAPTER_DIR / "ablation_adapters.json"
    return _ADAPTER_DIR / "rejected_adapters.json"


def _apply_registry_update(adapter_path: str, decision: dict[str, Any]) -> Path:
    entry = _decision_entry(adapter_path, decision)
    status = str(decision.get("status"))
    target = _registry_for_status(status)
    if status == "promote":
        _update_default_adapter(target, entry)
    else:
        _upsert_adapter_list(target, entry)
    return target


def _build_report_md(adapter_path: str, decision: dict[str, Any], target: Path) -> str:
    metrics = decision.get("metrics") or {}
    largest = decision.get("largest_drop") or {}
    lines: list[str] = []
    a = lines.append
    a("# Adapter Promotion Report")
    a("")
    a(f"**Adapter**: `{adapter_path}`  ")
    a(f"**Status**: `{decision.get('status')}`  ")
    a(f"**Decision**: {decision.get('reason') or 'n/a'}  ")
    a(f"**Comparison run**: `{decision.get('comparison_run_id') or 'unknown'}`  ")
    a(f"**Registry updated**: `{target}`  ")
    a(f"**Generated**: {_now()}")
    a("")
    a("## Metrics")
    a("")
    a("| Metric | Delta |")
    a("|--------|------:|")
    for key in (
        "accepted_delta",
        "avg_score_delta",
        "compile_delta",
        "runtime_delta",
        "semantic_delta",
        "keyword_delta",
        "min_task_delta",
    ):
        a(f"| {key} | {metrics.get(key)} |")
    a("")
    a("## Largest Drop")
    a("")
    if largest:
        a(f"- Task: `{largest.get('id')}`")
        a(f"- Base score: {largest.get('base_score')}")
        a(f"- LoRA score: {largest.get('lora_score')}")
        a(f"- Delta: {largest.get('delta')}")
    else:
        a("- No task deltas found.")
    a("")
    guard = decision.get("regression_guard") or {}
    if guard:
        a("## Regression Guard")
        a("")
        a(f"- Verdict: `{guard.get('verdict')}`")
        if guard.get("override"):
            a(f"- Override: **{guard.get('override')}** (regression guard blocked promotion)")
        if guard.get("regression_reasons"):
            for r in guard["regression_reasons"]:
                a(f"- {r}")
        a("")
    a("## Promotion Decision")
    a("")
    if decision.get("status") == "promote":
        a("Adapter is promoted as the default adapter.")
    elif decision.get("status") == "safe_no_change":
        a("Adapter is recorded as safe_no_change and is not set as default.")
    elif decision.get("status") == "ablation_only":
        a("Adapter is retained for ablation only and is not eligible for default use.")
    else:
        a("Adapter is rejected for promotion.")
    return "\n".join(lines)


def _apply_regression_guard(decision: dict[str, Any]) -> dict[str, Any]:
    """Monotonic safety overlay: the regression guard can only BLOCK a promotion.

    It runs the canonical regression policy on the adapter's own comparison deltas
    and, if a hard regression is detected, downgrades `promote`/`safe_no_change`
    to `reject`. It never upgrades a decision. The guard record is attached for
    auditability regardless of outcome.
    """
    metrics = decision.get("metrics") or {}
    guard = regression_verdict(
        {
            "accepted_delta": metrics.get("accepted_delta", 0),
            "avg_score_delta": metrics.get("avg_score_delta", 0.0),
            "compile_delta": metrics.get("compile_delta", 0.0),
            "runtime_delta": metrics.get("runtime_delta", 0.0),
            "newly_broken_count": 0,
        },
        task_deltas=decision.get("task_deltas"),
    )
    decision["regression_guard"] = guard
    status = decision.get("status")
    verdict = guard["verdict"]
    # Block on a hard regression (-> reject) or conflicting evidence (-> ablation_only).
    # Conflicting evidence is not safe to auto-promote, but is not a clean regression.
    if verdict in ("regression", "manual_review") and status in ("promote", "safe_no_change"):
        new_status = "reject" if verdict == "regression" else "ablation_only"
        guard["override"] = f"{status} -> {new_status}"
        decision["status"] = new_status
        base_reason = (decision.get("reason") or "").strip()
        reasons = guard["regression_reasons"] or ["conflicting regression/improvement signals"]
        guard_reason = "regression guard: " + "; ".join(reasons)
        decision["reason"] = f"{base_reason}; {guard_reason}".lstrip("; ").strip()
    return decision


def promote(adapter_path: str, comparison_path: Path) -> dict[str, Any]:
    decision = evaluate_file(comparison_path)
    decision["adapter_path"] = adapter_path
    decision = _apply_regression_guard(decision)
    target = _apply_registry_update(adapter_path, decision)

    report = {
        "timestamp": _now(),
        "adapter_path": adapter_path,
        "status": decision.get("status"),
        "reason": decision.get("reason"),
        "metrics": decision.get("metrics"),
        "largest_drop": decision.get("largest_drop"),
        "regression_guard": decision.get("regression_guard"),
        "comparison_run_id": decision.get("comparison_run_id"),
        "comparison_path": str(comparison_path),
        "registry_updated": str(target),
        "promotion_decision": (
            "set_default"
            if decision.get("status") == "promote"
            else "recorded_" + str(decision.get("status"))
        ),
    }

    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(_REPORT_DIR / "adapter_promotion_report.json", report)
    (_REPORT_DIR / "adapter_promotion_report.md").write_text(
        _build_report_md(adapter_path, decision, target),
        encoding="utf-8",
    )
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote or classify a LoRA adapter")
    parser.add_argument("--adapter", required=True, help="Adapter path to classify")
    parser.add_argument(
        "--comparison",
        default=str(_REPORT_DIR / "comparison_report.json"),
        help="Path to comparison_report.json",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        report = promote(args.adapter, Path(args.comparison))
    except Exception as exc:
        print(f"[promote-adapter] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"[promote-adapter] status={report['status']}")
    print(f"[promote-adapter] registry={report['registry_updated']}")
    print(f"[promote-adapter] report={_REPORT_DIR / 'adapter_promotion_report.md'}")


if __name__ == "__main__":
    main()
