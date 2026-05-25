#!/usr/bin/env python3
"""Validate generated synthetic C task specifications."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPORT_DIR = _HERE / "reports"
_DEFAULT_INPUT = _REPORT_DIR / "generated_tasks.jsonl"
_REPORT_JSON = _REPORT_DIR / "generated_task_validation_report.json"
_REPORT_MD = _REPORT_DIR / "generated_task_validation_report.md"

VALID_TOPICS = {"series_calculation", "pattern_generation", "geometry", "game_simulation"}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}
REQUIRED_FIELDS = {
    "id",
    "topic",
    "difficulty",
    "prompt",
    "required_features",
    "sample_input",
    "expected_output_contains",
    "checker_rules",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                rows.append({"_line": line_no, "_json_error": str(exc)})
                continue
            obj["_line"] = line_no
            rows.append(obj)
    return rows


def _validate_record(row: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if row.get("_json_error"):
        return [f"invalid JSON: {row['_json_error']}"]

    missing = sorted(field for field in REQUIRED_FIELDS if field not in row)
    for field in missing:
        issues.append(f"missing field: {field}")

    if not str(row.get("id", "")).strip():
        issues.append("id empty")
    if row.get("topic") not in VALID_TOPICS:
        issues.append(f"invalid topic: {row.get('topic')}")
    if row.get("difficulty") not in VALID_DIFFICULTIES:
        issues.append(f"invalid difficulty: {row.get('difficulty')}")
    if not str(row.get("prompt", "")).strip():
        issues.append("prompt empty")
    if not str(row.get("sample_input", "")).strip():
        issues.append("sample_input empty")

    required_features = row.get("required_features")
    if not isinstance(required_features, list) or not required_features:
        issues.append("required_features must be a non-empty list")

    expected = row.get("expected_output_contains")
    if not isinstance(expected, list) or not expected:
        issues.append("expected_output_contains must be a non-empty list")

    checker = row.get("checker_rules")
    if not isinstance(checker, dict) or not checker:
        issues.append("checker_rules must be a non-empty object")
    else:
        if "keywords" not in checker or not isinstance(checker.get("keywords"), list) or not checker.get("keywords"):
            issues.append("checker_rules.keywords must be a non-empty list")
        if "compile_required" not in checker:
            issues.append("checker_rules.compile_required missing")
        if "runtime_required" not in checker:
            issues.append("checker_rules.runtime_required missing")

    return issues


def validate(path: Path) -> dict[str, Any]:
    rows = _read_jsonl(path)
    issues: list[dict[str, Any]] = []
    seen_ids: dict[str, int] = {}
    seen_prompts: dict[str, int] = {}

    for row in rows:
        rid = str(row.get("id", ""))
        prompt = str(row.get("prompt", "")).strip()
        row_issues = _validate_record(row)

        if rid:
            if rid in seen_ids:
                row_issues.append(f"duplicate id also seen on line {seen_ids[rid]}")
            else:
                seen_ids[rid] = int(row.get("_line", 0))
        if prompt:
            if prompt in seen_prompts:
                row_issues.append(f"duplicate prompt also seen on line {seen_prompts[prompt]}")
            else:
                seen_prompts[prompt] = int(row.get("_line", 0))

        if row_issues:
            issues.append(
                {
                    "line": row.get("_line"),
                    "id": row.get("id"),
                    "issues": row_issues,
                }
            )

    topic_counts = Counter(str(row.get("topic")) for row in rows if row.get("topic") in VALID_TOPICS)
    difficulty_counts = Counter(str(row.get("difficulty")) for row in rows if row.get("difficulty") in VALID_DIFFICULTIES)
    balanced = len(set(topic_counts.values())) == 1 and set(topic_counts) == VALID_TOPICS
    report = {
        "timestamp": _now(),
        "input": str(path),
        "status": "PASS" if not issues else "FAIL",
        "records": len(rows),
        "topic_counts": dict(sorted(topic_counts.items())),
        "difficulty_counts": dict(sorted(difficulty_counts.items())),
        "topic_balanced": balanced,
        "unique_ids": len(seen_ids),
        "unique_prompts": len(seen_prompts),
        "duplicate_ids": len(seen_ids) != len([row for row in rows if row.get("id")]),
        "duplicate_prompts": len(seen_prompts) != len([row for row in rows if str(row.get("prompt", "")).strip()]),
        "issues": issues,
    }
    if not balanced:
        report["status"] = "FAIL"
        report["issues"].append(
            {
                "line": None,
                "id": None,
                "issues": ["topics are not balanced across valid topic set"],
            }
        )
    return report


def _markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append
    a("# Generated Task Validation Report")
    a("")
    a(f"Generated: `{report['timestamp']}`")
    a(f"Input: `{report['input']}`")
    a(f"Status: **{report['status']}**")
    a("")
    a("## Summary")
    a("")
    a(f"- Records: {report['records']}")
    a(f"- Unique IDs: {report['unique_ids']}")
    a(f"- Unique prompts: {report['unique_prompts']}")
    a(f"- Topic balanced: {report['topic_balanced']}")
    a("")
    a("## Topic Counts")
    a("")
    a("| Topic | Count |")
    a("|-------|------:|")
    for topic, count in report["topic_counts"].items():
        a(f"| {topic} | {count} |")
    a("")
    a("## Issues")
    a("")
    if report["issues"]:
        for issue in report["issues"]:
            a(f"- line={issue.get('line')} id={issue.get('id')}: {', '.join(issue['issues'])}")
    else:
        a("No issues found.")
    return "\n".join(lines)


def write_reports(report: dict[str, Any]) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _REPORT_MD.write_text(_markdown(report), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate generated task specs")
    parser.add_argument("--input", default=str(_DEFAULT_INPUT))
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    path = Path(args.input)
    if not path.exists():
        print(f"[validate-generated-tasks] ERROR: missing input {path}", file=sys.stderr)
        sys.exit(1)
    report = validate(path)
    write_reports(report)
    print(f"[validate-generated-tasks] status={report['status']} records={report['records']}")
    print(f"[validate-generated-tasks] report >> {_REPORT_MD}")
    if report["status"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
