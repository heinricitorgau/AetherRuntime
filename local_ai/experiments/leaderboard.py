#!/usr/bin/env python3
"""Build a leaderboard from local_ai experiment registry metadata."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from local_ai.experiments.register_run import REGISTRY_DIR, REPORTS_DIR


LEADERBOARD_TYPES = {"benchmark", "compare_lora"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_runs() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    if not REGISTRY_DIR.exists():
        return runs
    for path in REGISTRY_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        data.setdefault("run_id", path.stem)
        data["_path"] = str(path)
        runs.append(data)
    return runs


def _profile_value(run: dict[str, Any], key: str) -> Any:
    value = run.get(key)
    if value:
        return value
    profiles = run.get("config_profiles")
    if isinstance(profiles, dict):
        if key == "model_profile":
            return profiles.get("model")
        if key == "benchmark_profile":
            return profiles.get("benchmark")
    return value


def _as_float(value: Any, default: float = -1.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _accepted_sort_value(run: dict[str, Any]) -> float:
    return _as_float(run.get("accepted"), default=-1.0)


def _filter_runs(args: argparse.Namespace) -> list[dict[str, Any]]:
    run_type = args.type.replace("-", "_") if args.type else None
    runs = [
        run for run in _load_runs()
        if run.get("run_type") in LEADERBOARD_TYPES
    ]
    if run_type:
        runs = [run for run in runs if run.get("run_type") == run_type]
    if args.benchmark:
        runs = [
            run for run in runs
            if _profile_value(run, "benchmark_profile") == args.benchmark
        ]
    runs.sort(
        key=lambda run: (
            _as_float(run.get("avg_score"), default=-1.0),
            _accepted_sort_value(run),
            str(run.get("timestamp") or ""),
        ),
        reverse=True,
    )
    return runs[: max(args.limit, 0)]


def _row(run: dict[str, Any], rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "run_id": run.get("run_id"),
        "run_type": run.get("run_type"),
        "model_profile": _profile_value(run, "model_profile"),
        "benchmark_profile": _profile_value(run, "benchmark_profile"),
        "adapter_path": run.get("adapter_path"),
        "accepted": run.get("accepted"),
        "cases_run": run.get("cases_run") or run.get("tasks"),
        "avg_score": run.get("avg_score"),
        "compile_rate": run.get("compile_rate"),
        "runtime_rate": run.get("runtime_rate"),
        "semantic_rate": run.get("semantic_rate"),
        "keyword_rate": run.get("keyword_rate"),
        "timeout_rate": run.get("timeout_rate"),
        "timestamp": run.get("timestamp"),
        "registry_file": run.get("_path"),
    }


def _build_report(args: argparse.Namespace) -> dict[str, Any]:
    rows = [_row(run, i) for i, run in enumerate(_filter_runs(args), 1)]
    return {
        "timestamp": _now(),
        "filters": {
            "type": args.type,
            "benchmark": args.benchmark,
            "limit": args.limit,
        },
        "runs": rows,
    }


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _fmt_rate(value: Any) -> str:
    try:
        if value is None:
            return "-"
        return f"{float(value):.0%}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_accepted(row: dict[str, Any]) -> str:
    accepted = row.get("accepted")
    cases = row.get("cases_run")
    if accepted is None:
        return "-"
    if cases:
        return f"{accepted}/{cases}"
    return str(accepted)


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Experiment Leaderboard",
        "",
        f"**Generated**: {report['timestamp']}",
        "",
        "| Rank | Run ID | Type | Model | Benchmark | Adapter | Accepted | Avg | Compile | Runtime | Timeout | Timestamp |",
        "|-----:|--------|------|-------|-----------|---------|---------:|----:|--------:|--------:|--------:|-----------|",
    ]
    for row in report["runs"]:
        lines.append(
            "| "
            f"{row['rank']} | "
            f"`{_fmt(row.get('run_id'))}` | "
            f"{_fmt(row.get('run_type'))} | "
            f"{_fmt(row.get('model_profile'))} | "
            f"{_fmt(row.get('benchmark_profile'))} | "
            f"{_fmt(row.get('adapter_path'))} | "
            f"{_fmt_accepted(row)} | "
            f"{_fmt(row.get('avg_score'))} | "
            f"{_fmt_rate(row.get('compile_rate'))} | "
            f"{_fmt_rate(row.get('runtime_rate'))} | "
            f"{_fmt_rate(row.get('timeout_rate'))} | "
            f"{_fmt(row.get('timestamp'))} |"
        )
    if not report["runs"]:
        lines.append("| - | No matching runs | - | - | - | - | - | - | - | - | - | - |")
    return "\n".join(lines)


def _write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / "leaderboard.json"
    md_path = REPORTS_DIR / "leaderboard.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an experiment leaderboard")
    parser.add_argument("--type", choices=["benchmark", "compare_lora", "compare-lora"])
    parser.add_argument("--benchmark", help="Benchmark profile name")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    report = _build_report(args)
    json_path, md_path = _write_outputs(report)

    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(_markdown(report))
    print(f"\nReport JSON: {json_path}")
    print(f"Report MD:   {md_path}")


if __name__ == "__main__":
    main()
