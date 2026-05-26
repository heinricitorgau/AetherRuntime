#!/usr/bin/env python3
"""Build a portfolio demo index from existing reports."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_REPORT_DIR = _HERE / "reports"
_OUT_MD = _REPORT_DIR / "demo_index.md"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _latest_file(path: Path, pattern: str) -> Path | None:
    if not path.exists():
        return None
    files = [p for p in path.glob(pattern) if p.is_file()]
    return max(files, key=lambda p: p.stat().st_mtime, default=None)


def _latest_snapshot() -> Path | None:
    root = _LOCAL_AI / "release" / "snapshots"
    if not root.exists():
        return None
    dirs = [p for p in root.iterdir() if p.is_dir()]
    return max(dirs, key=lambda p: p.stat().st_mtime, default=None)


def build_demo_index() -> str:
    system_index = _load_json(_LOCAL_AI / "system" / "reports" / "system_index.json", {})
    latest_snapshot = _latest_snapshot()
    latest_benchmark = system_index.get("latest_benchmark")
    latest_routing = system_index.get("latest_routing_report") or str(
        _latest_file(_LOCAL_AI / "routing" / "reports", "*_routing_plan.md") or ""
    )
    latest_smoke = _LOCAL_AI / "system" / "reports" / "smoke_test_report.md"
    latest_adapter = _LOCAL_AI / "sft" / "reports" / "adapter_registry_summary.md"
    architecture = _LOCAL_AI / "system" / "reports" / "architecture_map.md"

    lines = [
        "# Demo Index",
        "",
        f"Generated: `{_now()}`",
        "",
        "## Latest Demo Artifacts",
        "",
        f"- Latest snapshot: `{latest_snapshot / 'snapshot.md' if latest_snapshot else 'missing'}`",
        f"- Latest smoke test: `{latest_smoke}`",
        f"- Latest routing report: `{latest_routing}`",
        f"- Latest benchmark: `{latest_benchmark}`",
        f"- Latest adapter registry: `{latest_adapter}`",
        f"- Architecture map: `{architecture}`",
        "",
        "## Suggested Demo Order",
        "",
        "1. Run `python local_ai/cli.py smoke`.",
        "2. Open `local_ai/system/reports/system_index.md`.",
        "3. Run `python local_ai/cli.py adapters`.",
        "4. Run `python local_ai/cli.py routing --benchmark c_exam_2025_strict_seeded`.",
        "5. Open the latest release snapshot.",
        "6. Open the architecture map and report index.",
        "",
        "## Stable Status",
        "",
        f"- Config status: `{system_index.get('config_status', 'unknown')}`",
        f"- Routing enabled: `{system_index.get('routing_enabled', 'unknown')}`",
        f"- Synthetic training status: `{system_index.get('synthetic_training_status', 'unknown')}`",
        f"- Safe adapters: `{len(system_index.get('safe_adapters', []))}`",
        f"- Rejected adapters: `{len(system_index.get('rejected_adapters', []))}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    try:
        _REPORT_DIR.mkdir(parents=True, exist_ok=True)
        _OUT_MD.write_text(build_demo_index(), encoding="utf-8")
    except Exception as exc:
        print(f"[demo-index] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"[demo-index] report >> {_OUT_MD}")


if __name__ == "__main__":
    main()
