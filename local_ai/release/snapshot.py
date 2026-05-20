#!/usr/bin/env python3
"""Create a read-only release snapshot from existing local_ai reports."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI_ROOT = _HERE.parent
_REPO_ROOT = _LOCAL_AI_ROOT.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


SNAPSHOT_ROOT = _HERE / "snapshots"
CONFIG_REPORT = _LOCAL_AI_ROOT / "config" / "profile_validation_report.json"
DOCTOR_REPORT = _LOCAL_AI_ROOT / "reports" / "doctor_report.json"
GOLDEN_BASELINE = _LOCAL_AI_ROOT / "benchmark" / "golden" / "golden_baseline.json"
SFT_READINESS = _LOCAL_AI_ROOT / "training_quality" / "reports" / "sft_readiness_report.json"
LEADERBOARD = _LOCAL_AI_ROOT / "experiments" / "reports" / "leaderboard.json"
REGISTRY_DIR = _LOCAL_AI_ROOT / "experiments" / "registry"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_name(value: str) -> str:
    safe = []
    for ch in value:
        if ch.isalnum() or ch in ("-", "_", "."):
            safe.append(ch)
        else:
            safe.append("_")
    return "".join(safe).strip("._") or "release"


def _load_json(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"WARN missing report: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        warnings.append(f"WARN could not read {path}: {exc}")
        return {}


def _write_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _git_commit() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=3,
        )
        if completed.returncode == 0:
            return completed.stdout.strip() or None
    except Exception:
        return None
    return None


def _cuda_info() -> tuple[bool | None, str | None]:
    try:
        import torch  # type: ignore[import-not-found]

        available = bool(torch.cuda.is_available())
        if available:
            return True, str(torch.cuda.get_device_name(0))
        return False, None
    except Exception:
        return None, None


def _registry_summary(warnings: list[str]) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    if not REGISTRY_DIR.exists():
        warnings.append(f"WARN missing experiment registry: {REGISTRY_DIR}")
        return {"experiment_count": 0, "by_type": {}, "latest_runs": []}
    for path in REGISTRY_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("run_id", path.stem)
            runs.append(data)
        except Exception as exc:
            warnings.append(f"WARN could not read registry entry {path}: {exc}")
    runs.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    by_type: dict[str, int] = {}
    for run in runs:
        run_type = str(run.get("run_type") or "unknown")
        by_type[run_type] = by_type.get(run_type, 0) + 1
    return {
        "experiment_count": len(runs),
        "by_type": by_type,
        "latest_runs": [
            {
                "run_id": run.get("run_id"),
                "timestamp": run.get("timestamp"),
                "run_type": run.get("run_type"),
                "avg_score": run.get("avg_score"),
                "accepted": run.get("accepted"),
                "benchmark_profile": run.get("benchmark_profile"),
                "model_profile": run.get("model_profile"),
                "adapter_path": run.get("adapter_path"),
            }
            for run in runs[:10]
        ],
    }


def _config_summary(config_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "PASS" if config_report.get("success") else "WARN",
        "timestamp": config_report.get("timestamp"),
        "checked": config_report.get("checked", {}),
        "issue_count": config_report.get("issue_count"),
        "issues": config_report.get("issues", []),
    }


def _benchmark_summary(golden: dict[str, Any], leaderboard: dict[str, Any]) -> dict[str, Any]:
    top = (leaderboard.get("runs") or [None])[0]
    return {
        "golden_baseline": {
            "run_id": golden.get("run_id"),
            "model": golden.get("model"),
            "task_count": golden.get("task_count"),
            "accepted": golden.get("accepted_count"),
            "avg_score": golden.get("avg_score"),
            "compile_pass_rate": golden.get("compile_pass_rate"),
            "runtime_pass_rate": golden.get("runtime_pass_rate"),
            "semantic_pass_rate": golden.get("semantic_pass_rate"),
            "keyword_pass_rate": golden.get("keyword_pass_rate"),
            "timeout_rate": golden.get("timeout_rate"),
            "created_at": golden.get("created_at"),
        },
        "latest_leaderboard_top": top,
    }


def _sft_summary(readiness: dict[str, Any]) -> dict[str, Any]:
    return {
        "ready_for_sft": readiness.get("ready_for_sft"),
        "timestamp": readiness.get("timestamp"),
        "dataset_passed": readiness.get("dataset_checks", {}).get("passed"),
        "semantic_passed": readiness.get("semantic_checks", {}).get("passed"),
        "benchmark_passed": readiness.get("benchmark_checks", {}).get("passed"),
        "reproducibility_passed": readiness.get("reproducibility_checks", {}).get("passed"),
        "documentation_passed": readiness.get("documentation_checks", {}).get("passed"),
    }


def _doctor_status(doctor: dict[str, Any]) -> str:
    if not doctor:
        return "WARN"
    return str(doctor.get("status") or ("PASS" if doctor.get("success") else "FAIL"))


def _known_limitations(warnings: list[str], doctor: dict[str, Any], sft: dict[str, Any]) -> list[str]:
    limitations = list(warnings)
    if doctor and _doctor_status(doctor) != "PASS":
        limitations.append(f"Doctor status is {_doctor_status(doctor)}.")
    if sft and sft.get("ready_for_sft") is not True:
        limitations.append("SFT readiness is not currently PASS; check reproducibility gate.")
    if not limitations:
        limitations.append("No missing reports detected in this snapshot.")
    return limitations


def _snapshot_json(
    release_name: str,
    config: dict[str, Any],
    doctor: dict[str, Any],
    golden: dict[str, Any],
    sft: dict[str, Any],
    leaderboard: dict[str, Any],
    registry: dict[str, Any],
    limitations: list[str],
) -> dict[str, Any]:
    cuda_available, gpu_name = _cuda_info()
    top = (leaderboard.get("runs") or [None])[0]
    return {
        "release_name": release_name,
        "timestamp": _now(),
        "git_commit": _git_commit(),
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "cuda_available": cuda_available,
        "gpu_name": gpu_name,
        "config_validation_status": "PASS" if config.get("success") else "WARN",
        "doctor_status": _doctor_status(doctor),
        "ready_for_sft": sft.get("ready_for_sft"),
        "golden_baseline_run_id": golden.get("run_id"),
        "golden_avg_score": golden.get("avg_score"),
        "golden_accepted": golden.get("accepted_count"),
        "latest_leaderboard_top": top,
        "experiment_count": registry.get("experiment_count", 0),
        "known_limitations": limitations,
    }


def _snapshot_markdown(snapshot: dict[str, Any], summaries: dict[str, Any]) -> str:
    top = snapshot.get("latest_leaderboard_top") or {}
    limitations = snapshot.get("known_limitations") or []
    lines = [
        f"# {snapshot['release_name']}",
        "",
        f"Generated: {snapshot['timestamp']}  ",
        f"Git commit: {snapshot.get('git_commit') or 'unknown'}  ",
        f"Python: {snapshot.get('python_version')}  ",
        f"CUDA: {snapshot.get('cuda_available')}  ",
        f"GPU: {snapshot.get('gpu_name') or 'unknown'}",
        "",
        "## What This Release Contains",
        "",
        "- Config-driven model, dataset, benchmark, runtime, and training profiles",
        "- Profile validation and startup doctor",
        "- Offline benchmark and golden baseline workflow",
        "- SFT readiness gate",
        "- LoRA training, inference, and base-vs-LoRA comparison",
        "- Experiment registry, run comparison, and leaderboard",
        "",
        "## Verified Capabilities",
        "",
        f"- Config validation: {snapshot.get('config_validation_status')}",
        f"- Doctor status: {snapshot.get('doctor_status')}",
        f"- Experiment registry entries: {snapshot.get('experiment_count')}",
        "",
        "## Current Best Benchmark",
        "",
        f"- Golden baseline run: {snapshot.get('golden_baseline_run_id')}",
        f"- Golden accepted: {snapshot.get('golden_accepted')}",
        f"- Golden average score: {snapshot.get('golden_avg_score')}",
        f"- Leaderboard top run: {top.get('run_id') if isinstance(top, dict) else 'none'}",
        f"- Leaderboard top avg score: {top.get('avg_score') if isinstance(top, dict) else 'none'}",
        "",
        "## SFT / LoRA Status",
        "",
        f"- READY_FOR_SFT: {snapshot.get('ready_for_sft')}",
        f"- SFT summary: {json.dumps(summaries.get('sft', {}), ensure_ascii=False)}",
        "",
        "## How To Reproduce",
        "",
        "```powershell",
        "python local_ai/config/validate_profiles.py",
        "python local_ai/doctor.py --benchmark c_exam_2025_strict_seeded",
        "python local_ai/run_profile.py benchmark --benchmark c_exam_2025_strict_seeded --dry-run",
        "python local_ai/experiments/leaderboard.py --limit 10 --format markdown",
        "python local_ai/release/snapshot.py --name local_ai_sft_infra_v1",
        "```",
        "",
        "## Known Limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in limitations)
    lines.extend(
        [
            "",
            "## Next Recommended Work",
            "",
            "- Resolve SFT reproducibility readiness warning",
            "- Register more benchmark and compare-lora runs for meaningful leaderboard ranking",
            "- Promote stable benchmark profiles into golden release candidates",
            "- Add release snapshot diffing once multiple snapshots exist",
            "",
        ]
    )
    return "\n".join(lines)


def create_snapshot(name: str) -> Path:
    release_name = _safe_name(name)
    snapshot_dir = SNAPSHOT_ROOT / release_name
    warnings: list[str] = []

    config = _load_json(CONFIG_REPORT, warnings)
    doctor = _load_json(DOCTOR_REPORT, warnings)
    golden = _load_json(GOLDEN_BASELINE, warnings)
    sft = _load_json(SFT_READINESS, warnings)
    leaderboard = _load_json(LEADERBOARD, warnings)
    registry = _registry_summary(warnings)
    limitations = _known_limitations(warnings, doctor, sft)

    summaries = {
        "config": _config_summary(config),
        "benchmark": _benchmark_summary(golden, leaderboard),
        "sft": _sft_summary(sft),
        "experiments": registry,
    }
    snapshot = _snapshot_json(
        release_name,
        config,
        doctor,
        golden,
        sft,
        leaderboard,
        registry,
        limitations,
    )

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    _write_json(snapshot_dir / "snapshot.json", snapshot)
    _write_json(snapshot_dir / "config_summary.json", summaries["config"])
    _write_json(snapshot_dir / "benchmark_summary.json", summaries["benchmark"])
    _write_json(snapshot_dir / "sft_summary.json", summaries["sft"])
    _write_json(snapshot_dir / "experiment_summary.json", summaries["experiments"])
    (snapshot_dir / "snapshot.md").write_text(
        _snapshot_markdown(snapshot, summaries),
        encoding="utf-8",
    )
    return snapshot_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a local_ai release snapshot")
    parser.add_argument("--name", required=True, help="Release snapshot name")
    args = parser.parse_args()

    snapshot_dir = create_snapshot(args.name)
    print(f"Release snapshot created: {snapshot_dir}")
    print(f"  snapshot.json -> {snapshot_dir / 'snapshot.json'}")
    print(f"  snapshot.md   -> {snapshot_dir / 'snapshot.md'}")


if __name__ == "__main__":
    main()
