#!/usr/bin/env python3
"""Index generated reports across local_ai subsystems."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_REPORT_DIR = _HERE / "reports"
_OUT_JSON = _REPORT_DIR / "report_index.json"
_OUT_MD = _REPORT_DIR / "report_index.md"

REPORT_ROOTS = [
    ("benchmark", _LOCAL_AI / "benchmark" / "reports", ["benchmark"]),
    ("sft", _LOCAL_AI / "sft" / "reports", ["sft", "adapter"]),
    ("routing", _LOCAL_AI / "routing" / "reports", ["routing"]),
    ("release_snapshot", _LOCAL_AI / "release" / "snapshots", ["release", "snapshot"]),
    ("experiment", _LOCAL_AI / "experiments" / "reports", ["experiment"]),
    ("dataset_scaling", _LOCAL_AI / "dataset_scaling" / "reports", ["dataset_scaling", "synthetic"]),
    ("system", _REPORT_DIR, ["system"]),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _tag_for(path: Path, base_tags: list[str]) -> list[str]:
    tags = set(base_tags)
    name = path.name.lower()
    if "regression" in name:
        tags.add("regression")
    if "promotion" in name:
        tags.add("promotion")
    if "routing" in name:
        tags.add("routing")
    if "benchmark" in name:
        tags.add("benchmark")
    if "summary" in name:
        tags.add("summary")
    if "snapshot" in name:
        tags.add("snapshot")
    return sorted(tags)


def build_index() -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    for report_type, root, tags in REPORT_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".jsonl"}:
                continue
            stat = path.stat()
            reports.append(
                {
                    "report_type": report_type,
                    "latest_modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
                    "path": str(path),
                    "tags": _tag_for(path, tags),
                    "size_bytes": stat.st_size,
                }
            )
    reports.sort(key=lambda row: row["latest_modified"], reverse=True)
    return {"timestamp": _now(), "count": len(reports), "reports": reports}


def _markdown(index: dict[str, Any]) -> str:
    lines = [
        "# Report Index",
        "",
        f"Generated: `{index['timestamp']}`",
        f"Reports indexed: {index['count']}",
        "",
        "| Type | Modified | Path | Tags |",
        "|------|----------|------|------|",
    ]
    for row in index["reports"]:
        lines.append(
            f"| {row['report_type']} | {row['latest_modified']} | `{row['path']}` | {', '.join(row['tags'])} |"
        )
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
        print(f"[report-index] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"[report-index] reports={index['count']} >> {_OUT_MD}")


if __name__ == "__main__":
    main()
