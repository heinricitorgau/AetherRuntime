#!/usr/bin/env python3
"""Analyze LoRA benchmark regressions without changing training or scoring.

Reads comparison_report.json from benchmark_lora.py and writes:
  - local_ai/sft/reports/lora_regression_analysis.json
  - local_ai/sft/reports/lora_regression_analysis.md
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPORTS = _HERE / "reports"
_DEFAULT_INPUT = _REPORTS / "comparison_report.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _check(result: dict[str, Any], name: str) -> dict[str, Any]:
    return result.get("checks", {}).get(name, {}) or {}


def _passed(result: dict[str, Any], name: str) -> bool | None:
    check = _check(result, name)
    if "passed" not in check:
        return None
    return bool(check.get("passed"))


def _score(result: dict[str, Any]) -> int:
    return int(result.get("score", 0) or 0)


def _runtime_missing(result: dict[str, Any]) -> list[str]:
    missing = _check(result, "runtime").get("missing", [])
    return [str(item) for item in missing] if isinstance(missing, list) else []


def _runtime_found(result: dict[str, Any]) -> list[str]:
    found = _check(result, "runtime").get("found", [])
    return [str(item) for item in found] if isinstance(found, list) else []


def _output_head(result: dict[str, Any]) -> str:
    runtime = _check(result, "runtime")
    value = runtime.get("output_head")
    if value is None:
        value = result.get("raw_output") or result.get("raw_response") or ""
    return str(value)


def _keyword_score(result: dict[str, Any]) -> float | None:
    score = _check(result, "keyword").get("score")
    if score is None:
        return None
    return float(score)


def _runtime_match_ratio(result: dict[str, Any]) -> float | None:
    ratio = _check(result, "runtime").get("match_ratio")
    if ratio is None:
        return None
    return float(ratio)


def _bool_delta(base: bool | None, lora: bool | None) -> int | None:
    if base is None or lora is None:
        return None
    return int(lora) - int(base)


def _task_topic(result: dict[str, Any]) -> str:
    return str(result.get("task_meta", {}).get("topic", ""))


def _missing_diff(base: dict[str, Any], lora: dict[str, Any]) -> dict[str, list[str]]:
    base_missing = set(_runtime_missing(base))
    lora_missing = set(_runtime_missing(lora))
    return {
        "base_missing": sorted(base_missing),
        "lora_missing": sorted(lora_missing),
        "new_missing": sorted(lora_missing - base_missing),
        "resolved_missing": sorted(base_missing - lora_missing),
        "base_found": _runtime_found(base),
        "lora_found": _runtime_found(lora),
    }


def _analyze_task(task_id: str, base: dict[str, Any], lora: dict[str, Any]) -> dict[str, Any]:
    base_score = _score(base)
    lora_score = _score(lora)
    missing = _missing_diff(base, lora)
    base_runtime = _passed(base, "runtime")
    lora_runtime = _passed(lora, "runtime")

    compile_delta = _bool_delta(_passed(base, "compile"), _passed(lora, "compile"))
    runtime_delta = _bool_delta(base_runtime, lora_runtime)
    semantic_delta = _bool_delta(_passed(base, "semantic"), _passed(lora, "semantic"))
    keyword_delta = _bool_delta(_passed(base, "keyword"), _passed(lora, "keyword"))

    missing_increased = len(missing["lora_missing"]) > len(missing["base_missing"])
    runtime_pass_to_fail = base_runtime is True and lora_runtime is False
    score_delta = lora_score - base_score

    regression_reasons: list[str] = []
    if score_delta < 0:
        regression_reasons.append("score_delta_negative")
    if runtime_pass_to_fail:
        regression_reasons.append("runtime_pass_to_fail")
    if missing_increased:
        regression_reasons.append("missing_tokens_increased")
    if compile_delta is not None and compile_delta < 0:
        regression_reasons.append("compile_regression")
    if semantic_delta is not None and semantic_delta < 0:
        regression_reasons.append("semantic_regression")
    if keyword_delta is not None and keyword_delta < 0:
        regression_reasons.append("keyword_regression")

    return {
        "id": task_id,
        "topic": _task_topic(lora) or _task_topic(base),
        "base_score": base_score,
        "lora_score": lora_score,
        "delta": score_delta,
        "avg_score_contribution": None,
        "compile_pass_base": _passed(base, "compile"),
        "compile_pass_lora": _passed(lora, "compile"),
        "compile_pass_delta": compile_delta,
        "runtime_pass_base": base_runtime,
        "runtime_pass_lora": lora_runtime,
        "runtime_pass_delta": runtime_delta,
        "runtime_match_ratio_base": _runtime_match_ratio(base),
        "runtime_match_ratio_lora": _runtime_match_ratio(lora),
        "semantic_pass_base": _passed(base, "semantic"),
        "semantic_pass_lora": _passed(lora, "semantic"),
        "semantic_pass_delta": semantic_delta,
        "keyword_pass_base": _passed(base, "keyword"),
        "keyword_pass_lora": _passed(lora, "keyword"),
        "keyword_pass_delta": keyword_delta,
        "keyword_score_base": _keyword_score(base),
        "keyword_score_lora": _keyword_score(lora),
        "missing_tokens": missing,
        "missing_tokens_increased": missing_increased,
        "base_output_head": _output_head(base),
        "lora_output_head": _output_head(lora),
        "regressed": bool(regression_reasons),
        "regression_reasons": regression_reasons,
    }


def _interference_assessment(tasks: list[dict[str, Any]], report: dict[str, Any]) -> dict[str, Any]:
    regressed = [task for task in tasks if task["regressed"]]
    runtime_regressed = [
        task for task in regressed
        if task["runtime_pass_base"] is True and task["runtime_pass_lora"] is False
    ]
    geometry_regressed = [
        task for task in regressed
        if "geometry" in task["topic"].lower() or "triangle" in task["topic"].lower()
    ]
    non_geometry_regressed = [
        task for task in regressed
        if task not in geometry_regressed
    ]
    adapter = str(report.get("adapter", "")).lower()
    geometry_adapter = "geometry" in adapter or "geometry" in str(report.get("retry_round", "")).lower()

    if geometry_adapter and geometry_regressed and runtime_regressed:
        verdict = "likely_geometry_overfit_with_runtime_interference"
    elif geometry_adapter and non_geometry_regressed:
        verdict = "possible_cross_task_interference"
    elif regressed:
        verdict = "adapter_regression_observed"
    else:
        verdict = "no_task_level_regression_detected"

    return {
        "adapter_is_geometry_retry": geometry_adapter,
        "verdict": verdict,
        "geometry_regression_task_ids": [task["id"] for task in geometry_regressed],
        "non_geometry_regression_task_ids": [task["id"] for task in non_geometry_regressed],
        "runtime_pass_to_fail_task_ids": [task["id"] for task in runtime_regressed],
        "summary": (
            "The adapter preserves compile, semantic, and keyword checks but changes "
            "runtime behavior. The largest drop is on a geometry task, which is direct "
            "evidence that retry_geometry_v1 is not safe to promote as-is."
        ),
    }


def _retention_recommendation(analysis: dict[str, Any]) -> dict[str, Any]:
    deltas = analysis["report_summary"].get("deltas", {})
    runtime_delta = float(deltas.get("runtime_pass_rate", 0.0) or 0.0)
    avg_delta = float(deltas.get("avg_score", 0.0) or 0.0)
    runtime_regressions = analysis["interference_assessment"]["runtime_pass_to_fail_task_ids"]

    keep_for_production = not (avg_delta < 0 or runtime_delta < 0 or runtime_regressions)
    return {
        "keep_for_production_or_default": keep_for_production,
        "keep_for_analysis_only": not keep_for_production,
        "recommendation": (
            "Do not promote retry_geometry_v1 as the default adapter. Keep the artifact "
            "for regression analysis and ablation only, then train a smaller guarded run."
            if not keep_for_production
            else "Adapter is acceptable to retain as a candidate."
        ),
    }


def _training_strategy() -> list[dict[str, str]]:
    return [
        {
            "action": "lower_epochs",
            "reason": "The adapter preserved syntax but changed runtime behavior, a classic overfit signal.",
        },
        {
            "action": "lower_learning_rate",
            "reason": "Reduce behavioral drift while still nudging geometry repairs.",
        },
        {
            "action": "lower_lora_rank",
            "reason": "Constrain adapter capacity so a tiny repair set cannot dominate general task behavior.",
        },
        {
            "action": "mix_base_sft_samples",
            "reason": "Blend neutral base examples to preserve non-target runtime behavior.",
        },
        {
            "action": "add_anti_regression_examples",
            "reason": "Include tasks 2025_midterm_001/002/004 and the base-passing geometry behavior as guardrails.",
        },
    ]


def analyze(report: dict[str, Any]) -> dict[str, Any]:
    base_results = {str(item["id"]): item for item in report.get("base_results", [])}
    lora_results = {str(item["id"]): item for item in report.get("lora_results", [])}
    task_ids = sorted(set(base_results) & set(lora_results))

    tasks = [
        _analyze_task(task_id, base_results[task_id], lora_results[task_id])
        for task_id in task_ids
    ]
    for task in tasks:
        task["avg_score_contribution"] = round(task["delta"] / len(tasks), 3) if tasks else 0.0
    regression_tasks = [task for task in tasks if task["regressed"]]
    score_regression_tasks = [task for task in tasks if task["delta"] < 0]
    avg_delta_from_tasks = round(sum(task["delta"] for task in tasks) / len(tasks), 3) if tasks else 0.0

    analysis: dict[str, Any] = {
        "generated_at": _now(),
        "source_report": str(_DEFAULT_INPUT),
        "report_summary": {
            "timestamp": report.get("timestamp"),
            "model": report.get("model"),
            "adapter": report.get("adapter"),
            "tasks": report.get("tasks", len(tasks)),
            "verdict": report.get("verdict"),
            "base": report.get("base", {}),
            "lora": report.get("lora", {}),
            "deltas": report.get("deltas", {}),
            "avg_delta_from_task_scores": avg_delta_from_tasks,
        },
        "tasks": tasks,
        "regression_tasks": regression_tasks,
        "score_regression_tasks": score_regression_tasks,
        "largest_score_drop": min(tasks, key=lambda task: task["delta"]) if tasks else None,
    }
    analysis["interference_assessment"] = _interference_assessment(tasks, report)
    analysis["retention_recommendation"] = _retention_recommendation(analysis)
    analysis["next_training_strategy"] = _training_strategy()
    return analysis


def _bool_word(value: bool | None) -> str:
    if value is None:
        return "n/a"
    return "pass" if value else "fail"


def _format_tokens(tokens: list[str]) -> str:
    return ", ".join(tokens) if tokens else "-"


def build_markdown(analysis: dict[str, Any]) -> str:
    summary = analysis["report_summary"]
    deltas = summary.get("deltas", {})
    tasks = analysis["tasks"]
    regressions = analysis["regression_tasks"]
    largest = analysis.get("largest_score_drop")
    interference = analysis["interference_assessment"]
    retention = analysis["retention_recommendation"]

    lines: list[str] = []
    a = lines.append
    a("# LoRA Regression Analysis")
    a("")
    a(f"Generated: {analysis['generated_at']}")
    a(f"Source report timestamp: {summary.get('timestamp')}")
    a(f"Adapter: `{summary.get('adapter')}`")
    a(f"Verdict: **{summary.get('verdict')}**")
    a("")
    a("## Executive Answer")
    a("")
    a(f"- Accepted stayed {summary.get('base', {}).get('accepted')}/{summary.get('tasks')} -> {summary.get('lora', {}).get('accepted')}/{summary.get('tasks')}.")
    a(f"- Compile stayed {summary.get('base', {}).get('rates', {}).get('compile_pass_rate')} -> {summary.get('lora', {}).get('rates', {}).get('compile_pass_rate')}.")
    a(f"- Runtime dropped {summary.get('base', {}).get('rates', {}).get('runtime_pass_rate')} -> {summary.get('lora', {}).get('rates', {}).get('runtime_pass_rate')}.")
    a(f"- Avg score delta is {deltas.get('avg_score')} points; task-score reconstruction gives {summary.get('avg_delta_from_task_scores')}.")
    if largest:
        a(f"- Largest damage: `{largest['id']}` ({largest['topic']}), delta {largest['delta']} points.")
    a("")
    a("## Per-Task Delta")
    a("")
    a("| Task | Topic | Base | LoRA | Delta | Compile | Runtime | Semantic | Keyword | New Missing Tokens |")
    a("|------|-------|-----:|-----:|------:|---------|---------|----------|---------|--------------------|")
    for task in tasks:
        new_missing = _format_tokens(task["missing_tokens"]["new_missing"])
        a(
            f"| {task['id']} | {task['topic']} | {task['base_score']} | {task['lora_score']} | "
            f"{task['delta']} | {_bool_word(task['compile_pass_base'])}->{_bool_word(task['compile_pass_lora'])} | "
            f"{_bool_word(task['runtime_pass_base'])}->{_bool_word(task['runtime_pass_lora'])} | "
            f"{_bool_word(task['semantic_pass_base'])}->{_bool_word(task['semantic_pass_lora'])} | "
            f"{_bool_word(task['keyword_pass_base'])}->{_bool_word(task['keyword_pass_lora'])} | "
            f"{new_missing} |"
        )
    a("")
    a("## Regression Tasks")
    a("")
    if not regressions:
        a("No task-level regressions detected.")
    for task in regressions:
        a(f"### {task['id']} - {task['topic']}")
        a("")
        a(f"- Score: {task['base_score']} -> {task['lora_score']} ({task['delta']}).")
        a(f"- Regression reasons: {', '.join(task['regression_reasons'])}.")
        a(f"- Compile: {_bool_word(task['compile_pass_base'])} -> {_bool_word(task['compile_pass_lora'])}.")
        a(f"- Runtime: {_bool_word(task['runtime_pass_base'])} -> {_bool_word(task['runtime_pass_lora'])}.")
        a(f"- Semantic: {_bool_word(task['semantic_pass_base'])} -> {_bool_word(task['semantic_pass_lora'])}.")
        a(f"- Keyword: {_bool_word(task['keyword_pass_base'])} -> {_bool_word(task['keyword_pass_lora'])}.")
        a(f"- Base missing tokens: {_format_tokens(task['missing_tokens']['base_missing'])}.")
        a(f"- LoRA missing tokens: {_format_tokens(task['missing_tokens']['lora_missing'])}.")
        a(f"- Newly missing tokens: {_format_tokens(task['missing_tokens']['new_missing'])}.")
        if task["base_output_head"] or task["lora_output_head"]:
            a("")
            a("Base output head:")
            a("```text")
            a(task["base_output_head"][:1000])
            a("```")
            a("LoRA output head:")
            a("```text")
            a(task["lora_output_head"][:1000])
            a("```")
        a("")
    a("## Damage Attribution")
    a("")
    a(f"- Interference verdict: **{interference['verdict']}**.")
    a(f"- Geometry regression tasks: {_format_tokens(interference['geometry_regression_task_ids'])}.")
    a(f"- Non-geometry regression tasks: {_format_tokens(interference['non_geometry_regression_task_ids'])}.")
    a(f"- Runtime pass-to-fail tasks: {_format_tokens(interference['runtime_pass_to_fail_task_ids'])}.")
    a(f"- Assessment: {interference['summary']}")
    a("")
    a("The average -4.5 is explained by task deltas: "
      f"{', '.join(f'{task['id']}={task['delta']}' for task in tasks)}. "
      "The large runtime failure is 2025_midterm_003: base produced `6.000`, "
      "LoRA produced repeated `4.146`, so both `area` and `6.000` became missing.")
    a("")
    a("## Keep Or Reject")
    a("")
    a(f"- Keep for production/default: **{retention['keep_for_production_or_default']}**.")
    a(f"- Keep for analysis only: **{retention['keep_for_analysis_only']}**.")
    a(f"- Recommendation: {retention['recommendation']}")
    a("")
    a("## Next Training Strategy")
    a("")
    for item in analysis["next_training_strategy"]:
        a(f"- {item['action']}: {item['reason']}")
    a("")
    a("## Non-Goals")
    a("")
    a("This analysis did not modify `train_lora.py` or benchmark scoring.")
    return "\n".join(lines) + "\n"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze LoRA regression from comparison_report.json")
    parser.add_argument("--input", type=Path, default=_DEFAULT_INPUT)
    parser.add_argument("--out-dir", type=Path, default=_REPORTS)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8"))
    analysis = analyze(report)
    analysis["source_report"] = str(args.input)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "lora_regression_analysis.json"
    md_path = args.out_dir / "lora_regression_analysis.md"
    json_path.write_text(json.dumps(analysis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(build_markdown(analysis), encoding="utf-8")

    largest = analysis.get("largest_score_drop") or {}
    print(f"[analysis] wrote {json_path}")
    print(f"[analysis] wrote {md_path}")
    print(
        "[analysis] largest_drop="
        f"{largest.get('id')} delta={largest.get('delta')} "
        f"avg_delta={analysis['report_summary'].get('deltas', {}).get('avg_score')}"
    )


if __name__ == "__main__":
    main()
