#!/usr/bin/env python3
"""Policy-driven task adapter router."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .task_classifier import classify_task
except ImportError:  # pragma: no cover - direct script import
    from task_classifier import classify_task

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_REPO_ROOT = _LOCAL_AI.parent
_POLICY_PATH = _HERE / "routing_policy.json"
_ADAPTER_DIR = _LOCAL_AI / "sft" / "adapters"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _adapter_name(path_or_name: str) -> str:
    return Path(str(path_or_name).replace("\\", "/")).name


def _load_adapter_registry() -> dict[str, Any]:
    safe = _load_json(_ADAPTER_DIR / "safe_adapters.json", {"adapters": []}).get("adapters") or []
    ablation = _load_json(_ADAPTER_DIR / "ablation_adapters.json", {"adapters": []}).get("adapters") or []
    rejected = _load_json(_ADAPTER_DIR / "rejected_adapters.json", {"adapters": []}).get("adapters") or []
    promoted = _load_json(_ADAPTER_DIR / "promoted_adapters.json", {"adapters": []}).get("adapters") or []
    default_data = _load_json(_ADAPTER_DIR / "default_adapter.json", {"active": None})
    default_active = default_data.get("active")

    usable: dict[str, dict[str, Any]] = {}
    blocked: dict[str, dict[str, Any]] = {}

    for row in promoted:
        row = dict(row)
        row.setdefault("status", "promote")
        usable[_adapter_name(row.get("adapter_path", ""))] = row
    if isinstance(default_active, dict) and default_active.get("adapter_path"):
        row = dict(default_active)
        row.setdefault("status", "promote")
        usable[_adapter_name(row.get("adapter_path", ""))] = row
    for row in safe:
        row = dict(row)
        row.setdefault("status", "safe_no_change")
        usable[_adapter_name(row.get("adapter_path", ""))] = row

    for row in ablation:
        row = dict(row)
        row.setdefault("status", "ablation_only")
        blocked[_adapter_name(row.get("adapter_path", ""))] = row
    for row in rejected:
        row = dict(row)
        row.setdefault("status", "reject")
        blocked[_adapter_name(row.get("adapter_path", ""))] = row

    return {
        "usable_by_name": usable,
        "blocked_by_name": blocked,
        "counts": {
            "safe": len(safe),
            "promoted": len(promoted) + (1 if isinstance(default_active, dict) else 0),
            "ablation": len(ablation),
            "rejected": len(rejected),
        },
    }


class AdapterRouter:
    def __init__(self, policy_path: Path = _POLICY_PATH) -> None:
        self.policy_path = policy_path
        self.policy = _load_json(policy_path, {"default": {"use": "base"}})
        self.registry = _load_adapter_registry()

    def route_task(self, task: dict[str, Any]) -> dict[str, Any]:
        topic = classify_task(task)
        rule = self.policy.get(topic) or self.policy.get("default", {"use": "base"})
        default_rule = self.policy.get("default", {"use": "base"})

        if rule.get("use") == "base":
            return self._base_decision(task, topic, "policy uses base")

        allowed = list(rule.get("allowed_adapters") or [])
        allowed_status = set(rule.get("only_if_status") or ["promote", "safe_no_change"])
        fallback = rule.get("fallback") or default_rule.get("use") or "base"

        for adapter_name in allowed:
            blocked = self.registry["blocked_by_name"].get(adapter_name)
            if blocked:
                continue
            row = self.registry["usable_by_name"].get(adapter_name)
            if not row:
                continue
            status = str(row.get("status") or "")
            if status not in allowed_status:
                continue
            adapter_path = str(row.get("adapter_path") or "")
            return {
                "task_id": task.get("id"),
                "detected_topic": topic,
                "selected": "adapter",
                "selected_model_path": adapter_path,
                "selected_adapter": adapter_name,
                "selected_adapter_status": status,
                "fallback_reason": "",
                "policy_rule": rule,
            }

        reason = "no allowed adapter with permitted status"
        if fallback != "base":
            reason = f"{reason}; unsupported fallback={fallback}, using base"
        return self._base_decision(task, topic, reason, rule)

    def _base_decision(
        self,
        task: dict[str, Any],
        topic: str,
        reason: str,
        rule: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "task_id": task.get("id"),
            "detected_topic": topic,
            "selected": "base",
            "selected_model_path": "base",
            "selected_adapter": None,
            "selected_adapter_status": None,
            "fallback_reason": reason,
            "policy_rule": rule or self.policy.get(topic) or self.policy.get("default", {}),
        }

    def summary(self) -> dict[str, Any]:
        return {
            "timestamp": _now(),
            "policy_path": str(self.policy_path),
            "adapter_registry_counts": self.registry["counts"],
            "usable_adapters": sorted(self.registry["usable_by_name"]),
            "blocked_adapters": sorted(self.registry["blocked_by_name"]),
        }
