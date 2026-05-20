#!/usr/bin/env python3
"""Show metadata for one registered local_ai experiment run."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from local_ai.experiments.register_run import REGISTRY_DIR


def _load_registry() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    if not REGISTRY_DIR.exists():
        return runs
    for path in REGISTRY_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("run_id", path.stem)
            data["_path"] = str(path)
            runs.append(data)
        except Exception:
            continue
    runs.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    return runs


def _find_run(run_id: str) -> dict[str, Any] | None:
    path = REGISTRY_DIR / f"{run_id}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("run_id", path.stem)
        data["_path"] = str(path)
        return data
    for run in _load_registry():
        if run.get("run_id") == run_id:
            return run
    return None


def _print_mapping(title: str, value: Any) -> None:
    if not value:
        return
    print(f"\n{title}")
    if isinstance(value, dict):
        for key, item in value.items():
            print(f"  {key}: {item}")
    elif isinstance(value, list):
        for item in value:
            print(f"  - {item}")
    else:
        print(f"  {value}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Show one local_ai experiment run")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    run = _find_run(args.run_id)
    if run is None:
        print(f"Experiment run not found: {args.run_id}", file=sys.stderr)
        print(f"Registry: {REGISTRY_DIR}", file=sys.stderr)
        sys.exit(1)

    print(f"Run: {run.get('run_id')}")
    print(f"Type: {run.get('run_type')}")
    print(f"Timestamp: {run.get('timestamp')}")
    print(f"Registry file: {run.get('_path')}")

    _print_mapping("Linked reports", run.get("linked_reports"))
    _print_mapping("Linked config profiles", run.get("config_profiles"))

    print("\nFull metadata")
    print(json.dumps({k: v for k, v in run.items() if k != "_path"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
