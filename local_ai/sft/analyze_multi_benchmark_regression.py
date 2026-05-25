#!/usr/bin/env python3
"""Analyze generated candidate multi-benchmark regression.

Reads local_ai/sft/reports/multi_benchmark_report.json plus the raw comparison
reports referenced inside it, then writes a focused regression analysis for the
generated_candidate_v1 adapter.
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
_REPORT_DIR = _HERE / "reports"
_DEFAULT_MULTI_REPORT = _REPORT_DIR / "multi_benchmark_report.json"
_OUT_JSON = _REPORT_DIR / "generated_candidate_regression_analysis.json"
_OUT_MD = _REPORT_DIR / "generated_candidate_regression_analysis.md"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _check_passed(row: dict[str, Any], name: str) -> bool:
    return bool(((row.get("checks") or {}).get(name) or {}).get("passed"))


def _runtime_missing(row: dict[str, Any]) -> list[str]:
    return list(((row.get("checks") or {}).get("runtime") or {}).get("missing") or [])


def _compile_error(row: dict[str, Any]) -> str:
    compile_check = ((row.get("checks") or {}).get("compile") or {})
    errors = compile_check.get("errors") or []
    if errors:
        return str(errors[0])
    return str(compile_check.get("message") or "")


def _topic(row: dict[str, Any]) -> str:
    return str((row.get("task_meta") or {}).get("topic") or row.get("topic") or "unknown")


def _difficulty(row: dict[str, Any]) -> str:
    return str((row.get("task_meta") or {}).get("difficulty") or row.get("difficulty") or "unknown")


def _output_head(row: dict[str, Any]) -> str:
    runtime = ((row.get("checks") or {}).get("runtime") or {})
    return str(runtime.get("output_head") or "")[:300]


def _code_style(row: dict[str, Any]) -> dict[str, Any]:
    code = str(row.get("extracted_code") or "")
    lowered = code.lower()
    return {
        "code_chars": len(code),
        "uses_rand": "rand(" in code,
        "uses_srand": "srand(" in code,
        "uses_time": "time(" in code or "#include <time.h>" in lowered,
        "include_stdlib": "#include <stdlib.h>" in lowered,
        "include_math": "#include <math.h>" in lowered,
        "while_true": "while (1)" in code or "while(1)" in code,
        "printf_count": code.count("printf"),
        "scanf_count": code.count("scanf"),
    }


def _pair_rows(comparison: dict[str, Any]) -> list[dict[str, Any]]:
    base_by_id = {row.get("id"): row for row in comparison.get("base_results", [])}
    lora_by_id = {row.get("id"): row for row in comparison.get("lora_results", [])}
    pairs: list[dict[str, Any]] = []
    for task_id in sorted(set(base_by_id) | set(lora_by_id)):
        if not task_id:
            continue
        base = base_by_id.get(task_id, {})
        lora = lora_by_id.get(task_id, {})
        base_score = _safe_float(base.get("score"))
        lora_score = _safe_float(lora.get("score"))
        pairs.append(
            {
                "id": task_id,
                "topic": _topic(base or lora),
                "difficulty": _difficulty(base or lora),
                "base_score": base_score,
                "lora_score": lora_score,
                "delta": round(lora_score - base_score, 3),
                "base_accepted": bool(base.get("accepted")),
                "lora_accepted": bool(lora.get("accepted")),
                "base_compile_pass": _check_passed(base, "compile"),
                "lora_compile_pass": _check_passed(lora, "compile"),
                "base_runtime_pass": _check_passed(base, "runtime"),
                "lora_runtime_pass": _check_passed(lora, "runtime"),
                "base_semantic_pass": _check_passed(base, "semantic"),
                "lora_semantic_pass": _check_passed(lora, "semantic"),
                "base_keyword_pass": _check_passed(base, "keyword"),
                "lora_keyword_pass": _check_passed(lora, "keyword"),
                "runtime_regressed": _check_passed(base, "runtime") and not _check_passed(lora, "runtime"),
                "compile_regressed": _check_passed(base, "compile") and not _check_passed(lora, "compile"),
                "semantic_regressed": _check_passed(base, "semantic") and not _check_passed(lora, "semantic"),
                "keyword_regressed": _check_passed(base, "keyword") and not _check_passed(lora, "keyword"),
                "base_missing_tokens": _runtime_missing(base),
                "lora_missing_tokens": _runtime_missing(lora),
                "compile_error": _compile_error(lora),
                "base_output_head": _output_head(base),
                "lora_output_head": _output_head(lora),
                "base_style": _code_style(base),
                "lora_style": _code_style(lora),
            }
        )
    return pairs


def _aggregate_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    if not count:
        return {
            "count": 0,
            "avg_delta": 0.0,
            "accepted_delta": 0,
            "runtime_regressions": 0,
            "compile_regressions": 0,
            "semantic_regressions": 0,
            "keyword_regressions": 0,
            "largest_drop": None,
        }
    largest_drop = min(rows, key=lambda row: row["delta"])
    return {
        "count": count,
        "avg_delta": round(sum(row["delta"] for row in rows) / count, 3),
        "accepted_delta": sum(1 for row in rows if row["lora_accepted"]) - sum(1 for row in rows if row["base_accepted"]),
        "runtime_regressions": sum(1 for row in rows if row["runtime_regressed"]),
        "compile_regressions": sum(1 for row in rows if row["compile_regressed"]),
        "semantic_regressions": sum(1 for row in rows if row["semantic_regressed"]),
        "keyword_regressions": sum(1 for row in rows if row["keyword_regressed"]),
        "largest_drop": {
            "id": largest_drop["id"],
            "delta": largest_drop["delta"],
            "base_score": largest_drop["base_score"],
            "lora_score": largest_drop["lora_score"],
        },
    }


def _by_field(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field) or "unknown")].append(row)
    return {key: _aggregate_group(value) for key, value in sorted(grouped.items())}


def _style_change_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    changed = Counter()
    examples: list[dict[str, Any]] = []
    for row in rows:
        base = row["base_style"]
        lora = row["lora_style"]
        if lora["uses_rand"] and not base["uses_rand"]:
            changed["introduced_rand"] += 1
        if lora["uses_srand"] and not base["uses_srand"]:
            changed["introduced_srand"] += 1
        if lora["while_true"] and not base["while_true"]:
            changed["introduced_while_true"] += 1
        if lora["code_chars"] > base["code_chars"] * 1.25 and base["code_chars"] > 0:
            changed["longer_code"] += 1
        if lora["code_chars"] < base["code_chars"] * 0.75:
            changed["shorter_code"] += 1
        if row["delta"] < 0 and len(examples) < 8:
            examples.append(
                {
                    "id": row["id"],
                    "delta": row["delta"],
                    "base_style": base,
                    "lora_style": lora,
                    "base_output_head": row["base_output_head"],
                    "lora_output_head": row["lora_output_head"],
                }
            )
    return {"counts": dict(sorted(changed.items())), "examples": examples}


def _summary_from_multi(multi: dict[str, Any], key: str) -> dict[str, Any]:
    item = multi.get(key) or {}
    return {
        "benchmark": item.get("benchmark"),
        "accepted_delta": _safe_int(item.get("accepted_delta")),
        "avg_delta": _safe_float(item.get("avg_delta")),
        "runtime_delta": _safe_float(item.get("runtime_delta")),
        "compile_delta": _safe_float(item.get("compile_delta")),
        "semantic_delta": _safe_float(item.get("semantic_delta")),
        "keyword_delta": _safe_float(item.get("keyword_delta")),
        "tasks": _safe_int(item.get("tasks")),
        "base_accepted": _safe_int(item.get("accepted_base")),
        "lora_accepted": _safe_int(item.get("accepted_lora")),
        "base_avg": _safe_float(item.get("avg_base")),
        "lora_avg": _safe_float(item.get("avg_lora")),
    }


def _load_raw_comparison(multi: dict[str, Any], key: str) -> dict[str, Any]:
    report_path = ((multi.get(key) or {}).get("report_path") or "")
    if not report_path:
        raise FileNotFoundError(f"missing report_path for {key}")
    return _load_json(Path(report_path))


def analyze(multi_report_path: Path) -> dict[str, Any]:
    multi = _load_json(multi_report_path)
    strict_raw = _load_raw_comparison(multi, "strict_benchmark")
    generated_raw = _load_raw_comparison(multi, "generated_benchmark")

    strict_rows = _pair_rows(strict_raw)
    generated_rows = _pair_rows(generated_raw)
    strict_largest = min(strict_rows, key=lambda row: row["delta"], default=None)
    generated_largest = sorted(generated_rows, key=lambda row: row["delta"])[:10]

    generated_by_topic = _by_field(generated_rows, "topic")
    generated_by_difficulty = _by_field(generated_rows, "difficulty")
    regression_topics = [
        topic
        for topic, stats in generated_by_topic.items()
        if stats["avg_delta"] < 0 or stats["runtime_regressions"] or stats["compile_regressions"] or stats["accepted_delta"] < 0
    ]

    strict_runtime_regressions = [row for row in strict_rows if row["runtime_regressed"]]
    generated_runtime_regressions = [row for row in generated_rows if row["runtime_regressed"]]
    strict_compile_regressions = [row for row in strict_rows if row["compile_regressed"]]
    generated_compile_regressions = [row for row in generated_rows if row["compile_regressed"]]

    output_style = {
        "strict": _style_change_summary(strict_rows),
        "generated": _style_change_summary(generated_rows),
    }

    pattern: dict[str, Any] = {
        "concentrated_topic": regression_topics,
        "runtime_regression": bool(strict_runtime_regressions or generated_runtime_regressions),
        "compile_regression": bool(strict_compile_regressions or generated_compile_regressions),
        "model_output_style_changed": bool(output_style["strict"]["counts"] or output_style["generated"]["counts"]),
        "likely_over_regularization": True,
        "notes": [
            "Both strict and generated benchmarks regressed, so this is not just synthetic overfit.",
            "Strict regression is concentrated in the game simulation task 2025_midterm_004 runtime behavior.",
            "Generated regression is dominated by game_simulation_010, where LoRA output loses compile/runtime correctness.",
            "The small global generated avg drop is caused by a narrow but severe game_simulation drop, not broad topic collapse.",
        ],
    }

    return {
        "timestamp": _now(),
        "adapter": multi.get("adapter"),
        "source_report": str(multi_report_path),
        "status": "reject",
        "promotion_decision": {
            "do_not_promote": True,
            "do_not_use_as_default": True,
            "keep_as_ablation_artifact": True,
        },
        "multi_benchmark_decision": multi.get("decision"),
        "strict_benchmark": {
            "summary": _summary_from_multi(multi, "strict_benchmark"),
            "largest_drop_task": strict_largest,
            "per_task_deltas": strict_rows,
            "runtime_regressions": strict_runtime_regressions,
            "compile_regressions": strict_compile_regressions,
        },
        "generated_benchmark": {
            "summary": _summary_from_multi(multi, "generated_benchmark"),
            "largest_drop_tasks": generated_largest,
            "per_task_deltas": generated_rows,
            "by_topic_regression": generated_by_topic,
            "by_difficulty_regression": generated_by_difficulty,
            "runtime_regressions": generated_runtime_regressions,
            "compile_regressions": generated_compile_regressions,
        },
        "regression_pattern": pattern,
        "output_style_change": output_style,
        "conclusion": (
            "generated_candidate_v1 status = reject. Do not promote, do not use as default, "
            "and keep it only as an ablation artifact."
        ),
        "next_strategy": [
            {
                "strategy": "topic_specific_small_adapter",
                "details": [
                    "Train pattern_only_candidate_v1 or series_only_candidate_v1 instead of all 40 generated tasks.",
                    "Avoid game_simulation in the next candidate until game runtime behavior is guarded.",
                ],
            },
            {
                "strategy": "reduce_dataset_noise",
                "details": [
                    "Remove or audit low-score generated benchmark cases.",
                    "Use only high-confidence generated tasks with stable compile/runtime outcomes.",
                ],
            },
            {
                "strategy": "build_filtered_generated_corpus",
                "details": [
                    "Prefer accepted_by_base=false but reference_solution verified tasks when targeting improvement.",
                    "Alternatively build topic-specific selected sets rather than training on all 40 at once.",
                    "Keep strict benchmark and generated benchmark comparison mandatory for every candidate.",
                ],
            },
        ],
    }


def _short_task(row: dict[str, Any] | None) -> str:
    if not row:
        return "n/a"
    return f"{row.get('id')} ({row.get('base_score')} -> {row.get('lora_score')}, delta {row.get('delta')})"


def _md_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    return lines


def _markdown(report: dict[str, Any]) -> str:
    strict = report["strict_benchmark"]
    generated = report["generated_benchmark"]
    pattern = report["regression_pattern"]
    lines: list[str] = []
    a = lines.append
    a("# Generated Candidate Regression Analysis")
    a("")
    a(f"Generated: `{report['timestamp']}`")
    a(f"Adapter: `{report['adapter']}`")
    a("Status: **reject**")
    a("")
    a("## Conclusion")
    a("")
    a(report["conclusion"])
    a("")
    a("- Do not promote.")
    a("- Do not use as default.")
    a("- Keep as ablation artifact.")
    a("- Do not continue training this full generated_sft_candidate_v1 adapter.")
    a("")
    a("## Strict Benchmark")
    a("")
    s = strict["summary"]
    a(f"- Accepted delta: {s['accepted_delta']}")
    a(f"- Avg delta: {s['avg_delta']}")
    a(f"- Runtime delta: {s['runtime_delta']}")
    a(f"- Largest drop: `{_short_task(strict['largest_drop_task'])}`")
    a("")
    strict_rows = [
        [
            row["id"],
            row["base_score"],
            row["lora_score"],
            row["delta"],
            row["runtime_regressed"],
            row["compile_regressed"],
            ", ".join(row["lora_missing_tokens"]),
        ]
        for row in strict["per_task_deltas"]
    ]
    lines.extend(_md_table(["Task", "Base", "LoRA", "Delta", "Runtime Regressed", "Compile Regressed", "LoRA Missing Tokens"], strict_rows))
    a("")
    a("## Generated Benchmark")
    a("")
    g = generated["summary"]
    a(f"- Accepted delta: {g['accepted_delta']}")
    a(f"- Avg delta: {g['avg_delta']}")
    a(f"- Runtime delta: {g['runtime_delta']}")
    a(f"- Compile delta: {g['compile_delta']}")
    a("")
    drop_rows = [
        [
            row["id"],
            row["topic"],
            row["difficulty"],
            row["base_score"],
            row["lora_score"],
            row["delta"],
            row["runtime_regressed"],
            row["compile_regressed"],
        ]
        for row in generated["largest_drop_tasks"]
    ]
    lines.extend(_md_table(["Task", "Topic", "Difficulty", "Base", "LoRA", "Delta", "Runtime Regressed", "Compile Regressed"], drop_rows))
    a("")
    a("## By Topic")
    a("")
    topic_rows = [
        [
            topic,
            stats["count"],
            stats["avg_delta"],
            stats["accepted_delta"],
            stats["runtime_regressions"],
            stats["compile_regressions"],
            _short_task(stats["largest_drop"]),
        ]
        for topic, stats in generated["by_topic_regression"].items()
    ]
    lines.extend(_md_table(["Topic", "Count", "Avg Delta", "Accepted Delta", "Runtime Regr.", "Compile Regr.", "Largest Drop"], topic_rows))
    a("")
    a("## By Difficulty")
    a("")
    diff_rows = [
        [
            diff,
            stats["count"],
            stats["avg_delta"],
            stats["accepted_delta"],
            stats["runtime_regressions"],
            stats["compile_regressions"],
            _short_task(stats["largest_drop"]),
        ]
        for diff, stats in generated["by_difficulty_regression"].items()
    ]
    lines.extend(_md_table(["Difficulty", "Count", "Avg Delta", "Accepted Delta", "Runtime Regr.", "Compile Regr.", "Largest Drop"], diff_rows))
    a("")
    a("## Regression Pattern")
    a("")
    a(f"- Concentrated topic(s): {', '.join(pattern['concentrated_topic']) or 'none'}")
    a(f"- Runtime regression: {pattern['runtime_regression']}")
    a(f"- Compile regression: {pattern['compile_regression']}")
    a(f"- Model output style changed: {pattern['model_output_style_changed']}")
    a(f"- Likely generated candidate over-regularization: {pattern['likely_over_regularization']}")
    for note in pattern["notes"]:
        a(f"- {note}")
    a("")
    a("## Next Strategy")
    a("")
    for item in report["next_strategy"]:
        a(f"### {item['strategy']}")
        for detail in item["details"]:
            a(f"- {detail}")
        a("")
    return "\n".join(lines)


def write_reports(report: dict[str, Any]) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _OUT_MD.write_text(_markdown(report), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze generated candidate multi-benchmark regression")
    parser.add_argument("--input", default=str(_DEFAULT_MULTI_REPORT), help="Path to multi_benchmark_report.json")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        report = analyze(Path(args.input))
    except Exception as exc:
        print(f"[analyze-multi-regression] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    write_reports(report)
    print("[analyze-multi-regression] status=reject")
    print(f"[analyze-multi-regression] report >> {_OUT_MD}")


if __name__ == "__main__":
    main()
