#!/usr/bin/env python3
"""Generate a routing plan for a benchmark without running models."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_REPO_ROOT = _LOCAL_AI.parent
_REPORT_DIR = _HERE / "reports"
_REPORT_JSON = _REPORT_DIR / "routing_plan.json"
_REPORT_MD = _REPORT_DIR / "routing_plan.md"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_LOCAL_AI / "benchmark") not in sys.path:
    sys.path.insert(0, str(_LOCAL_AI / "benchmark"))

from local_ai.shared.config_loader import load_benchmark_profile, load_dataset_profile  # noqa: E402
from benchmark_cases import load_tasks  # type: ignore  # noqa: E402

try:
    from .adapter_router import AdapterRouter
except ImportError:  # pragma: no cover
    from adapter_router import AdapterRouter


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_name(value: str) -> str:
    cleaned = []
    for char in value:
        if char.isalnum() or char in {"_", "-"}:
            cleaned.append(char)
        else:
            cleaned.append("_")
    return "".join(cleaned).strip("_") or "benchmark"


def _load_benchmark_tasks(benchmark_name: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    benchmark = load_benchmark_profile(benchmark_name)
    dataset = load_dataset_profile(str(benchmark["dataset"]))
    tasks = load_tasks(source=str(dataset["path"]))
    return benchmark, tasks


def evaluate(benchmark_name: str) -> dict[str, Any]:
    benchmark, tasks = _load_benchmark_tasks(benchmark_name)
    router = AdapterRouter()
    decisions = [router.route_task(task) for task in tasks]
    selected_counts = Counter(row["selected"] for row in decisions)
    topic_counts = Counter(row["detected_topic"] for row in decisions)
    selected_by_topic: dict[str, Counter[str]] = {}
    selected_by_adapter: Counter[str] = Counter()
    for row in decisions:
        topic = str(row["detected_topic"])
        selected = str(row["selected"])
        selected_by_topic.setdefault(topic, Counter())[selected] += 1
        adapter = str(row.get("selected_adapter") or "base")
        selected_by_adapter[adapter] += 1

    router_summary = router.summary()
    counts = router_summary["adapter_registry_counts"]
    return {
        "timestamp": _now(),
        "benchmark": benchmark_name,
        "benchmark_profile": benchmark,
        "tasks": len(tasks),
        "routing_summary": {
            "selected_counts": dict(sorted(selected_counts.items())),
            "topic_counts": dict(sorted(topic_counts.items())),
            "selected_base_count": selected_counts.get("base", 0),
            "selected_adapter_count": selected_counts.get("adapter", 0),
            "selected_by_topic": {
                topic: dict(sorted(counter.items()))
                for topic, counter in sorted(selected_by_topic.items())
            },
            "selected_by_adapter": dict(sorted(selected_by_adapter.items())),
            "rejected_adapter_count": counts.get("rejected", 0),
            "ablation_adapter_count": counts.get("ablation", 0),
            "safe_adapter_count": counts.get("safe", 0),
            "promoted_adapter_count": counts.get("promoted", 0),
            "usable_adapters": router_summary["usable_adapters"],
            "blocked_adapters": router_summary["blocked_adapters"],
        },
        "decisions": decisions,
        "side_effects": "routing_plan_only_no_model_execution",
    }


def _markdown(report: dict[str, Any]) -> str:
    summary = report["routing_summary"]
    lines: list[str] = []
    a = lines.append
    a("# Routing Plan")
    a("")
    a(f"Generated: `{report['timestamp']}`")
    a(f"Benchmark: `{report['benchmark']}`")
    a(f"Total tasks: {report['tasks']}")
    a("")
    a("## Summary")
    a("")
    a(f"- Benchmark: `{report['benchmark']}`")
    a(f"- Total tasks: {report['tasks']}")
    a(f"- Selected base count: {summary['selected_base_count']}")
    a(f"- Selected adapter count: {summary['selected_adapter_count']}")
    a(f"- Selected by topic: `{summary['selected_by_topic']}`")
    a(f"- Selected by adapter: `{summary['selected_by_adapter']}`")
    a(f"- Topic counts: `{summary['topic_counts']}`")
    a(f"- Rejected adapter count: {summary['rejected_adapter_count']}")
    a(f"- Ablation adapter count: {summary['ablation_adapter_count']}")
    a(f"- Safe adapter count: {summary['safe_adapter_count']}")
    a(f"- Promoted adapter count: {summary['promoted_adapter_count']}")
    a("")
    a("## Decisions")
    a("")
    a("| Task ID | Topic | Selected | Model Path | Adapter Status | Fallback Reason |")
    a("|---------|-------|----------|------------|----------------|-----------------|")
    for row in report["decisions"]:
        a(
            f"| {row.get('task_id')} | {row.get('detected_topic')} | {row.get('selected')} | "
            f"{row.get('selected_model_path')} | {row.get('selected_adapter_status') or ''} | "
            f"{row.get('fallback_reason') or ''} |"
        )
    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any]) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{_safe_name(str(report['benchmark']))}_routing_plan"
    specific_json = _REPORT_DIR / f"{stem}.json"
    specific_md = _REPORT_DIR / f"{stem}.md"
    json_text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    md_text = _markdown(report)
    specific_json.write_text(json_text, encoding="utf-8")
    specific_md.write_text(md_text, encoding="utf-8")
    _REPORT_JSON.write_text(json_text, encoding="utf-8")
    _REPORT_MD.write_text(md_text, encoding="utf-8")
    report["_written_reports"] = {
        "specific_json": str(specific_json),
        "specific_md": str(specific_md),
        "latest_json": str(_REPORT_JSON),
        "latest_md": str(_REPORT_MD),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate task-specific adapter routing plan")
    parser.add_argument("--benchmark", required=True, help="Benchmark profile name")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        report = evaluate(args.benchmark)
    except Exception as exc:
        print(f"[evaluate-routing] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    write_reports(report)
    print(
        "[evaluate-routing] "
        f"benchmark={report['benchmark']} tasks={report['tasks']} "
        f"selected={report['routing_summary']['selected_counts']}"
    )
    written = report.get("_written_reports", {})
    print(f"[evaluate-routing] report >> {written.get('specific_md', _REPORT_MD)}")
    print(f"[evaluate-routing] latest >> {_REPORT_MD}")


if __name__ == "__main__":
    main()
