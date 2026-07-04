#!/usr/bin/env python3
"""Fast pre-commit smoke validation for local_ai infrastructure.

This smoke test does not run models, train adapters, call the proxy, require
CUDA/torch, modify benchmark scoring, or promote adapters.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_REPO_ROOT = _LOCAL_AI.parent
_REPORT_DIR = _HERE / "reports"
_OUT_JSON = _REPORT_DIR / "smoke_test_report.json"
_OUT_MD = _REPORT_DIR / "smoke_test_report.md"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_step(name: str, args: list[str]) -> dict[str, Any]:
    started = _now()
    cmd = [sys.executable, *args]
    proc = subprocess.run(
        cmd,
        cwd=str(_REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "name": name,
        "kind": "command",
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "returncode": proc.returncode,
        "command": cmd,
        "started_at": started,
        "finished_at": _now(),
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _check_exists(name: str, path: Path) -> dict[str, Any]:
    exists = path.exists()
    return {
        "name": name,
        "kind": "file_exists",
        "status": "PASS" if exists else "FAIL",
        "path": str(path),
        "exists": exists,
        "checked_at": _now(),
    }


def run_smoke() -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    steps.append(_run_step("config validation", ["local_ai/config/validate_profiles.py"]))
    steps.append(_run_step("config loader self-test", ["local_ai/shared/config_loader.py", "--self-test"]))
    steps.append(_run_step("system index", ["local_ai/system/system_index.py"]))
    steps.append(_run_step("report index", ["local_ai/system/build_report_index.py"]))
    steps.append(_run_step("architecture map", ["local_ai/system/build_architecture_map.py"]))
    steps.append(_run_step("adapter registry summary", ["local_ai/sft/list_adapters.py"]))
    steps.append(_run_step("routing classifier self-test", ["local_ai/routing/task_classifier.py", "--self-test"]))
    steps.append(_run_step("regression detector self-test", ["local_ai/benchmark/detect_regression.py", "--self-test"]))
    steps.append(_run_step("benchmark trend self-test", ["local_ai/benchmark/benchmark_trend.py", "--self-test"]))
    steps.append(_run_step("eval reliability self-test", ["local_ai/benchmark/eval_reliability.py", "--self-test"]))
    steps.append(_run_step("profile governance self-test", ["local_ai/config/govern_profiles.py", "--self-test"]))
    steps.append(_run_step("goldens governance self-test", ["local_ai/goldens/promote_goldens.py", "--self-test"]))
    steps.append(_run_step("routing governance self-test", ["local_ai/routing/audit_routing.py", "--self-test"]))
    steps.append(_run_step("deploy gate self-test", ["local_ai/release/deploy_gate.py", "--self-test"]))
    steps.append(_run_step("corpus import self-test", ["local_ai/corpus/import_exam.py", "--self-test"]))
    steps.append(_run_step("corpus review-workflow self-test", ["local_ai/corpus/review_workflow.py", "--self-test"]))
    steps.append(_run_step("corpus integrity validation", ["local_ai/corpus/validate_corpus.py"]))
    steps.append(_run_step("governance status self-test", ["local_ai/system/governance_status.py", "--self-test"]))
    steps.append(
        _run_step(
            "routing plan dry evaluation",
            ["local_ai/routing/evaluate_routing.py", "--benchmark", "c_exam_2025_strict_seeded"],
        )
    )
    steps.append(
        _check_exists(
            "generated dataset promotion report exists",
            _LOCAL_AI / "dataset_scaling" / "reports" / "generated_dataset_promotion_report.json",
        )
    )
    steps.append(
        _check_exists(
            "synthetic training summary exists",
            _LOCAL_AI / "sft" / "reports" / "synthetic_training_summary.json",
        )
    )

    failed = [step for step in steps if step["status"] != "PASS"]
    return {
        "timestamp": _now(),
        "status": "PASS" if not failed else "FAIL",
        "passed": len(steps) - len(failed),
        "failed": len(failed),
        "steps": steps,
        "guardrails": {
            "runs_models": False,
            "trains_adapters": False,
            "calls_proxy": False,
            "requires_cuda_or_torch": False,
            "modifies_benchmark_scoring": False,
            "promotes_adapters": False,
        },
    }


def _markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append
    a("# Smoke Test Report")
    a("")
    a(f"Generated: `{report['timestamp']}`")
    a(f"Status: **{report['status']}**")
    a(f"Passed: {report['passed']}")
    a(f"Failed: {report['failed']}")
    a("")
    a("## Steps")
    a("")
    a("| Step | Status | Detail |")
    a("|------|--------|--------|")
    for step in report["steps"]:
        if step["kind"] == "command":
            detail = " ".join(step["command"])
            if step["status"] != "PASS":
                tail = (step.get("stderr_tail") or step.get("stdout_tail") or "").strip().replace("\n", " ")
                if tail:
                    detail = f"{detail} :: {tail[:180]}"
        else:
            detail = step["path"]
        a(f"| {step['name']} | {step['status']} | `{detail}` |")
    a("")
    a("## Guardrails")
    a("")
    for key, value in report["guardrails"].items():
        a(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any]) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _OUT_MD.write_text(_markdown(report), encoding="utf-8")


def main() -> None:
    report = run_smoke()
    write_reports(report)
    print(f"[smoke-test] status={report['status']} passed={report['passed']} failed={report['failed']}")
    print(f"[smoke-test] report >> {_OUT_MD}")
    if report["status"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
