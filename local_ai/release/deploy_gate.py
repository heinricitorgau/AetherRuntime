#!/usr/bin/env python3
"""Deployment readiness gate (roadmap #10 — capstone).

A single governed answer to "is this safe to release/deploy?". It aggregates the
reports every governance layer already produces and derives a verdict from a
policy (block-conditions vs warn-conditions are data, not code). It runs no
models and changes no state — it only reads and decides.

Verdicts:
  ready                 all blocking checks pass, no warnings
  ready_with_warnings   all blocking checks pass, but soft concerns remain
  blocked               at least one blocking check failed

Inputs (each produced by its governance tool; missing inputs are treated as
not-yet-run and surfaced):
  system/reports/smoke_test_report.json
  config/profile_validation_report.json
  config/profile_governance_report.json
  routing/reports/routing_governance_report.json
  benchmark/reports/regression/regression_report.json
  benchmark/reports/reliability/eval_reliability.json
  system/reports/governance_status.json
  goldens/approved_goldens.json

Outputs:
  release/reports/deploy_readiness.json
  release/reports/deploy_readiness.md

Usage:
  python local_ai/release/deploy_gate.py
  python local_ai/release/deploy_gate.py --self-test
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
_OUT_JSON = _REPORT_DIR / "deploy_readiness.json"
_OUT_MD = _REPORT_DIR / "deploy_readiness.md"

# Which check ids block a release vs. only warn (data, not code).
DEFAULT_DEPLOY_POLICY: dict[str, Any] = {
    "block_on": ["smoke", "config", "profile_governance", "routing_governance", "regression"],
    "warn_on": ["reliability", "awaiting_review", "human_goldens"],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _checks() -> list[dict[str, Any]]:
    """Each check -> {id, ok, detail}. ok=None means 'not run / unknown'."""
    checks: list[dict[str, Any]] = []

    smoke = _load(_LOCAL_AI / "system" / "reports" / "smoke_test_report.json")
    checks.append({
        "id": "smoke",
        "ok": (smoke.get("status") == "PASS") if smoke else None,
        "detail": f"status={smoke.get('status')}" if smoke else "no smoke report",
    })

    config = _load(_LOCAL_AI / "config" / "profile_validation_report.json")
    checks.append({
        "id": "config",
        "ok": bool(config.get("success")) if config else None,
        "detail": f"issues={config.get('issue_count')}" if config else "no config report",
    })

    prof = _load(_LOCAL_AI / "config" / "profile_governance_report.json")
    checks.append({
        "id": "profile_governance",
        "ok": (prof.get("decision") == "pass") if prof else None,
        "detail": f"decision={prof.get('decision')}" if prof else "no profile report",
    })

    routing = _load(_LOCAL_AI / "routing" / "reports" / "routing_governance_report.json")
    checks.append({
        "id": "routing_governance",
        "ok": (routing.get("verdict") == "pass") if routing else None,
        "detail": f"verdict={routing.get('verdict')}" if routing else "no routing audit",
    })

    regression = _load(_LOCAL_AI / "benchmark" / "reports" / "regression" / "regression_report.json")
    reg_verdict = regression.get("verdict") if regression else None
    checks.append({
        "id": "regression",
        # A standing 'regression' verdict blocks; pass/improvement/manual_review/no_reference do not.
        "ok": (reg_verdict != "regression") if regression else None,
        "detail": f"latest verdict={reg_verdict}" if regression else "no regression report",
    })

    reliability = _load(_LOCAL_AI / "benchmark" / "reports" / "reliability" / "eval_reliability.json")
    rel_verdict = reliability.get("verdict") if reliability else None
    checks.append({
        "id": "reliability",
        "ok": (rel_verdict == "reliable") if reliability else None,
        "detail": f"verdict={rel_verdict} stamp_rate={reliability.get('stamp_rate')}" if reliability else "no reliability report",
    })

    gov = _load(_LOCAL_AI / "system" / "reports" / "governance_status.json")
    awaiting = gov.get("awaiting_manual_review", []) if gov else []
    checks.append({
        "id": "awaiting_review",
        "ok": (len(awaiting) == 0) if gov else None,
        "detail": f"{len(awaiting)} awaiting manual review" if gov else "no governance status",
    })

    goldens = _load(_LOCAL_AI / "goldens" / "approved_goldens.json")
    human = goldens.get("human_verified_count") if goldens else None
    checks.append({
        "id": "human_goldens",
        "ok": (human is not None and human > 0) if goldens else None,
        "detail": f"human_verified={human}" if goldens else "no goldens registry",
    })

    return checks


def evaluate(policy: dict[str, Any] | None = None) -> dict[str, Any]:
    pol = {**DEFAULT_DEPLOY_POLICY, **(policy or {})}
    checks = _checks()
    by_id = {c["id"]: c for c in checks}

    blocked_by: list[str] = []
    warnings: list[str] = []

    for cid in pol["block_on"]:
        c = by_id.get(cid)
        if c and c["ok"] is False:
            blocked_by.append(f"{cid}: {c['detail']}")
        elif c and c["ok"] is None:
            # A blocking check that has never run is itself a block (unknown == unsafe).
            blocked_by.append(f"{cid}: not run ({c['detail']})")

    for cid in pol["warn_on"]:
        c = by_id.get(cid)
        if c and c["ok"] is not True:
            warnings.append(f"{cid}: {c['detail']}")

    if blocked_by:
        verdict = "blocked"
    elif warnings:
        verdict = "ready_with_warnings"
    else:
        verdict = "ready"

    return {
        "timestamp": _now(),
        "verdict": verdict,
        "policy": pol,
        "blocked_by": blocked_by,
        "warnings": warnings,
        "checks": checks,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append
    a("# Deployment Readiness Report")
    a("")
    a(f"Generated: `{report['timestamp']}`  ")
    a(f"Verdict: **{report['verdict']}**")
    a("")
    a("## Checks")
    a("")
    a("| Check | Result | Detail |")
    a("|-------|:------:|--------|")
    for c in report["checks"]:
        mark = "PASS" if c["ok"] is True else ("FAIL" if c["ok"] is False else "—")
        a(f"| `{c['id']}` | {mark} | {c['detail']} |")
    a("")
    a("## Blocked By")
    a("")
    if report["blocked_by"]:
        for b in report["blocked_by"]:
            a(f"- {b}")
    else:
        a("Nothing blocking.")
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
    a("- Read-only aggregation of governance reports; runs no models, changes no state.")
    a("- A blocking check that has never run counts as a block (unknown == unsafe).")
    a("- `blocked` exits non-zero so deployment automation can refuse to ship.")
    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any]) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _OUT_MD.write_text(_markdown(report), encoding="utf-8")


def _self_test() -> bool:
    report = evaluate()
    required = {"verdict", "checks", "blocked_by", "warnings"}
    ok = not (required - set(report)) and report["verdict"] in {"ready", "ready_with_warnings", "blocked"}
    print(f"[deploy-gate] self-test {'ok' if ok else 'FAIL'}: verdict={report.get('verdict')}")
    return ok


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deployment readiness gate")
    parser.add_argument("--self-test", action="store_true", help="Read-only aggregation self-test")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.self_test:
        ok = _self_test()
        print(f"[deploy-gate] self-test {'PASS' if ok else 'FAIL'}")
        sys.exit(0 if ok else 1)

    report = evaluate()
    write_reports(report)
    print(f"[deploy-gate] verdict={report['verdict']} "
          f"blocked_by={len(report['blocked_by'])} warnings={len(report['warnings'])}")
    for b in report["blocked_by"]:
        print(f"  BLOCK: {b}")
    print(f"[deploy-gate] report >> {_OUT_MD}")
    sys.exit(1 if report["verdict"] == "blocked" else 0)


if __name__ == "__main__":
    main()
