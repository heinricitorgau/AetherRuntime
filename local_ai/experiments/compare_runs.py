#!/usr/bin/env python3
"""Compare two registered local_ai experiment runs."""
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


METRICS: dict[str, str] = {
    "accepted": "higher",
    "avg_score": "higher",
    "compile_rate": "higher",
    "runtime_rate": "higher",
    "semantic_rate": "higher",
    "keyword_rate": "higher",
    "timeout_rate": "lower",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_id(value: str) -> str:
    safe = []
    for ch in value:
        if ch.isalnum() or ch in ("-", "_", "."):
            safe.append(ch)
        else:
            safe.append("_")
    return "".join(safe).strip("._") or "run"


def _load_run(run_id: str) -> dict[str, Any]:
    path = REGISTRY_DIR / f"{run_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"run not found: {run_id} ({path})")
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("run_id", run_id)
    data["_path"] = str(path)
    return data


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compare_metric(name: str, base: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    base_value = _as_float(base.get(name))
    new_value = _as_float(new.get(name))
    direction = METRICS[name]
    changed = base.get(name) != new.get(name)

    result: dict[str, Any] = {
        "base": base.get(name),
        "new": new.get(name),
        "delta": None,
        "direction": direction,
        "change": "unavailable",
        "changed": changed,
    }
    if base_value is None or new_value is None:
        return result

    delta = round(new_value - base_value, 6)
    result["delta"] = delta
    result["changed"] = abs(delta) > 1e-9
    if abs(delta) <= 1e-9:
        result["change"] = "no_change"
    elif (direction == "higher" and delta > 0) or (direction == "lower" and delta < 0):
        result["change"] = "improvement"
    else:
        result["change"] = "regression"
    return result


def compare_runs(base: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    metrics = {name: _compare_metric(name, base, new) for name in METRICS}
    changed_fields = [
        name for name, result in metrics.items()
        if result.get("changed") and result.get("change") != "unavailable"
    ]
    improved_fields = [
        name for name, result in metrics.items()
        if result.get("change") == "improvement"
    ]
    regressed_fields = [
        name for name, result in metrics.items()
        if result.get("change") == "regression"
    ]
    unavailable_fields = [
        name for name, result in metrics.items()
        if result.get("change") == "unavailable"
    ]

    if regressed_fields:
        verdict = "regression"
    elif improved_fields:
        verdict = "improvement"
    else:
        verdict = "no_change"

    return {
        "timestamp": _now(),
        "base_run_id": base.get("run_id"),
        "new_run_id": new.get("run_id"),
        "verdict": verdict,
        "changed_fields": changed_fields,
        "improved_fields": improved_fields,
        "regressed_fields": regressed_fields,
        "unavailable_fields": unavailable_fields,
        "metrics": metrics,
        "base": {
            "run_type": base.get("run_type"),
            "model_profile": base.get("model_profile"),
            "benchmark_profile": base.get("benchmark_profile"),
            "adapter_path": base.get("adapter_path"),
            "timestamp": base.get("timestamp"),
            "registry_file": base.get("_path"),
        },
        "new": {
            "run_type": new.get("run_type"),
            "model_profile": new.get("model_profile"),
            "benchmark_profile": new.get("benchmark_profile"),
            "adapter_path": new.get("adapter_path"),
            "timestamp": new.get("timestamp"),
            "registry_file": new.get("_path"),
        },
    }


def _fmt_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Experiment Run Comparison",
        "",
        f"**Base**: `{report['base_run_id']}`  ",
        f"**New**: `{report['new_run_id']}`  ",
        f"**Verdict**: **{report['verdict']}**  ",
        f"**Generated**: {report['timestamp']}",
        "",
        "## Metric Deltas",
        "",
        "| Metric | Base | New | Delta | Direction | Change |",
        "|--------|-----:|----:|------:|-----------|--------|",
    ]
    for name, result in report["metrics"].items():
        lines.append(
            "| "
            f"{name} | "
            f"{_fmt_value(result.get('base'))} | "
            f"{_fmt_value(result.get('new'))} | "
            f"{_fmt_value(result.get('delta'))} | "
            f"{result.get('direction')} | "
            f"{result.get('change')} |"
        )
    lines.extend(
        [
            "",
            "## Changed Fields",
            "",
            ", ".join(report["changed_fields"]) if report["changed_fields"] else "None",
            "",
            "## Regression Fields",
            "",
            ", ".join(report["regressed_fields"]) if report["regressed_fields"] else "None",
            "",
            "## Improvement Fields",
            "",
            ", ".join(report["improved_fields"]) if report["improved_fields"] else "None",
            "",
        ]
    )
    return "\n".join(lines)


def _write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"compare_{_safe_id(str(report['base_run_id']))}_vs_{_safe_id(str(report['new_run_id']))}"
    json_path = REPORTS_DIR / f"{stem}.json"
    md_path = REPORTS_DIR / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two experiment registry runs")
    parser.add_argument("--base", required=True, help="Base run_id")
    parser.add_argument("--new", required=True, help="New run_id")
    args = parser.parse_args()

    try:
        base = _load_run(args.base)
        new = _load_run(args.new)
    except FileNotFoundError as exc:
        print(f"[compare_runs] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    report = compare_runs(base, new)
    json_path, md_path = _write_outputs(report)
    print(f"Experiment comparison: {report['verdict']}")
    print(f"Changed fields: {', '.join(report['changed_fields']) or 'none'}")
    print(f"Report JSON: {json_path}")
    print(f"Report MD:   {md_path}")


if __name__ == "__main__":
    main()
