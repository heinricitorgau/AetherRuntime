#!/usr/bin/env python3
"""Run guarded multi-benchmark comparison for one LoRA adapter.

This wrapper compares the same adapter on:
1. c_exam_2025_strict_seeded
2. generated_c_tasks_v1

It writes an aggregate report only. It does not promote adapters, modify the
production SFT corpus, change benchmark scoring, or overwrite adapter artifacts.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPORT_DIR = _HERE / "reports"
_RUN_DIR = _REPORT_DIR / "multi_benchmark_runs"
_REPORT_JSON = _REPORT_DIR / "multi_benchmark_report.json"
_REPORT_MD = _REPORT_DIR / "multi_benchmark_report.md"

_STRICT_BENCHMARK = "c_exam_2025_strict_seeded"
_GENERATED_BENCHMARK = "generated_c_tasks_v1"


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


def _run_compare(adapter: Path, benchmark: str, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(_HERE / "benchmark_lora.py"),
        "--adapter",
        str(adapter),
        "--benchmark",
        benchmark,
        "--out-dir",
        str(out_dir),
    ]
    print(f"[multi-benchmark] running benchmark={benchmark}", flush=True)
    proc = subprocess.run(
        cmd,
        cwd=str(_HERE.parent.parent),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"benchmark {benchmark} failed with exit code {proc.returncode}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    report_path = out_dir / "comparison_report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"benchmark {benchmark} did not write {report_path}")
    comparison = _load_json(report_path)
    comparison["_stdout_tail"] = proc.stdout[-4000:]
    comparison["_stderr_tail"] = proc.stderr[-4000:]
    comparison["_report_path"] = str(report_path)
    return comparison


def _metric_summary(comparison: dict[str, Any]) -> dict[str, Any]:
    deltas = comparison.get("deltas") or {}
    base = comparison.get("base") or {}
    lora = comparison.get("lora") or {}
    return {
        "benchmark": comparison.get("benchmark") or comparison.get("metadata", {}).get("benchmark"),
        "tasks": _safe_int(comparison.get("tasks")),
        "verdict": comparison.get("verdict"),
        "accepted_base": _safe_int(base.get("accepted")),
        "accepted_lora": _safe_int(lora.get("accepted")),
        "accepted_delta": _safe_int(deltas.get("accepted")),
        "avg_base": _safe_float(base.get("avg_score")),
        "avg_lora": _safe_float(lora.get("avg_score")),
        "avg_delta": _safe_float(deltas.get("avg_score")),
        "runtime_base": _safe_float((base.get("rates") or {}).get("runtime_pass_rate")),
        "runtime_lora": _safe_float((lora.get("rates") or {}).get("runtime_pass_rate")),
        "runtime_delta": _safe_float(deltas.get("runtime_pass_rate")),
        "compile_delta": _safe_float(deltas.get("compile_pass_rate")),
        "semantic_delta": _safe_float(deltas.get("semantic_pass_rate")),
        "keyword_delta": _safe_float(deltas.get("keyword_pass_rate")),
        "report_path": comparison.get("_report_path"),
    }


def _benchmark_state(summary: dict[str, Any]) -> str:
    """Classify one benchmark as improvement, no_change, or regression."""
    if (
        summary["accepted_delta"] < 0
        or summary["avg_delta"] < -1.0
        or summary["runtime_delta"] < 0
        or summary["compile_delta"] < 0
        or summary["semantic_delta"] < 0
    ):
        return "regression"
    if (
        summary["accepted_delta"] > 0
        or summary["avg_delta"] > 1.0
        or summary["runtime_delta"] > 0
    ):
        return "improvement"
    return "no_change"


def _decision(strict_state: str, generated_state: str) -> tuple[str, list[str]]:
    if generated_state == "improvement" and strict_state != "regression":
        return "safe_generalization", [
            "strict benchmark has no regression",
            "generated benchmark improves",
        ]
    if generated_state == "improvement" and strict_state == "regression":
        return "synthetic_overfit", [
            "generated benchmark improves",
            "strict benchmark regresses",
        ]
    if strict_state == "regression" and generated_state == "regression":
        return "regression", ["both strict and generated benchmarks regress"]
    if strict_state == "regression":
        return "regression", ["strict benchmark regresses"]
    if generated_state == "regression":
        return "regression", ["generated benchmark regresses"]
    if strict_state == "no_change" and generated_state == "no_change":
        return "no_effect", ["both benchmarks are no_change"]
    return "no_effect", ["no regression detected, but generated benchmark did not improve"]


def compare_multi(adapter: Path, strict_benchmark: str, generated_benchmark: str) -> dict[str, Any]:
    if not adapter.exists():
        raise FileNotFoundError(f"adapter not found: {adapter}")

    strict_out = _RUN_DIR / strict_benchmark
    generated_out = _RUN_DIR / generated_benchmark
    strict_comparison = _run_compare(adapter, strict_benchmark, strict_out)
    generated_comparison = _run_compare(adapter, generated_benchmark, generated_out)

    strict = _metric_summary(strict_comparison)
    generated = _metric_summary(generated_comparison)
    strict["benchmark"] = strict_benchmark
    generated["benchmark"] = generated_benchmark

    strict_state = _benchmark_state(strict)
    generated_state = _benchmark_state(generated)
    status, reasons = _decision(strict_state, generated_state)

    return {
        "timestamp": _now(),
        "adapter": str(adapter),
        "strict_benchmark": strict,
        "generated_benchmark": generated,
        "strict_state": strict_state,
        "generated_state": generated_state,
        "decision": status,
        "reasons": reasons,
        "guardrails": {
            "promotion_to_default": False,
            "modifies_formal_sft_corpus": False,
            "modifies_benchmark_scoring": False,
            "auto_promotes_adapter": False,
            "overwrites_existing_adapters": False,
        },
        "raw_report_paths": {
            strict_benchmark: strict.get("report_path"),
            generated_benchmark: generated.get("report_path"),
        },
    }


def _markdown(report: dict[str, Any]) -> str:
    strict = report["strict_benchmark"]
    generated = report["generated_benchmark"]
    lines: list[str] = []
    a = lines.append
    a("# Multi-Benchmark LoRA Report")
    a("")
    a(f"Generated: `{report['timestamp']}`")
    a(f"Adapter: `{report['adapter']}`")
    a(f"Decision: **{report['decision']}**")
    a("")
    a("## Reasons")
    a("")
    for reason in report["reasons"]:
        a(f"- {reason}")
    a("")
    a("## Benchmark Deltas")
    a("")
    a("| Benchmark | State | Accepted Delta | Avg Delta | Runtime Delta | Compile Delta | Semantic Delta |")
    a("|-----------|-------|---------------:|----------:|--------------:|--------------:|---------------:|")
    a(
        f"| {strict['benchmark']} | {report['strict_state']} | {strict['accepted_delta']} | "
        f"{strict['avg_delta']} | {strict['runtime_delta']} | {strict['compile_delta']} | {strict['semantic_delta']} |"
    )
    a(
        f"| {generated['benchmark']} | {report['generated_state']} | {generated['accepted_delta']} | "
        f"{generated['avg_delta']} | {generated['runtime_delta']} | {generated['compile_delta']} | {generated['semantic_delta']} |"
    )
    a("")
    a("## Absolute Metrics")
    a("")
    a("| Benchmark | Base Accepted | LoRA Accepted | Base Avg | LoRA Avg | Base Runtime | LoRA Runtime |")
    a("|-----------|--------------:|--------------:|---------:|---------:|-------------:|-------------:|")
    for row in (strict, generated):
        a(
            f"| {row['benchmark']} | {row['accepted_base']}/{row['tasks']} | "
            f"{row['accepted_lora']}/{row['tasks']} | {row['avg_base']} | {row['avg_lora']} | "
            f"{row['runtime_base']} | {row['runtime_lora']} |"
        )
    a("")
    a("## Guardrails")
    a("")
    a("- No default adapter promotion.")
    a("- No formal SFT corpus modification.")
    a("- No benchmark scoring modification.")
    a("- No automatic adapter promotion.")
    a("- Existing adapter artifacts are not overwritten.")
    a("")
    a("## Raw Reports")
    a("")
    for name, path in report["raw_report_paths"].items():
        a(f"- `{name}`: `{path}`")
    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any]) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _REPORT_MD.write_text(_markdown(report), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare one LoRA adapter on strict and generated benchmarks")
    parser.add_argument("--adapter", required=True, help="Path to LoRA adapter directory")
    parser.add_argument("--strict-benchmark", default=_STRICT_BENCHMARK)
    parser.add_argument("--generated-benchmark", default=_GENERATED_BENCHMARK)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        report = compare_multi(Path(args.adapter), args.strict_benchmark, args.generated_benchmark)
    except Exception as exc:
        print(f"[multi-benchmark] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    write_reports(report)
    print(
        "[multi-benchmark] "
        f"decision={report['decision']} "
        f"strict={report['strict_state']} generated={report['generated_state']}"
    )
    print(f"[multi-benchmark] report >> {_REPORT_MD}")


if __name__ == "__main__":
    main()
