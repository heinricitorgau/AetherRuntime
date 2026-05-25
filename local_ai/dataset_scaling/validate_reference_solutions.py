#!/usr/bin/env python3
"""Compile/runtime/semantic validation for generated reference solutions."""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_REPORT_DIR = _HERE / "reports"
_SOLUTIONS_PATH = _REPORT_DIR / "generated_solutions.jsonl"
_REPORT_JSON = _REPORT_DIR / "generated_solution_validation_report.json"
_REPORT_MD = _REPORT_DIR / "generated_solution_validation_report.md"
_ACCEPTED = _REPORT_DIR / "accepted_generated_solutions.jsonl"
_REJECTED = _REPORT_DIR / "rejected_generated_solutions.jsonl"
_BENCH_DIR = _LOCAL_AI / "benchmark"

if str(_BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(_BENCH_DIR))

from _bench_common import (  # type: ignore[import-not-found]
    check_output_tokens,
    check_structure,
    compile_code,
    find_compiler,
    run_exe,
    semantic_check,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if raw:
                rows.append(json.loads(raw))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _structure_check(code: str) -> dict[str, Any]:
    result = check_structure(code)
    issues = list(result.get("issues", []))
    if not re.search(r"\bint\s+main\s*\(", code):
        issues.append("missing int main")
    if "#include" not in code:
        issues.append("missing #include")
    if code.count("{") != code.count("}"):
        issues.append("unbalanced braces")
    return {
        "passed": not issues and bool(result.get("ok")),
        "issues": issues,
        "raw": result,
    }


def _failure_reasons(
    structure: dict[str, Any],
    compile_r: dict[str, Any],
    runtime_r: dict[str, Any] | None,
    token_r: dict[str, Any] | None,
    semantic_r: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    if not structure.get("passed"):
        reasons.append("structure_error")
    if not compile_r.get("ok"):
        msg = str(compile_r.get("message", ""))
        reasons.append("timeout" if "timeout" in msg.lower() else "compile_error")
    if runtime_r:
        if runtime_r.get("timed_out"):
            reasons.append("timeout")
        elif not runtime_r.get("ok") or (token_r and token_r.get("missing")):
            reasons.append("runtime_mismatch")
    if not semantic_r.get("passed", True):
        reasons.append("semantic_error")
    return sorted(set(reasons))


def validate_solution(row: dict[str, Any], compiler: str | None, work_dir: Path) -> dict[str, Any]:
    code = str(row.get("reference_solution") or "")
    structure = _structure_check(code)

    compile_r: dict[str, Any] = {"ok": False, "message": "compiler not found", "errors": [], "warnings": [], "exe": None}
    runtime_r: dict[str, Any] | None = None
    token_r: dict[str, Any] | None = None
    semantic_r = semantic_check(code) if code.strip() else {
        "passed": False,
        "warnings": [],
        "errors": ["empty reference_solution"],
        "risk_score": 1.0,
    }

    if compiler and code.strip() and structure.get("passed"):
        compile_r = compile_code(code, str(row.get("id", "generated")), work_dir, compiler)
        if compile_r.get("ok") and compile_r.get("exe"):
            timeout = int((row.get("checker_rules") or {}).get("timeout_seconds", 5))
            runtime_r = run_exe(str(compile_r["exe"]), str(row.get("sample_input", "")), timeout=timeout)
            token_r = check_output_tokens(
                str(runtime_r.get("output", "")),
                list(row.get("expected_output_contains", [])),
            )

    reasons = _failure_reasons(structure, compile_r, runtime_r, token_r, semantic_r)
    accepted = not reasons
    return {
        "id": row.get("id"),
        "topic": row.get("topic"),
        "difficulty": row.get("difficulty"),
        "accepted": accepted,
        "failure_reasons": reasons,
        "structure": structure,
        "compile": compile_r,
        "runtime": runtime_r,
        "output_tokens": token_r,
        "semantic": semantic_r,
        "generation_model": row.get("generation_model"),
        "generation_error": row.get("generation_error"),
    }


def validate_all(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    rows = _read_jsonl(path)
    compiler = find_compiler()
    accepted_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="generated_solution_validate_") as tmp_dir:
        tmp = Path(tmp_dir)
        for row in rows:
            result = validate_solution(row, compiler, tmp)
            results.append(result)
            if result["accepted"]:
                accepted_rows.append({**row, "validation": result})
            else:
                rejected_rows.append({**row, "validation": result, "rejection_reasons": result["failure_reasons"]})

    reason_counts = Counter(reason for result in results for reason in result["failure_reasons"])
    topic_counts = Counter(str(row.get("topic")) for row in rows)
    accepted_topic_counts = Counter(str(row.get("topic")) for row in accepted_rows)
    report = {
        "timestamp": _now(),
        "input": str(path),
        "compiler": compiler,
        "records": len(rows),
        "accepted": len(accepted_rows),
        "rejected": len(rejected_rows),
        "topic_counts": dict(sorted(topic_counts.items())),
        "accepted_topic_counts": dict(sorted(accepted_topic_counts.items())),
        "rejection_reason_counts": dict(sorted(reason_counts.items())),
        "results": results,
    }
    return report, accepted_rows, rejected_rows


def _markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append
    a("# Generated Solution Validation Report")
    a("")
    a(f"Generated: `{report['timestamp']}`")
    a(f"Input: `{report['input']}`")
    a(f"Compiler: `{report.get('compiler') or 'NOT FOUND'}`")
    a("")
    a("## Summary")
    a("")
    a(f"- Records: {report['records']}")
    a(f"- Accepted: {report['accepted']}")
    a(f"- Rejected: {report['rejected']}")
    a("")
    a("## Rejection Reasons")
    a("")
    if report["rejection_reason_counts"]:
        for reason, count in report["rejection_reason_counts"].items():
            a(f"- {reason}: {count}")
    else:
        a("No rejected records.")
    a("")
    a("## Per Record")
    a("")
    a("| ID | Topic | Accepted | Reasons |")
    a("|----|-------|:--------:|---------|")
    for result in report["results"]:
        reasons = ", ".join(result["failure_reasons"]) if result["failure_reasons"] else "-"
        a(f"| {result['id']} | {result['topic']} | {result['accepted']} | {reasons} |")
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], accepted_rows: list[dict[str, Any]], rejected_rows: list[dict[str, Any]]) -> None:
    _write_json(_REPORT_JSON, report)
    _REPORT_MD.write_text(_markdown(report), encoding="utf-8")
    _write_jsonl(_ACCEPTED, accepted_rows)
    _write_jsonl(_REJECTED, rejected_rows)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate generated reference C solutions")
    parser.add_argument("--input", default=str(_SOLUTIONS_PATH))
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    path = Path(args.input)
    if not path.exists():
        print(f"[validate-solutions] ERROR: missing input {path}", file=sys.stderr)
        sys.exit(1)
    report, accepted_rows, rejected_rows = validate_all(path)
    write_outputs(report, accepted_rows, rejected_rows)
    print(
        f"[validate-solutions] accepted={report['accepted']} "
        f"rejected={report['rejected']} records={report['records']}"
    )
    print(f"[validate-solutions] report >> {_REPORT_MD}")


if __name__ == "__main__":
    main()
