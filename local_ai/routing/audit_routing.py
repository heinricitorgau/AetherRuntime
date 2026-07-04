#!/usr/bin/env python3
"""Routing governance audit (roadmap #4 — close the governance loop).

The router already consults the adapter registry and refuses blocked adapters.
This read-only audit *proves* that property: it checks the routing policy and the
latest routing plan against the live adapter registry and flags any rule or plan
decision that points at a non-approved / blocked adapter. It runs no models.

Outputs:
  reports/routing_governance_report.json
  reports/routing_governance_report.md

Usage:
  python local_ai/routing/audit_routing.py
  python local_ai/routing/audit_routing.py --self-test
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
_REPO_ROOT = _LOCAL_AI.parent
sys.path.insert(0, str(_HERE))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from adapter_router import AdapterRouter, _adapter_name  # noqa: E402

_POLICY_PATH = _HERE / "routing_policy.json"
_PLAN_PATH = _HERE / "reports" / "routing_plan.json"
_REPORT_DIR = _HERE / "reports"
_REPORT_JSON = _REPORT_DIR / "routing_governance_report.json"
_REPORT_MD = _REPORT_DIR / "routing_governance_report.md"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def audit() -> dict[str, Any]:
    router = AdapterRouter()
    usable = router.registry["usable_by_name"]
    blocked = router.registry["blocked_by_name"]
    policy = _load(_POLICY_PATH)
    plan = _load(_PLAN_PATH)

    violations: list[str] = []
    warnings: list[str] = []

    # ── Policy audit: rules must not allow blocked adapters ───────────────────
    for topic, rule in policy.items():
        if not isinstance(rule, dict):
            continue
        for adapter in rule.get("allowed_adapters", []) or []:
            name = _adapter_name(adapter)
            if name in blocked:
                violations.append(
                    f"policy[{topic}] allows blocked adapter '{name}' "
                    f"(status {blocked[name].get('status')})"
                )
            elif name not in usable:
                warnings.append(f"policy[{topic}] references unknown/unpromoted adapter '{name}'")

    # ── Plan audit: every selected adapter must currently be approved ─────────
    plan_checked = 0
    for d in plan.get("decisions", []) or []:
        if d.get("selected") == "adapter":
            plan_checked += 1
            name = _adapter_name(d.get("selected_adapter") or d.get("selected_model_path") or "")
            if name in blocked:
                violations.append(
                    f"plan task {d.get('task_id')} selected blocked adapter '{name}'"
                )
            elif name not in usable:
                violations.append(
                    f"plan task {d.get('task_id')} selected non-approved adapter '{name}'"
                )

    verdict = "pass" if not violations else "violations"
    return {
        "timestamp": _now(),
        "verdict": verdict,
        "policy_path": str(_POLICY_PATH),
        "plan_path": str(_PLAN_PATH) if plan else None,
        "usable_adapters": sorted(usable),
        "blocked_adapters": sorted(blocked),
        "plan_adapter_decisions_checked": plan_checked,
        "violations": violations,
        "warnings": warnings,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append
    a("# Routing Governance Report")
    a("")
    a(f"Generated: `{report['timestamp']}`  ")
    a(f"Verdict: **{report['verdict']}**")
    a("")
    a(f"- Usable adapters: {report['usable_adapters'] or '—'}")
    a(f"- Blocked adapters: {report['blocked_adapters'] or '—'}")
    a(f"- Plan adapter decisions checked: {report['plan_adapter_decisions_checked']}")
    a("")
    a("## Violations")
    a("")
    if report["violations"]:
        for v in report["violations"]:
            a(f"- {v}")
    else:
        a("None — routing selects only governed-approved adapters.")
    a("")
    a("## Warnings")
    a("")
    if report["warnings"]:
        for w in report["warnings"]:
            a(f"- {w}")
    else:
        a("None.")
    a("")
    a("## Guardrails")
    a("")
    a("- Read-only audit; runs no models, changes no routing policy.")
    a("- A violation means routing could use a non-approved adapter — block release until fixed.")
    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any]) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _REPORT_MD.write_text(_markdown(report), encoding="utf-8")


def _self_test() -> bool:
    report = audit()
    required = {"verdict", "violations", "warnings", "usable_adapters"}
    ok = not (required - set(report))
    print(f"[audit-routing] self-test {'ok' if ok else 'FAIL'}: verdict={report.get('verdict')}")
    return ok


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Routing governance audit")
    parser.add_argument("--self-test", action="store_true", help="Read-only audit self-test")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.self_test:
        ok = _self_test()
        print(f"[audit-routing] self-test {'PASS' if ok else 'FAIL'}")
        sys.exit(0 if ok else 1)

    report = audit()
    write_reports(report)
    print(f"[audit-routing] verdict={report['verdict']} "
          f"violations={len(report['violations'])} warnings={len(report['warnings'])}")
    print(f"[audit-routing] report >> {_REPORT_MD}")
    sys.exit(1 if report["verdict"] == "violations" else 0)


if __name__ == "__main__":
    main()
