#!/usr/bin/env python3
"""Validate config profile registries and cross-references."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from local_ai.shared.paths import CONFIG_DIR, resolve_repo_path
from local_ai.shared.report_utils import write_json_report, write_text_report

CONFIG_NAMES = (
    "models",
    "datasets",
    "benchmarks",
    "training_jobs",
    "runtime_profiles",
)

MODEL_REQUIRED = {"hf_model", "ollama_model", "dtype", "max_tokens", "temperature"}
TRAINING_JOB_REQUIRED = {"model", "dataset", "output_dir", "epochs"}
RUNTIME_REQUIRED = {
    "ollama_timeout_seconds",
    "first_token_timeout_seconds",
    "proxy_port",
    "ollama_port",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(name: str, issues: list[dict[str, str]]) -> dict[str, Any]:
    path = CONFIG_DIR / f"{name}.json"
    if not path.exists():
        issues.append({
            "type": "missing_config",
            "config": name,
            "message": f"config file not found: {path}",
        })
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append({
            "type": "invalid_json",
            "config": name,
            "message": f"invalid JSON in {path}: {exc}",
        })
        return {}
    if not isinstance(data, dict):
        issues.append({
            "type": "invalid_config_shape",
            "config": name,
            "message": f"config file must contain an object: {path}",
        })
        return {}
    return data


def _require_keys(
    registry: str,
    profile_name: str,
    profile: Any,
    required: set[str],
    issues: list[dict[str, str]],
) -> None:
    if not isinstance(profile, dict):
        issues.append({
            "type": "invalid_profile_shape",
            "registry": registry,
            "profile": profile_name,
            "message": f"{registry}.{profile_name} must be an object",
        })
        return
    missing = sorted(required - set(profile))
    for key in missing:
        issues.append({
            "type": "missing_key",
            "registry": registry,
            "profile": profile_name,
            "key": key,
            "message": f"{registry}.{profile_name} is missing required key: {key}",
        })


def _check_reference(
    registry: str,
    profile_name: str,
    key: str,
    target_registry: str,
    target_profiles: dict[str, Any],
    issues: list[dict[str, str]],
    value: Any,
) -> None:
    if value is None:
        return
    ref = str(value)
    if ref not in target_profiles:
        issues.append({
            "type": "missing_reference",
            "registry": registry,
            "profile": profile_name,
            "key": key,
            "reference": ref,
            "target_registry": target_registry,
            "message": (
                f"{registry}.{profile_name}.{key} references missing "
                f"{target_registry} profile: {ref}"
            ),
        })


def _validate_dataset_paths(
    datasets: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    for name, profile in datasets.items():
        if not isinstance(profile, dict):
            continue
        raw_path = profile.get("path")
        if raw_path is None:
            issues.append({
                "type": "missing_key",
                "registry": "datasets",
                "profile": name,
                "key": "path",
                "message": f"datasets.{name} is missing required key: path",
            })
            continue
        resolved = resolve_repo_path(raw_path)
        if not resolved.exists():
            issues.append({
                "type": "missing_file",
                "registry": "datasets",
                "profile": name,
                "path": str(resolved),
                "message": f"datasets.{name}.path does not exist: {resolved}",
            })


def validate_profiles() -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    configs = {name: _load_json(name, issues) for name in CONFIG_NAMES}

    models = configs["models"]
    datasets = configs["datasets"]
    benchmarks = configs["benchmarks"]
    training_jobs = configs["training_jobs"]
    runtime_profiles = configs["runtime_profiles"]

    for name, profile in models.items():
        _require_keys("models", name, profile, MODEL_REQUIRED, issues)

    for name, profile in training_jobs.items():
        _require_keys("training_jobs", name, profile, TRAINING_JOB_REQUIRED, issues)

    for name, profile in runtime_profiles.items():
        _require_keys("runtime_profiles", name, profile, RUNTIME_REQUIRED, issues)

    _validate_dataset_paths(datasets, issues)

    for name, profile in benchmarks.items():
        if not isinstance(profile, dict):
            _require_keys("benchmarks", name, profile, set(), issues)
            continue
        _check_reference(
            "benchmarks", name, "model", "models", models, issues, profile.get("model")
        )
        _check_reference(
            "benchmarks",
            name,
            "dataset",
            "datasets",
            datasets,
            issues,
            profile.get("dataset"),
        )

    for name, profile in training_jobs.items():
        if not isinstance(profile, dict):
            continue
        _check_reference(
            "training_jobs", name, "model", "models", models, issues, profile.get("model")
        )
        _check_reference(
            "training_jobs",
            name,
            "dataset",
            "datasets",
            datasets,
            issues,
            profile.get("dataset"),
        )

    return {
        "timestamp": _now(),
        "success": not issues,
        "checked": {
            "models": len(models),
            "datasets": len(datasets),
            "benchmarks": len(benchmarks),
            "training_jobs": len(training_jobs),
            "runtime_profiles": len(runtime_profiles),
        },
        "issue_count": len(issues),
        "issues": issues,
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Config Profile Validation Report")
    lines.append("")
    lines.append(f"Generated: `{report['timestamp']}`")
    lines.append("")
    lines.append(f"Status: **{'PASS' if report['success'] else 'FAIL'}**")
    lines.append("")
    lines.append("## Checked Registries")
    lines.append("")
    lines.append("| Registry | Count |")
    lines.append("|----------|------:|")
    for key, count in report["checked"].items():
        lines.append(f"| `{key}` | {count} |")
    lines.append("")
    lines.append("## Issues")
    lines.append("")
    if not report["issues"]:
        lines.append("No issues found.")
    else:
        lines.append("| Type | Location | Message |")
        lines.append("|------|----------|---------|")
        for issue in report["issues"]:
            location = issue.get("registry") or issue.get("config", "")
            profile = issue.get("profile")
            if profile:
                location = f"{location}.{profile}"
            message = str(issue.get("message", "")).replace("|", "\\|")
            lines.append(f"| `{issue.get('type', '')}` | `{location}` | {message} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    report = validate_profiles()
    json_path = CONFIG_DIR / "profile_validation_report.json"
    md_path = CONFIG_DIR / "profile_validation_report.md"
    write_json_report(json_path, report)
    write_text_report(md_path, _markdown_report(report))

    if report["success"]:
        print("Config profile validation: PASS")
        print(f"Report: {md_path}")
        return

    print("Config profile validation: FAIL")
    for issue in report["issues"]:
        print(f"- {issue['message']}")
    print(f"Report: {md_path}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
