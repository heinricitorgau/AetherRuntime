#!/usr/bin/env python3
"""Prompt / profile governance (roadmap #5).

Prompt profiles silently shape every benchmark result, so they need the same
governance discipline as datasets, adapters, and models. This read-only gate
validates the prompt/benchmark profiles and records an approved-profiles
registry. It does not run models or change scoring.

Checks per prompt profile (`config/benchmark_profiles.json`):
  - references a `prompt_file` that exists under `benchmark/prompts/`
  - that prompt file is non-empty
  - declares deterministic generation (temperature == 0) — else flagged as a
    reliability risk (ties into the evaluation-reliability analyzer)

Cross-reference: every benchmark in `config/benchmarks.json` must reference a
known prompt profile.

Outputs:
  config/profile_governance_report.json
  config/profile_governance_report.md
  config/approved_profiles.json            (registry)

Usage:
  python local_ai/config/govern_profiles.py
  python local_ai/config/govern_profiles.py --self-test
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
_PROMPTS_DIR = _LOCAL_AI / "benchmark" / "prompts"

_BENCHMARK_PROFILES = _HERE / "benchmark_profiles.json"
_BENCHMARKS = _HERE / "benchmarks.json"
_REPORT_JSON = _HERE / "profile_governance_report.json"
_REPORT_MD = _HERE / "profile_governance_report.md"
_APPROVED = _HERE / "approved_profiles.json"

_DETERMINISTIC_TEMPERATURE = 0.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def evaluate() -> dict[str, Any]:
    profiles_cfg = _load(_BENCHMARK_PROFILES)
    benchmarks_cfg = _load(_BENCHMARKS)

    profiles: list[dict[str, Any]] = []
    issues: list[str] = []
    warnings: list[str] = []

    for name, prof in profiles_cfg.items():
        if name.startswith("_") or not isinstance(prof, dict):
            continue
        prompt_file = prof.get("prompt_file")
        temperature = prof.get("temperature")
        prompt_path = _PROMPTS_DIR / prompt_file if prompt_file else None

        file_ok = bool(prompt_path and prompt_path.exists())
        nonempty = bool(file_ok and prompt_path.read_text(encoding="utf-8").strip())
        deterministic = temperature is not None and float(temperature) == _DETERMINISTIC_TEMPERATURE

        status = "approved" if (file_ok and nonempty) else "invalid"
        if not file_ok:
            issues.append(f"{name}: prompt_file missing ({prompt_file})")
        elif not nonempty:
            issues.append(f"{name}: prompt_file is empty ({prompt_file})")
        if file_ok and not deterministic:
            warnings.append(f"{name}: temperature={temperature} is non-deterministic")

        profiles.append(
            {
                "name": name,
                "prompt_file": prompt_file,
                "prompt_file_exists": file_ok,
                "non_empty": nonempty,
                "deterministic": deterministic,
                "temperature": temperature,
                "max_tokens": prof.get("max_tokens"),
                "status": status,
            }
        )

    profile_names = {p["name"] for p in profiles}
    dangling: list[str] = []
    for bname, bench in benchmarks_cfg.items():
        if not isinstance(bench, dict):
            continue
        ref = bench.get("prompt_profile")
        if ref and ref not in profile_names:
            dangling.append(f"{bname}: references unknown prompt_profile '{ref}'")
    issues.extend(dangling)

    approved = [p for p in profiles if p["status"] == "approved"]
    decision = "pass" if not issues else "fail"

    return {
        "timestamp": _now(),
        "decision": decision,
        "profiles_total": len(profiles),
        "profiles_approved": len(approved),
        "issues": issues,
        "warnings": warnings,
        "profiles": profiles,
    }


def _write_registry(report: dict[str, Any]) -> None:
    registry = {
        "updated_at": report["timestamp"],
        "decision": report["decision"],
        "profiles": [
            {
                "name": p["name"],
                "prompt_file": p["prompt_file"],
                "status": p["status"],
                "deterministic": p["deterministic"],
            }
            for p in report["profiles"]
        ],
    }
    _APPROVED.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append
    a("# Prompt / Profile Governance Report")
    a("")
    a(f"Generated: `{report['timestamp']}`  ")
    a(f"Decision: **{report['decision']}**  ")
    a(f"Approved: {report['profiles_approved']}/{report['profiles_total']}")
    a("")
    a("## Profiles")
    a("")
    a("| Profile | Prompt file | Exists | Deterministic | Status |")
    a("|---------|-------------|:------:|:-------------:|--------|")
    for p in report["profiles"]:
        a(f"| `{p['name']}` | `{p['prompt_file']}` | {p['prompt_file_exists']} "
          f"| {p['deterministic']} | {p['status']} |")
    a("")
    a("## Issues")
    a("")
    if report["issues"]:
        for i in report["issues"]:
            a(f"- {i}")
    else:
        a("None.")
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
    a("- Read-only validation; runs no models, changes no scoring or prompts.")
    a("- Non-deterministic temperatures are flagged, not silently accepted.")
    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any]) -> None:
    _REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _REPORT_MD.write_text(_markdown(report), encoding="utf-8")
    _write_registry(report)


def _self_test() -> bool:
    report = evaluate()
    required = {"decision", "profiles", "issues", "warnings"}
    if required - set(report):
        print(f"[govern-profiles] self-test FAIL: missing {required - set(report)}")
        return False
    print(f"[govern-profiles] self-test ok: decision={report['decision']} "
          f"approved={report['profiles_approved']}/{report['profiles_total']}")
    return True


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prompt/profile governance gate")
    parser.add_argument("--self-test", action="store_true", help="Read-only validation self-test")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.self_test:
        ok = _self_test()
        print(f"[govern-profiles] self-test {'PASS' if ok else 'FAIL'}")
        sys.exit(0 if ok else 1)

    report = evaluate()
    write_reports(report)
    print(f"[govern-profiles] decision={report['decision']} "
          f"approved={report['profiles_approved']}/{report['profiles_total']}")
    print(f"[govern-profiles] report >> {_REPORT_MD}")
    sys.exit(0 if report["decision"] == "pass" else 1)


if __name__ == "__main__":
    main()
