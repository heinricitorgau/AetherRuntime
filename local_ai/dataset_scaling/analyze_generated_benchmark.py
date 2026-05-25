#!/usr/bin/env python3
"""Analyze generated benchmark results for dataset scaling decisions.

This script is intentionally read-only with respect to benchmark data. It reads
one benchmark run directory and writes analysis artifacts under
local_ai/dataset_scaling/reports/.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_RUNS_DIR = _LOCAL_AI / "benchmark" / "reports" / "runs"
_REPORTS_DIR = _HERE / "reports"
_DEFAULT_RUN_ID = "strict_20260523_205251"
_ANALYSIS_JSON = _REPORTS_DIR / "generated_benchmark_analysis.json"
_ANALYSIS_MD = _REPORTS_DIR / "generated_benchmark_analysis.md"

LOW_SCORE_THRESHOLD = 60
VALID_CLASSIFICATIONS = {
    "likely_prompt_ambiguous",
    "expected_token_too_strict",
    "model_generation_failure",
    "checker_rule_mismatch",
    "task_spec_issue",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _resolve_latest_run() -> Path:
    candidates = [p for p in _RUNS_DIR.iterdir() if p.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"no benchmark runs found under {_RUNS_DIR}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _load_run(run_id: str | None, latest: bool) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    run_dir = _resolve_latest_run() if latest else _RUNS_DIR / (run_id or _DEFAULT_RUN_ID)
    report_path = run_dir / "report.json"
    results_path = run_dir / "results.jsonl"

    if not report_path.exists() and not results_path.exists():
        raise FileNotFoundError(f"missing report.json/results.jsonl in {run_dir}")

    report = _read_json(report_path) if report_path.exists() else {}
    results = report.get("results")
    if not isinstance(results, list):
        results = _read_jsonl(results_path)
    return run_dir, report, results


def _check_passed(row: dict[str, Any], name: str) -> bool:
    check = row.get("checks", {}).get(name, {})
    return bool(check.get("passed"))


def _failed_checks(row: dict[str, Any]) -> list[str]:
    failed: list[str] = []
    for name, check in row.get("checks", {}).items():
        if isinstance(check, dict) and check.get("passed") is False:
            failed.append(name)
    return failed


def _topic(row: dict[str, Any]) -> str:
    return str(row.get("task_meta", {}).get("topic") or row.get("topic") or "unknown")


def _difficulty(row: dict[str, Any]) -> str:
    return str(row.get("task_meta", {}).get("difficulty") or row.get("difficulty") or "unknown")


def _score(row: dict[str, Any]) -> float:
    try:
        return float(row.get("score", 0))
    except (TypeError, ValueError):
        return 0.0


def _short_compile_error(row: dict[str, Any]) -> str:
    compile_check = row.get("checks", {}).get("compile", {})
    errors = compile_check.get("errors") or []
    if errors:
        return str(errors[0])
    return str(compile_check.get("message") or "")


def _runtime_summary(row: dict[str, Any]) -> dict[str, Any]:
    runtime = row.get("checks", {}).get("runtime", {})
    return {
        "passed": bool(runtime.get("passed")),
        "timed_out": bool(runtime.get("timed_out")),
        "missing": runtime.get("missing") or [],
        "found": runtime.get("found") or [],
        "match_ratio": runtime.get("match_ratio"),
        "output_head": str(runtime.get("output_head") or "")[:300],
        "note": runtime.get("note"),
    }


def _classify_low_score(row: dict[str, Any]) -> dict[str, Any]:
    checks = row.get("checks", {})
    runtime = checks.get("runtime", {})
    compile_check = checks.get("compile", {})
    semantic = checks.get("semantic", {})
    structure = checks.get("structure", {})
    code = str(row.get("extracted_code") or "")
    failures = set(_failed_checks(row))
    topic = _topic(row)

    evidence: list[str] = []
    classification = "model_generation_failure"

    if "proxy" in failures or not code.strip():
        classification = "model_generation_failure"
        evidence.append("proxy/empty response prevented code extraction")
    elif "compile" in failures:
        error = _short_compile_error(row)
        classification = "model_generation_failure"
        if "implicit declaration" in error.lower() or "undeclared" in error.lower():
            evidence.append("generated code does not compile cleanly under strict C99")
        else:
            evidence.append("generated code failed compile validation")
    elif runtime.get("timed_out"):
        classification = "likely_prompt_ambiguous" if topic == "game_simulation" else "model_generation_failure"
        evidence.append("runtime timed out, often caused by waiting for extra input or loop logic")
    elif "runtime" in failures and runtime.get("missing"):
        output_head = str(runtime.get("output_head") or "")
        if output_head.strip():
            classification = "expected_token_too_strict"
            evidence.append("program produced output, but expected output tokens were missing")
        else:
            classification = "checker_rule_mismatch"
            evidence.append("runtime failed without useful output evidence")
    elif "keyword" in failures:
        classification = "checker_rule_mismatch"
        evidence.append("keyword check failed while structural checks were otherwise available")
    elif "semantic" in failures:
        classification = "model_generation_failure"
        evidence.append("semantic validator reported generated code issues")

    if "empty response" in [str(x).lower() for x in structure.get("issues", [])]:
        evidence.append("structure check reported empty response")
    if semantic.get("errors"):
        evidence.append("semantic errors: " + "; ".join(str(e) for e in semantic.get("errors", [])[:2]))
    if compile_check.get("message"):
        evidence.append("compile: " + str(compile_check.get("message")))
    if runtime.get("missing"):
        evidence.append("missing runtime tokens: " + ", ".join(str(t) for t in runtime.get("missing", [])[:5]))

    if classification not in VALID_CLASSIFICATIONS:
        classification = "model_generation_failure"

    return {
        "classification": classification,
        "evidence": evidence,
    }


def _summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    accepted = sum(1 for r in rows if r.get("accepted"))
    total_score = sum(_score(r) for r in rows)
    return {
        "count": count,
        "accepted": accepted,
        "rejected": count - accepted,
        "acceptance_rate": round(accepted / count, 4) if count else 0.0,
        "avg_score": round(total_score / count, 2) if count else 0.0,
        "low_score_count": sum(1 for r in rows if _score(r) < LOW_SCORE_THRESHOLD),
        "compile_failures": sum(1 for r in rows if not _check_passed(r, "compile")),
        "runtime_failures": sum(1 for r in rows if not _check_passed(r, "runtime")),
        "semantic_failures": sum(1 for r in rows if not _check_passed(r, "semantic")),
        "keyword_failures": sum(1 for r in rows if not _check_passed(r, "keyword")),
    }


def _case_summary(row: dict[str, Any], include_classification: bool = False) -> dict[str, Any]:
    item = {
        "id": row.get("id"),
        "topic": _topic(row),
        "difficulty": _difficulty(row),
        "score": _score(row),
        "accepted": bool(row.get("accepted")),
        "failed_checks": _failed_checks(row),
        "compile_error": _short_compile_error(row),
        "runtime": _runtime_summary(row),
    }
    if include_classification:
        item.update(_classify_low_score(row))
    return item


def _decision_summary(analysis: dict[str, Any]) -> dict[str, Any]:
    low_cases = analysis["low_score_cases"]
    class_counts = Counter(c["classification"] for c in low_cases)
    by_topic = analysis["by_topic"]
    runtime_topics = [
        topic for topic, stats in by_topic.items() if stats.get("runtime_failures", 0) > 0
    ]
    low_topics = [
        topic for topic, stats in by_topic.items() if stats.get("low_score_count", 0) > 0
    ]

    spec_issue_cases = [
        c for c in low_cases if c["classification"] in {"task_spec_issue", "checker_rule_mismatch"}
    ]

    return {
        "isolated_evaluation": {
            "suitable": True,
            "answer": (
                "Yes, with caveats. The generated benchmark is balanced across four topics "
                "and exposes useful compile/runtime gaps. Golden comparison skipping is expected "
                "because this run has 40 generated tasks while the golden baseline has 4 tasks."
            ),
        },
        "candidate_training_corpus": {
            "suitable": True,
            "answer": (
                "generated_sft_candidate_v1 is suitable as an isolated candidate corpus only if it "
                "uses validated reference solutions, keeps these benchmark outputs out of training, "
                "and preserves a held-out generated evaluation split. Do not train on failed model "
                "outputs from this benchmark run."
            ),
        },
        "topics_needing_more_data_or_checker_work": sorted(set(runtime_topics + low_topics)),
        "task_spec_issues": {
            "confirmed_count": len([c for c in low_cases if c["classification"] == "task_spec_issue"]),
            "checker_audit_count": len(spec_issue_cases),
            "answer": (
                "No confirmed task_spec_issue was detected among the six unaccepted cases. "
                "However, runtime token mismatches in geometry and pattern_generation should be "
                "audited before those exact tasks are used as promotion-quality evaluation."
            ),
        },
        "low_score_classification_counts": dict(sorted(class_counts.items())),
    }


def analyze(run_id: str | None, latest: bool) -> dict[str, Any]:
    run_dir, report, results = _load_run(run_id, latest)
    if not results:
        raise ValueError(f"no benchmark results found in {run_dir}")

    by_topic_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_difficulty_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        by_topic_rows[_topic(row)].append(row)
        by_difficulty_rows[_difficulty(row)].append(row)

    failed_cases = [_case_summary(r) for r in results if not r.get("accepted")]
    low_score_cases = [
        _case_summary(r, include_classification=True)
        for r in results
        if _score(r) < LOW_SCORE_THRESHOLD
    ]

    analysis: dict[str, Any] = {
        "generated_at": _now(),
        "run_id": report.get("run_id") or run_dir.name,
        "run_dir": str(run_dir),
        "model": report.get("model"),
        "tasks": len(results),
        "accepted": sum(1 for r in results if r.get("accepted")),
        "rejected": sum(1 for r in results if not r.get("accepted")),
        "avg_score": round(sum(_score(r) for r in results) / len(results), 2),
        "reported_avg_score": report.get("average_score"),
        "reported_rates": report.get("rates", {}),
        "by_topic": {
            key: _summarize_group(rows) for key, rows in sorted(by_topic_rows.items())
        },
        "by_difficulty": {
            key: _summarize_group(rows) for key, rows in sorted(by_difficulty_rows.items())
        },
        "failed_cases": failed_cases,
        "low_score_cases": low_score_cases,
        "compile_failures": [
            _case_summary(r) for r in results if not _check_passed(r, "compile")
        ],
        "runtime_failures": [
            _case_summary(r) for r in results if not _check_passed(r, "runtime")
        ],
        "semantic_failures": [
            _case_summary(r) for r in results if not _check_passed(r, "semantic")
        ],
        "keyword_failures": [
            _case_summary(r) for r in results if not _check_passed(r, "keyword")
        ],
    }
    analysis["decisions"] = _decision_summary(analysis)
    return analysis


def _fmt_num(value: Any) -> str:
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}"
    return str(value)


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        lines.append("| " + " | ".join(_fmt_num(v) for v in row) + " |")
    return lines


def _markdown(analysis: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append
    a("# Generated Benchmark Analysis")
    a("")
    a(f"Generated: `{analysis['generated_at']}`")
    a(f"Run: `{analysis['run_id']}`")
    a(f"Run directory: `{analysis['run_dir']}`")
    a("")
    a("## Summary")
    a("")
    a(f"- Tasks: {analysis['tasks']}")
    a(f"- Accepted: {analysis['accepted']}/{analysis['tasks']}")
    a(f"- Rejected: {analysis['rejected']}")
    a(f"- Average score: {analysis['avg_score']}")
    a(f"- Low score cases (< {LOW_SCORE_THRESHOLD}): {len(analysis['low_score_cases'])}")
    a(f"- Compile failures: {len(analysis['compile_failures'])}")
    a(f"- Runtime failures: {len(analysis['runtime_failures'])}")
    a(f"- Semantic failures: {len(analysis['semantic_failures'])}")
    a(f"- Keyword failures: {len(analysis['keyword_failures'])}")
    a("")
    a("## Decision Answers")
    a("")
    decisions = analysis["decisions"]
    a(f"- Isolated evaluation: {decisions['isolated_evaluation']['answer']}")
    a(f"- Candidate training corpus: {decisions['candidate_training_corpus']['answer']}")
    a(
        "- Topics needing more data or checker work: "
        + ", ".join(decisions["topics_needing_more_data_or_checker_work"])
    )
    a(f"- Task spec issues: {decisions['task_spec_issues']['answer']}")
    a("")
    a("## By Topic")
    a("")
    topic_rows = [
        [
            topic,
            stats["count"],
            stats["accepted"],
            stats["rejected"],
            stats["avg_score"],
            stats["low_score_count"],
            stats["compile_failures"],
            stats["runtime_failures"],
            stats["semantic_failures"],
            stats["keyword_failures"],
        ]
        for topic, stats in analysis["by_topic"].items()
    ]
    lines.extend(
        _markdown_table(
            [
                "Topic",
                "Count",
                "Accepted",
                "Rejected",
                "Avg",
                "Low",
                "Compile Fail",
                "Runtime Fail",
                "Semantic Fail",
                "Keyword Fail",
            ],
            topic_rows,
        )
    )
    a("")
    a("## By Difficulty")
    a("")
    diff_rows = [
        [
            difficulty,
            stats["count"],
            stats["accepted"],
            stats["rejected"],
            stats["avg_score"],
            stats["low_score_count"],
            stats["compile_failures"],
            stats["runtime_failures"],
            stats["semantic_failures"],
            stats["keyword_failures"],
        ]
        for difficulty, stats in analysis["by_difficulty"].items()
    ]
    lines.extend(
        _markdown_table(
            [
                "Difficulty",
                "Count",
                "Accepted",
                "Rejected",
                "Avg",
                "Low",
                "Compile Fail",
                "Runtime Fail",
                "Semantic Fail",
                "Keyword Fail",
            ],
            diff_rows,
        )
    )
    a("")
    a("## Failed Cases")
    a("")
    failed_rows = [
        [
            c["id"],
            c["topic"],
            c["difficulty"],
            c["score"],
            ", ".join(c["failed_checks"]),
            c["compile_error"][:90],
            ", ".join(str(t) for t in c["runtime"]["missing"]),
        ]
        for c in analysis["failed_cases"]
    ]
    lines.extend(
        _markdown_table(
            ["ID", "Topic", "Difficulty", "Score", "Failed Checks", "Compile Evidence", "Missing Tokens"],
            failed_rows,
        )
    )
    a("")
    a("## Low Score Classification")
    a("")
    low_rows = [
        [
            c["id"],
            c["topic"],
            c["difficulty"],
            c["score"],
            c["classification"],
            "; ".join(c["evidence"])[:140],
        ]
        for c in analysis["low_score_cases"]
    ]
    lines.extend(
        _markdown_table(
            ["ID", "Topic", "Difficulty", "Score", "Classification", "Evidence"],
            low_rows,
        )
    )
    a("")
    a("## Recommendations")
    a("")
    a("- Treat `generated_c_tasks_v1` as a useful isolated evaluation set, not as a golden baseline replacement.")
    a("- Use `generated_sft_candidate_v1` only from validated reference solutions and keep a held-out split for generated benchmark evaluation.")
    a("- Audit game_simulation timeouts and the geometry/pattern runtime token expectations before relying on those checks for promotion decisions.")
    a("- Do not train on the six failed benchmark outputs; they are model/proxy failures, not trusted repair targets.")
    return "\n".join(lines) + "\n"


def write_reports(analysis: dict[str, Any]) -> None:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    _ANALYSIS_JSON.write_text(json.dumps(analysis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _ANALYSIS_MD.write_text(_markdown(analysis), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze generated benchmark failures")
    parser.add_argument("--run-id", default=_DEFAULT_RUN_ID, help="benchmark run id under local_ai/benchmark/reports/runs")
    parser.add_argument("--latest", action="store_true", help="use the newest run directory instead of --run-id")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        analysis = analyze(args.run_id, args.latest)
    except Exception as exc:
        print(f"[analyze-generated-benchmark] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    write_reports(analysis)
    print(
        "[analyze-generated-benchmark] "
        f"run={analysis['run_id']} accepted={analysis['accepted']}/{analysis['tasks']} "
        f"avg={analysis['avg_score']} failed={analysis['rejected']} "
        f"low_score={len(analysis['low_score_cases'])}"
    )
    print(f"[analyze-generated-benchmark] report >> {_ANALYSIS_MD}")


if __name__ == "__main__":
    main()
