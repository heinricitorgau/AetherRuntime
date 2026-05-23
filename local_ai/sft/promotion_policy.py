#!/usr/bin/env python3
"""Adapter promotion policy for LoRA comparison reports."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_REPO_ROOT = _LOCAL_AI.parent
_EXPERIMENT_REGISTRY = _LOCAL_AI / "experiments" / "registry"
_LEADERBOARD = _LOCAL_AI / "experiments" / "reports" / "leaderboard.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm_path(value: str | None) -> str:
    if not value:
        return ""
    return str(value).replace("\\", "/").rstrip("/")


def _rate_delta(comparison: dict[str, Any], key: str) -> float:
    deltas = comparison.get("deltas") or {}
    if key in deltas:
        return float(deltas.get(key) or 0.0)
    base = ((comparison.get("base") or {}).get("rates") or {}).get(key, 0.0)
    lora = ((comparison.get("lora") or {}).get("rates") or {}).get(key, 0.0)
    return float(lora or 0.0) - float(base or 0.0)


def _score_delta(comparison: dict[str, Any]) -> float:
    deltas = comparison.get("deltas") or {}
    if "avg_score" in deltas:
        return float(deltas.get("avg_score") or 0.0)
    base = (comparison.get("base") or {}).get("avg_score", 0.0)
    lora = (comparison.get("lora") or {}).get("avg_score", 0.0)
    return float(lora or 0.0) - float(base or 0.0)


def _accepted_delta(comparison: dict[str, Any]) -> int:
    deltas = comparison.get("deltas") or {}
    if "accepted" in deltas:
        return int(deltas.get("accepted") or 0)
    base = (comparison.get("base") or {}).get("accepted", 0)
    lora = (comparison.get("lora") or {}).get("accepted", 0)
    return int(lora or 0) - int(base or 0)


def _task_deltas(comparison: dict[str, Any]) -> list[dict[str, Any]]:
    base_by_id = {r.get("id"): r for r in comparison.get("base_results", [])}
    lora_by_id = {r.get("id"): r for r in comparison.get("lora_results", [])}
    rows: list[dict[str, Any]] = []
    for task_id in sorted(set(base_by_id) | set(lora_by_id)):
        if not task_id:
            continue
        base = base_by_id.get(task_id, {})
        lora = lora_by_id.get(task_id, {})
        base_score = float(base.get("score", 0.0) or 0.0)
        lora_score = float(lora.get("score", 0.0) or 0.0)
        rows.append(
            {
                "id": task_id,
                "base_score": base_score,
                "lora_score": lora_score,
                "delta": round(lora_score - base_score, 3),
                "base_runtime_pass": bool(
                    ((base.get("checks") or {}).get("runtime") or {}).get("passed", False)
                ),
                "lora_runtime_pass": bool(
                    ((lora.get("checks") or {}).get("runtime") or {}).get("passed", False)
                ),
            }
        )
    return rows


def _load_registry_match(comparison: dict[str, Any]) -> dict[str, Any] | None:
    adapter = _norm_path(comparison.get("adapter") or (comparison.get("metadata") or {}).get("adapter_path"))
    timestamp = str(comparison.get("timestamp") or "")
    if not _EXPERIMENT_REGISTRY.exists():
        return None

    matches: list[dict[str, Any]] = []
    for path in _EXPERIMENT_REGISTRY.glob("*.json"):
        try:
            row = _load_json(path)
        except Exception:
            continue
        if row.get("run_type") != "compare_lora":
            continue
        if _norm_path(row.get("adapter_path")) != adapter:
            continue
        row["_registry_file"] = str(path)
        matches.append(row)

    if not matches:
        return None
    for row in matches:
        if timestamp and row.get("timestamp") == timestamp:
            return row
    matches.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    return matches[0]


def _load_leaderboard_match(registry_run_id: str | None) -> dict[str, Any] | None:
    if not registry_run_id or not _LEADERBOARD.exists():
        return None
    try:
        data = _load_json(_LEADERBOARD)
    except Exception:
        return None
    for row in data.get("runs", []):
        if row.get("run_id") == registry_run_id:
            return row
    return None


def evaluate_comparison(comparison: dict[str, Any]) -> dict[str, Any]:
    """Return a policy decision for a comparison_report.json payload."""
    task_rows = _task_deltas(comparison)
    largest_drop = min(task_rows, key=lambda row: row["delta"], default=None)
    min_task_delta = float(largest_drop["delta"]) if largest_drop else 0.0

    metrics = {
        "accepted_delta": _accepted_delta(comparison),
        "avg_score_delta": round(_score_delta(comparison), 3),
        "compile_delta": round(_rate_delta(comparison, "compile_pass_rate"), 3),
        "runtime_delta": round(_rate_delta(comparison, "runtime_pass_rate"), 3),
        "semantic_delta": round(_rate_delta(comparison, "semantic_pass_rate"), 3),
        "keyword_delta": round(_rate_delta(comparison, "keyword_pass_rate"), 3),
        "min_task_delta": min_task_delta,
    }

    accepted_ok = metrics["accepted_delta"] >= 0
    compile_ok = metrics["compile_delta"] >= 0
    runtime_ok = metrics["runtime_delta"] >= 0
    semantic_ok = metrics["semantic_delta"] >= 0
    no_large_task_drop = min_task_delta >= -5
    severe_runtime_collapse = metrics["runtime_delta"] <= -0.5

    reasons: list[str] = []
    status = "reject"

    if (
        metrics["accepted_delta"] < 0
        or metrics["compile_delta"] < 0
        or metrics["semantic_delta"] < 0
        or severe_runtime_collapse
        or min_task_delta < -20
    ):
        status = "reject"
        if metrics["accepted_delta"] < 0:
            reasons.append("accepted_delta < 0")
        if metrics["compile_delta"] < 0:
            reasons.append("compile_delta < 0")
        if metrics["semantic_delta"] < 0:
            reasons.append("semantic_delta < 0")
        if severe_runtime_collapse:
            reasons.append("severe runtime collapse")
        if min_task_delta < -20:
            reasons.append("task delta < -20")
    elif (
        accepted_ok
        and metrics["avg_score_delta"] > 0
        and compile_ok
        and runtime_ok
        and semantic_ok
        and no_large_task_drop
    ):
        status = "promote"
        reasons.append("positive avg_score_delta with no guardrail regressions")
    elif (
        accepted_ok
        and abs(metrics["avg_score_delta"]) <= 0.5
        and compile_ok
        and runtime_ok
        and semantic_ok
        and no_large_task_drop
    ):
        status = "safe_no_change"
        reasons.append("no material aggregate change and all guardrails held")
    elif (
        accepted_ok
        and compile_ok
        and semantic_ok
        and (
            metrics["avg_score_delta"] < -0.5
            or metrics["runtime_delta"] < 0
            or min_task_delta < -5
        )
    ):
        status = "ablation_only"
        if metrics["avg_score_delta"] < -0.5:
            reasons.append("avg_score_delta < -0.5")
        if metrics["runtime_delta"] < 0:
            reasons.append("runtime_delta < 0")
        if min_task_delta < -5:
            reasons.append("task delta < -5")
    else:
        status = "reject"
        reasons.append("comparison did not satisfy promotion or safe-no-change criteria")

    registry_match = _load_registry_match(comparison)
    registry_run_id = registry_match.get("run_id") if registry_match else None
    leaderboard_match = _load_leaderboard_match(registry_run_id)

    adapter_path = str(comparison.get("adapter") or (comparison.get("metadata") or {}).get("adapter_path") or "")
    return {
        "timestamp": _now(),
        "adapter_path": adapter_path,
        "adapter_name": comparison.get("adapter_name") or Path(adapter_path).name,
        "status": status,
        "reason": "; ".join(reasons),
        "metrics": metrics,
        "largest_drop": largest_drop,
        "task_deltas": task_rows,
        "comparison_run_id": registry_run_id,
        "comparison_timestamp": comparison.get("timestamp"),
        "comparison_verdict": comparison.get("verdict"),
        "experiment_registry": registry_match,
        "leaderboard": leaderboard_match,
    }


def evaluate_file(path: Path) -> dict[str, Any]:
    return evaluate_comparison(_load_json(path))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate adapter promotion policy")
    parser.add_argument(
        "--comparison",
        default=str(_HERE / "reports" / "comparison_report.json"),
        help="Path to comparison_report.json",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        decision = evaluate_file(Path(args.comparison))
    except Exception as exc:
        print(f"[promotion-policy] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(decision, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
