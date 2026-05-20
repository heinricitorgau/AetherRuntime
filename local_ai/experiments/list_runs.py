#!/usr/bin/env python3
"""List registered local_ai experiment runs."""
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


def _load_runs() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    if not REGISTRY_DIR.exists():
        return runs
    for path in REGISTRY_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("run_id", path.stem)
            data["_path"] = str(path)
            runs.append(data)
        except Exception as exc:
            runs.append(
                {
                    "run_id": path.stem,
                    "timestamp": "",
                    "run_type": "invalid",
                    "error": str(exc),
                    "_path": str(path),
                }
            )
    runs.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    return runs


def _fmt_score(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_accepted(run: dict[str, Any]) -> str:
    accepted = run.get("accepted")
    cases = run.get("cases_run") or run.get("tasks")
    if accepted is None:
        return "-"
    if cases:
        return f"{accepted}/{cases}"
    return str(accepted)


def main() -> None:
    parser = argparse.ArgumentParser(description="List local_ai experiment runs")
    parser.add_argument("--type", choices=["benchmark", "train", "compare_lora", "compare-lora"])
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    runs = _load_runs()
    run_type = args.type.replace("-", "_") if args.type else None
    if run_type:
        runs = [run for run in runs if run.get("run_type") == run_type]
    runs = runs[: max(args.limit, 0)]

    if not runs:
        print("No experiment runs registered.")
        print(f"Registry: {REGISTRY_DIR}")
        return

    print(f"Latest experiment runs ({len(runs)} shown)")
    print(f"{'timestamp':<22} {'type':<13} {'run_id':<34} {'avg':>6} {'accepted':>10}")
    print("-" * 91)
    for run in runs:
        print(
            f"{str(run.get('timestamp') or '-'):<22} "
            f"{str(run.get('run_type') or '-'):<13} "
            f"{str(run.get('run_id') or '-'):<34} "
            f"{_fmt_score(run.get('avg_score')):>6} "
            f"{_fmt_accepted(run):>10}"
        )


if __name__ == "__main__":
    main()
