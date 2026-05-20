#!/usr/bin/env python3
"""Register structured experiment metadata for local_ai runs."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from local_ai.shared.paths import LOCAL_AI_ROOT, REPO_ROOT


EXPERIMENTS_DIR = LOCAL_AI_ROOT / "experiments"
REGISTRY_DIR = EXPERIMENTS_DIR / "registry"
REPORTS_DIR = EXPERIMENTS_DIR / "reports"

RUN_FIELDS = [
    "run_id",
    "timestamp",
    "run_type",
    "model_profile",
    "benchmark_profile",
    "training_job",
    "adapter_path",
    "accepted",
    "avg_score",
    "compile_rate",
    "runtime_rate",
    "semantic_rate",
    "timeout_rate",
    "git_commit",
    "python_version",
    "cuda_available",
    "gpu_name",
]


def _now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _safe_id(value: str) -> str:
    safe = []
    for ch in value:
        if ch.isalnum() or ch in ("-", "_", "."):
            safe.append(ch)
        else:
            safe.append("_")
    return "".join(safe).strip("._") or "run"


def _unique_run_id(raw_id: str) -> str:
    base = _safe_id(raw_id)
    candidate = base
    suffix = 2
    while (REGISTRY_DIR / f"{candidate}.json").exists():
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def _git_commit() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(REPO_ROOT),
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


def _runtime_metadata() -> dict[str, Any]:
    cuda_available, gpu_name = _cuda_info()
    return {
        "git_commit": _git_commit(),
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "cuda_available": cuda_available,
        "gpu_name": gpu_name,
    }


def register_run(run_data: dict[str, Any]) -> dict[str, Any]:
    """Write one experiment registry JSON file and return its metadata."""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    run_type = str(run_data.get("run_type") or "run")
    timestamp = str(run_data.get("timestamp") or _now_iso())
    raw_run_id = str(run_data.get("run_id") or f"{run_type}_{_now_compact()}")
    run_id = _unique_run_id(raw_run_id)

    metadata: dict[str, Any] = {field: None for field in RUN_FIELDS}
    metadata.update(_runtime_metadata())
    metadata.update(_jsonable(run_data))
    metadata["run_id"] = run_id
    metadata["timestamp"] = timestamp
    metadata["run_type"] = run_type

    path = REGISTRY_DIR / f"{run_id}.json"
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return metadata


def main() -> None:
    print("register_run.py is a library module.")
    print("Import register_run(run_data) from pipeline scripts to record experiments.")


if __name__ == "__main__":
    main()
