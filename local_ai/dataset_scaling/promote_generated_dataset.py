#!/usr/bin/env python3
"""Promotion gate for generated dataset candidates.

The gate classifies generated_sft_candidate_v1 using validation, benchmark,
and config metadata. It writes reports only; it does not modify the production
SFT corpus, training jobs, benchmark scoring, or generated task data.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_REPO_ROOT = _LOCAL_AI.parent
_REPORTS_DIR = _HERE / "reports"

_DATASET_ID = "generated_sft_candidate_v1"
_BENCHMARK_ID = "generated_c_tasks_v1"
_BENCHMARK_DATASET_ID = "generated_benchmark_v1"

_SUMMARY_PATH = _REPORTS_DIR / "generated_dataset_summary.json"
_SOLUTION_VALIDATION_PATH = _REPORTS_DIR / "generated_solution_validation_report.json"
_BENCHMARK_ANALYSIS_PATH = _REPORTS_DIR / "generated_benchmark_analysis.json"
_DATASET_CARD_PATH = _REPORTS_DIR / "generated_dataset_card.md"
_DATASETS_CONFIG = _LOCAL_AI / "config" / "datasets.json"
_BENCHMARKS_CONFIG = _LOCAL_AI / "config" / "benchmarks.json"
_REPORT_JSON = _REPORTS_DIR / "generated_dataset_promotion_report.json"
_REPORT_MD = _REPORTS_DIR / "generated_dataset_promotion_report.md"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _load_json(path)


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _topic_min_acceptance(by_topic: dict[str, Any]) -> float:
    rates: list[float] = []
    for stats in by_topic.values():
        if not isinstance(stats, dict):
            continue
        if "acceptance_rate" in stats:
            rates.append(float(stats.get("acceptance_rate") or 0.0))
        else:
            count = float(stats.get("count") or 0)
            accepted = float(stats.get("accepted") or 0)
            rates.append(_ratio(accepted, count))
    return min(rates) if rates else 0.0


def _weak_topics(by_topic: dict[str, Any]) -> list[dict[str, Any]]:
    weak: list[dict[str, Any]] = []
    for topic, stats in sorted(by_topic.items()):
        if not isinstance(stats, dict):
            continue
        rate = float(stats.get("acceptance_rate") or _ratio(float(stats.get("accepted") or 0), float(stats.get("count") or 0)))
        low_score_count = int(stats.get("low_score_count") or 0)
        runtime_failures = int(stats.get("runtime_failures") or 0)
        compile_failures = int(stats.get("compile_failures") or 0)
        if rate < 0.8 or low_score_count > 0 or runtime_failures > 0 or compile_failures > 0:
            weak.append(
                {
                    "topic": topic,
                    "acceptance_rate": round(rate, 4),
                    "low_score_count": low_score_count,
                    "compile_failures": compile_failures,
                    "runtime_failures": runtime_failures,
                }
            )
    return weak


def _collect_metrics(
    summary: dict[str, Any],
    solution_validation: dict[str, Any],
    benchmark_analysis: dict[str, Any],
    datasets_config: dict[str, Any],
    benchmarks_config: dict[str, Any],
) -> dict[str, Any]:
    records = int(solution_validation.get("records") or summary.get("total_records") or 0)
    accepted_solutions = int(solution_validation.get("accepted") or 0)
    rejected_solutions = int(solution_validation.get("rejected") or 0)
    benchmark_tasks = int(benchmark_analysis.get("tasks") or 0)
    benchmark_accepted = int(benchmark_analysis.get("accepted") or 0)

    dataset_cfg = datasets_config.get(_DATASET_ID) or {}
    benchmark_dataset_cfg = datasets_config.get(_BENCHMARK_DATASET_ID) or {}
    benchmark_cfg = benchmarks_config.get(_BENCHMARK_ID) or {}
    by_topic = benchmark_analysis.get("by_topic") or {}
    task_spec_issues = (benchmark_analysis.get("decisions") or {}).get("task_spec_issues") or {}

    return {
        "dataset_id": _DATASET_ID,
        "benchmark_id": _BENCHMARK_ID,
        "records": records,
        "generated_solution_accepted": accepted_solutions,
        "generated_solution_rejected": rejected_solutions,
        "generated_solution_acceptance_rate": _ratio(accepted_solutions, records),
        "benchmark_tasks": benchmark_tasks,
        "benchmark_accepted": benchmark_accepted,
        "benchmark_rejected": int(benchmark_analysis.get("rejected") or max(benchmark_tasks - benchmark_accepted, 0)),
        "benchmark_acceptance_rate": _ratio(benchmark_accepted, benchmark_tasks),
        "benchmark_avg_score": float(benchmark_analysis.get("avg_score") or 0.0),
        "min_topic_acceptance_rate": _topic_min_acceptance(by_topic),
        "weak_topics": _weak_topics(by_topic),
        "low_score_cases": len(benchmark_analysis.get("low_score_cases") or []),
        "compile_verified_count": int(summary.get("compile_verified_count") or 0),
        "runtime_verified_count": int(summary.get("runtime_verified_count") or 0),
        "semantic_verified_count": int(summary.get("semantic_verified_count") or 0),
        "dataset_card_exists": _DATASET_CARD_PATH.exists(),
        "dataset_isolated": bool(dataset_cfg.get("isolated")),
        "benchmark_dataset_isolated": bool(benchmark_dataset_cfg.get("isolated")),
        "dataset_config_path": dataset_cfg.get("path"),
        "benchmark_dataset_config_path": benchmark_dataset_cfg.get("path"),
        "benchmark_dataset_ref": benchmark_cfg.get("dataset"),
        "task_spec_issue_count": int(task_spec_issues.get("confirmed_count") or 0),
        "checker_audit_count": int(task_spec_issues.get("checker_audit_count") or 0),
        "reported_task_spec_issue_answer": task_spec_issues.get("answer"),
    }


def _validation_unreliable(metrics: dict[str, Any]) -> bool:
    records = int(metrics["records"])
    if records <= 0:
        return True
    return (
        metrics["compile_verified_count"] < records
        or metrics["runtime_verified_count"] < records
        or metrics["semantic_verified_count"] < records
    )


def evaluate_gate(
    summary: dict[str, Any],
    solution_validation: dict[str, Any],
    benchmark_analysis: dict[str, Any],
    datasets_config: dict[str, Any],
    benchmarks_config: dict[str, Any],
) -> dict[str, Any]:
    metrics = _collect_metrics(summary, solution_validation, benchmark_analysis, datasets_config, benchmarks_config)
    reasons: list[str] = []
    risks: list[str] = []
    recommended_next_action = ""

    solution_acceptance = float(metrics["generated_solution_acceptance_rate"])
    benchmark_acceptance = float(metrics["benchmark_acceptance_rate"])
    rejected_ratio = _ratio(float(metrics["generated_solution_rejected"]), float(metrics["records"]))
    min_topic_rate = float(metrics["min_topic_acceptance_rate"])
    avg_score = float(metrics["benchmark_avg_score"])
    unreliable_validation = _validation_unreliable(metrics)
    task_spec_issues = int(metrics["task_spec_issue_count"]) > 0
    checker_mismatch = int(metrics["checker_audit_count"]) > 0

    if unreliable_validation or rejected_ratio > 0.25 or avg_score < 50:
        status = "reject"
        if unreliable_validation:
            reasons.append("compile/runtime/semantic validation is incomplete or unreliable")
        if rejected_ratio > 0.25:
            reasons.append("rejected generated solutions exceed 25%")
        if avg_score < 50:
            reasons.append("generated benchmark avg_score < 50")
        recommended_next_action = "Do not use this generated corpus; repair validation and regenerate before any training experiment."
    elif solution_acceptance < 0.90 or benchmark_acceptance < 0.70 or task_spec_issues or checker_mismatch:
        status = "needs_audit"
        if solution_acceptance < 0.90:
            reasons.append("generated solutions accepted < 90%")
        if benchmark_acceptance < 0.70:
            reasons.append("benchmark accepted < 70%")
        if task_spec_issues:
            reasons.append("task spec issues detected")
        if checker_mismatch:
            reasons.append("checker mismatch detected")
        recommended_next_action = "Audit task specs/checkers and regenerate or revalidate before training."
    elif (
        solution_acceptance >= 0.95
        and int(metrics["generated_solution_rejected"]) == 0
        and benchmark_acceptance >= 0.80
        and avg_score >= 75
        and min_topic_rate >= 0.70
        and metrics["dataset_card_exists"]
        and metrics["dataset_isolated"]
    ):
        status = "promote_to_candidate_training"
        reasons.append("validated generated solutions meet candidate-training threshold")
        reasons.append("generated benchmark acceptance and avg_score meet gate threshold")
        reasons.append("all topic acceptance rates are >= 70%")
        reasons.append("dataset card exists and dataset config is isolated=true")
        recommended_next_action = (
            "Create a guarded, isolated LoRA experiment using generated_sft_candidate_v1; "
            "compare against base on both generated_c_tasks_v1 and the existing strict exam benchmark before any adapter promotion."
        )
    elif solution_acceptance >= 0.90 and benchmark_acceptance >= 0.70:
        status = "isolated_eval_only"
        reasons.append("dataset is useful for isolated evaluation but has weak cases or audit needs")
        recommended_next_action = "Keep as isolated evaluation data until weak topics/checkers are audited."
    else:
        status = "needs_audit"
        reasons.append("dataset did not satisfy a higher confidence gate")
        recommended_next_action = "Audit validation and benchmark evidence before using for training."

    if metrics["weak_topics"]:
        risks.append("Benchmark has weak or noisy topic signals; review weak_topics before promotion-quality use.")
    if metrics["low_score_cases"]:
        risks.append(f"Benchmark contains {metrics['low_score_cases']} low-score model outputs; do not train on failed outputs.")
    if metrics["benchmark_dataset_ref"] != _BENCHMARK_DATASET_ID:
        risks.append("generated_c_tasks_v1 benchmark is not pointing at generated_benchmark_v1.")
    if not metrics["benchmark_dataset_isolated"]:
        risks.append("generated benchmark dataset config is not marked isolated=true.")
    risks.append("Candidate-training-ready does not mean default corpus; keep this data isolated until guarded experiments pass.")

    return {
        "generated_at": _now(),
        "dataset_id": _DATASET_ID,
        "status": status,
        "candidate_training_ready": status == "promote_to_candidate_training",
        "decision": status,
        "reasons": reasons,
        "metrics": metrics,
        "risks": risks,
        "recommended_next_action": recommended_next_action,
        "side_effects": "reports_only",
    }


def _markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lines: list[str] = []
    a = lines.append
    a("# Generated Dataset Promotion Report")
    a("")
    a(f"Generated: `{report['generated_at']}`")
    a(f"Dataset: `{report['dataset_id']}`")
    a(f"Decision: **{report['decision']}**")
    a(f"Candidate-training-ready: **{report['candidate_training_ready']}**")
    a("")
    a("## Reasons")
    a("")
    for reason in report["reasons"]:
        a(f"- {reason}")
    a("")
    a("## Metrics")
    a("")
    a("| Metric | Value |")
    a("|--------|------:|")
    for key in (
        "records",
        "generated_solution_accepted",
        "generated_solution_rejected",
        "generated_solution_acceptance_rate",
        "benchmark_tasks",
        "benchmark_accepted",
        "benchmark_rejected",
        "benchmark_acceptance_rate",
        "benchmark_avg_score",
        "min_topic_acceptance_rate",
        "low_score_cases",
        "compile_verified_count",
        "runtime_verified_count",
        "semantic_verified_count",
        "dataset_card_exists",
        "dataset_isolated",
    ):
        a(f"| {key} | {metrics.get(key)} |")
    a("")
    a("## Weak Topics / Audit Signals")
    a("")
    weak_topics = metrics.get("weak_topics") or []
    if weak_topics:
        a("| Topic | Accept Rate | Low Score | Compile Fail | Runtime Fail |")
        a("|-------|------------:|----------:|-------------:|-------------:|")
        for row in weak_topics:
            a(
                f"| {row['topic']} | {row['acceptance_rate']} | {row['low_score_count']} | "
                f"{row['compile_failures']} | {row['runtime_failures']} |"
            )
    else:
        a("No weak topic signals detected.")
    a("")
    a("## Risks")
    a("")
    for risk in report["risks"]:
        a(f"- {risk}")
    a("")
    a("## Recommended Next Action")
    a("")
    a(report["recommended_next_action"])
    a("")
    a("## Guardrails")
    a("")
    a("- Isolated candidate only.")
    a("- Not default corpus.")
    a("- Use with guarded benchmark comparison.")
    a("- Do not use failed benchmark outputs for training.")
    a("- This script does not modify SFT corpus, training jobs, benchmark scoring, or generated task data.")
    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any]) -> None:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    _REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _REPORT_MD.write_text(_markdown(report), encoding="utf-8")


def promote_generated_dataset() -> dict[str, Any]:
    summary = _load_json(_SUMMARY_PATH)
    solution_validation = _load_json(_SOLUTION_VALIDATION_PATH)
    benchmark_analysis = _load_json(_BENCHMARK_ANALYSIS_PATH)
    datasets_config = _safe_load_json(_DATASETS_CONFIG)
    benchmarks_config = _safe_load_json(_BENCHMARKS_CONFIG)
    return evaluate_gate(summary, solution_validation, benchmark_analysis, datasets_config, benchmarks_config)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate generated dataset promotion gate")
    return parser.parse_args()


def main() -> None:
    _parse_args()
    try:
        report = promote_generated_dataset()
    except Exception as exc:
        print(f"[promote-generated-dataset] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    write_reports(report)
    print(
        "[promote-generated-dataset] "
        f"decision={report['decision']} "
        f"candidate_training_ready={report['candidate_training_ready']}"
    )
    print(f"[promote-generated-dataset] report >> {_REPORT_MD}")


if __name__ == "__main__":
    main()
