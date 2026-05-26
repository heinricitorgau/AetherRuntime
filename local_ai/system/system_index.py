#!/usr/bin/env python3
"""Build a high-level index of local_ai system status."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_REPO_ROOT = _LOCAL_AI.parent
_REPORT_DIR = _HERE / "reports"
_OUT_JSON = _REPORT_DIR / "system_index.json"
_OUT_MD = _REPORT_DIR / "system_index.md"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _count_files(path: Path, pattern: str = "*") -> int:
    if not path.exists():
        return 0
    return sum(1 for p in path.glob(pattern) if p.is_file())


def _latest(paths: list[Path]) -> Path | None:
    existing = [p for p in paths if p.exists()]
    if not existing:
        return None
    return max(existing, key=lambda p: p.stat().st_mtime)


def _latest_in(path: Path, pattern: str = "*", recursive: bool = False) -> Path | None:
    if not path.exists():
        return None
    iterator = path.rglob(pattern) if recursive else path.glob(pattern)
    files = [p for p in iterator if p.is_file()]
    return _latest(files)


def _latest_snapshot() -> dict[str, Any]:
    root = _LOCAL_AI / "release" / "snapshots"
    if not root.exists():
        return {"count": 0, "latest": None}
    dirs = [p for p in root.iterdir() if p.is_dir()]
    latest = max(dirs, key=lambda p: p.stat().st_mtime, default=None)
    return {"count": len(dirs), "latest": str(latest) if latest else None}


def _adapter_counts() -> dict[str, Any]:
    adapter_dir = _LOCAL_AI / "sft" / "adapters"
    safe = _load_json(adapter_dir / "safe_adapters.json", {"adapters": []}).get("adapters", [])
    rejected = _load_json(adapter_dir / "rejected_adapters.json", {"adapters": []}).get("adapters", [])
    ablation = _load_json(adapter_dir / "ablation_adapters.json", {"adapters": []}).get("adapters", [])
    promoted = _load_json(adapter_dir / "promoted_adapters.json", {"adapters": []}).get("adapters", [])
    default = _load_json(adapter_dir / "default_adapter.json", {"active": None})
    has_default = bool(default.get("active"))
    total = len(safe) + len(rejected) + len(ablation) + len(promoted) + (1 if has_default else 0)
    return {
        "total": total,
        "safe_count": len(safe),
        "rejected_count": len(rejected),
        "ablation_count": len(ablation),
        "promoted_count": len(promoted) + (1 if has_default else 0),
        "safe_adapters": [row.get("adapter_path") for row in safe],
        "rejected_adapters": [row.get("adapter_path") for row in rejected],
        "default_selected": has_default,
    }


def build_index() -> dict[str, Any]:
    config_report = _LOCAL_AI / "config" / "profile_validation_report.json"
    config_data = _load_json(config_report, {})
    if config_data.get("success") is True or config_data.get("status") == "PASS":
        config_status = "PASS"
    elif config_report.exists():
        config_status = "FAIL" if config_data.get("issue_count", 0) else "available"
    else:
        config_status = "missing"
    doctor_exists = (_LOCAL_AI / "doctor.py").exists()
    latest_benchmark = _latest_in(_LOCAL_AI / "benchmark" / "reports", "*.json", recursive=True)
    latest_routing = _latest_in(_LOCAL_AI / "routing" / "reports", "*_routing_plan.md")
    synthetic = _load_json(_LOCAL_AI / "sft" / "reports" / "synthetic_training_summary.json", {})
    snapshots = _latest_snapshot()
    adapters = _adapter_counts()

    return {
        "timestamp": _now(),
        "config_status": config_status,
        "doctor_status": "available" if doctor_exists else "missing",
        "benchmark_status": "available" if (_LOCAL_AI / "benchmark").exists() else "missing",
        "experiment_count": _count_files(_LOCAL_AI / "experiments" / "registry", "*.json"),
        "adapter_count": adapters["total"],
        "safe_adapters": adapters["safe_adapters"],
        "rejected_adapters": adapters["rejected_adapters"],
        "adapter_registry": adapters,
        "snapshots_count": snapshots["count"],
        "routing_enabled": (_LOCAL_AI / "routing" / "routing_policy.json").exists(),
        "synthetic_training_status": synthetic.get("status", "unknown"),
        "latest_release_snapshot": snapshots["latest"],
        "latest_benchmark": str(latest_benchmark) if latest_benchmark and latest_benchmark.exists() else None,
        "latest_routing_report": str(latest_routing) if latest_routing else None,
    }


def _markdown(index: dict[str, Any]) -> str:
    lines = [
        "# System Index",
        "",
        f"Generated: `{index['timestamp']}`",
        "",
        "## Status",
        "",
        f"- Config status: `{index['config_status']}`",
        f"- Doctor status: `{index['doctor_status']}`",
        f"- Benchmark status: `{index['benchmark_status']}`",
        f"- Experiment count: {index['experiment_count']}",
        f"- Adapter count: {index['adapter_count']}",
        f"- Safe adapters: {len(index['safe_adapters'])}",
        f"- Rejected adapters: {len(index['rejected_adapters'])}",
        f"- Snapshots count: {index['snapshots_count']}",
        f"- Routing enabled: {index['routing_enabled']}",
        f"- Synthetic training status: `{index['synthetic_training_status']}`",
        "",
        "## Latest Artifacts",
        "",
        f"- Latest release snapshot: `{index['latest_release_snapshot']}`",
        f"- Latest benchmark: `{index['latest_benchmark']}`",
        f"- Latest routing report: `{index['latest_routing_report']}`",
    ]
    return "\n".join(lines) + "\n"


def write_reports(index: dict[str, Any]) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _OUT_JSON.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _OUT_MD.write_text(_markdown(index), encoding="utf-8")


def main() -> None:
    try:
        index = build_index()
        write_reports(index)
    except Exception as exc:
        print(f"[system-index] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"[system-index] report >> {_OUT_MD}")


if __name__ == "__main__":
    main()
