#!/usr/bin/env python3
"""Summarize synthetic LoRA training outcomes and freeze the route."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_REPORT_DIR = _HERE / "reports"
_EXPERIMENT_REGISTRY = _LOCAL_AI / "experiments" / "registry"
_ADAPTER_DIR = _HERE / "adapters"

_MULTI_REPORT = _REPORT_DIR / "multi_benchmark_report.json"
_GENERATED_REGRESSION = _REPORT_DIR / "generated_candidate_regression_analysis.json"
_GENERATED_BENCHMARK_ANALYSIS = _LOCAL_AI / "dataset_scaling" / "reports" / "generated_benchmark_analysis.json"
_PROMOTION_GATE = _LOCAL_AI / "dataset_scaling" / "reports" / "generated_dataset_promotion_report.json"
_OUT_JSON = _REPORT_DIR / "synthetic_training_summary.json"
_OUT_MD = _REPORT_DIR / "synthetic_training_summary.md"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_registry_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not _EXPERIMENT_REGISTRY.exists():
        return rows
    for path in sorted(_EXPERIMENT_REGISTRY.glob("*.json")):
        try:
            row = _load_json(path)
        except Exception:
            continue
        row["_path"] = str(path)
        rows.append(row)
    return rows


def _adapter_registry() -> dict[str, Any]:
    data: dict[str, Any] = {}
    if not _ADAPTER_DIR.exists():
        return data
    for name in (
        "default_adapter.json",
        "promoted_adapters.json",
        "safe_adapters.json",
        "ablation_adapters.json",
        "rejected_adapters.json",
    ):
        path = _ADAPTER_DIR / name
        data[name] = _load_json(path, {"missing": True}) if path.exists() else {"missing": True}
    return data


def _filter_registry(rows: list[dict[str, Any]], needle: str) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for row in rows:
        haystack = json.dumps(row, ensure_ascii=False)
        if needle in haystack:
            matched.append(row)
    matched.sort(key=lambda item: str(item.get("timestamp") or item.get("completed_at") or ""), reverse=True)
    return matched


def _generated_adapter_summary(regression: dict[str, Any]) -> dict[str, Any]:
    strict = ((regression.get("strict_benchmark") or {}).get("summary") or {})
    generated = ((regression.get("generated_benchmark") or {}).get("summary") or {})
    largest_strict = (regression.get("strict_benchmark") or {}).get("largest_drop_task") or {}
    largest_generated = ((regression.get("generated_benchmark") or {}).get("largest_drop_tasks") or [{}])[0]
    return {
        "adapter": "generated_candidate_v1",
        "status": "reject",
        "decision": regression.get("multi_benchmark_decision") or "regression",
        "strict": {
            "accepted_delta": strict.get("accepted_delta"),
            "avg_delta": strict.get("avg_delta"),
            "runtime_delta": strict.get("runtime_delta"),
            "largest_drop": {
                "id": largest_strict.get("id"),
                "delta": largest_strict.get("delta"),
            },
        },
        "generated": {
            "accepted_delta": generated.get("accepted_delta"),
            "avg_delta": generated.get("avg_delta"),
            "runtime_delta": generated.get("runtime_delta"),
            "largest_drop": {
                "id": largest_generated.get("id"),
                "delta": largest_generated.get("delta"),
            },
        },
        "pattern": "full generated corpus regressed strict and generated benchmarks; game_simulation dominated the damage",
    }


def _pattern_adapter_summary(multi: dict[str, Any]) -> dict[str, Any]:
    strict = multi.get("strict_benchmark") or {}
    generated = multi.get("generated_benchmark") or {}
    extras = multi.get("extra_benchmarks") or []
    pattern = next((row for row in extras if row.get("benchmark") == "pattern_only_benchmark_v1"), {})
    return {
        "adapter": "pattern_only_candidate_v1",
        "status": "reject",
        "decision": multi.get("decision") or "regression",
        "strict": {
            "accepted_delta": strict.get("accepted_delta"),
            "avg_delta": strict.get("avg_delta"),
            "runtime_delta": strict.get("runtime_delta"),
            "compile_delta": strict.get("compile_delta"),
        },
        "generated": {
            "accepted_delta": generated.get("accepted_delta"),
            "avg_delta": generated.get("avg_delta"),
            "runtime_delta": generated.get("runtime_delta"),
            "compile_delta": generated.get("compile_delta"),
        },
        "pattern_only": {
            "state": pattern.get("state") or pattern.get("verdict"),
            "accepted_delta": pattern.get("accepted_delta"),
            "avg_delta": pattern.get("avg_delta"),
            "runtime_delta": pattern.get("runtime_delta"),
        },
        "pattern": "pattern-only target benchmark did not improve, while strict and generated benchmarks regressed",
    }


def analyze() -> dict[str, Any]:
    multi = _load_json(_MULTI_REPORT)
    generated_regression = _load_json(_GENERATED_REGRESSION)
    generated_benchmark = _load_json(_GENERATED_BENCHMARK_ANALYSIS)
    promotion_gate = _load_json(_PROMOTION_GATE)
    registry_rows = _safe_registry_rows()

    adapters = [
        _generated_adapter_summary(generated_regression),
        _pattern_adapter_summary(multi),
    ]
    experiments = {
        "generated_candidate_v1": _filter_registry(registry_rows, "generated_candidate_v1"),
        "pattern_only_candidate_v1": _filter_registry(registry_rows, "pattern_only_candidate_v1"),
    }

    return {
        "timestamp": _now(),
        "status": "synthetic_training_route_frozen",
        "route_frozen": True,
        "synthetic_experiments_summary": {
            "generated_corpus_records": (promotion_gate.get("metrics") or {}).get("records"),
            "generated_benchmark": {
                "run_id": generated_benchmark.get("run_id"),
                "tasks": generated_benchmark.get("tasks"),
                "accepted": generated_benchmark.get("accepted"),
                "rejected": generated_benchmark.get("rejected"),
                "avg_score": generated_benchmark.get("avg_score"),
            },
            "promotion_gate_decision": promotion_gate.get("decision"),
            "promotion_gate_note": (
                "Candidate-training-ready was a permission to run guarded experiments, "
                "not evidence that synthetic SFT would improve LoRA behavior."
            ),
        },
        "adapters": adapters,
        "regression_patterns": [
            "generated_candidate_v1: strict regression and generated regression",
            "pattern_only_candidate_v1: pattern_only benchmark no_change, but strict and generated benchmarks regress",
            "Synthetic training signal did not transfer safely even when reference solutions were compile/runtime/semantic validated",
        ],
        "conclusion": {
            "do_not_continue_synthetic_lora_training_for_now": True,
            "keep_datasets_as_isolated_evaluation_assets": True,
            "use_generated_benchmark_for_stress_testing_not_training": True,
            "lesson": "validated synthetic solutions do not guarantee useful SFT signal",
        },
        "recommended_next_path": [
            "Run a dataset audit before any further synthetic training.",
            "Prioritize human-curated goldens for repair targets.",
            "Explore task-specific adapter routing instead of one synthetic LoRA.",
            "Improve prompt/profile behavior before more LoRA experiments.",
            "Expand real exam-style verified corpus rather than synthetic-only corpus.",
        ],
        "experiment_registry_matches": experiments,
        "adapter_registry_snapshot": _adapter_registry(),
        "inputs": {
            "multi_benchmark_report": str(_MULTI_REPORT),
            "generated_candidate_regression_analysis": str(_GENERATED_REGRESSION),
            "generated_benchmark_analysis": str(_GENERATED_BENCHMARK_ANALYSIS),
            "promotion_gate": str(_PROMOTION_GATE),
        },
        "side_effects": "reports_and_docs_only",
    }


def _md_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        lines.append("| " + " | ".join(str(item) for item in row) + " |")
    return lines


def _markdown(report: dict[str, Any]) -> str:
    summary = report["synthetic_experiments_summary"]
    bench = summary["generated_benchmark"]
    lines: list[str] = []
    a = lines.append
    a("# Synthetic Training Summary")
    a("")
    a(f"Generated: `{report['timestamp']}`")
    a("Status: **synthetic_training_route_frozen**")
    a("")
    a("## Corpus And Benchmark")
    a("")
    a(f"- Generated corpus records: {summary.get('generated_corpus_records')}")
    a(f"- Generated benchmark run: `{bench.get('run_id')}`")
    a(f"- Generated benchmark accepted: {bench.get('accepted')}/{bench.get('tasks')}")
    a(f"- Generated benchmark avg score: {bench.get('avg_score')}")
    a(f"- Promotion gate decision: `{summary.get('promotion_gate_decision')}`")
    a(f"- Gate note: {summary.get('promotion_gate_note')}")
    a("")
    a("## Adapter Status")
    a("")
    rows = []
    for adapter in report["adapters"]:
        rows.append(
            [
                adapter["adapter"],
                adapter["status"],
                adapter["decision"],
                adapter.get("strict", {}).get("avg_delta"),
                adapter.get("generated", {}).get("avg_delta"),
                (adapter.get("pattern_only") or {}).get("state", "n/a"),
            ]
        )
    lines.extend(_md_table(["Adapter", "Status", "Decision", "Strict Avg Delta", "Generated Avg Delta", "Pattern Benchmark"], rows))
    a("")
    a("## Regression Patterns")
    a("")
    for pattern in report["regression_patterns"]:
        a(f"- {pattern}")
    a("")
    a("## Conclusion")
    a("")
    conclusion = report["conclusion"]
    a("- Do not continue synthetic LoRA training for now.")
    a("- Keep generated datasets as isolated evaluation assets.")
    a("- Use the generated benchmark for stress testing, not training.")
    a(f"- Final lesson: {conclusion['lesson']}.")
    a("")
    a("## Recommended Next Path")
    a("")
    for item in report["recommended_next_path"]:
        a(f"- {item}")
    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any]) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _OUT_MD.write_text(_markdown(report), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize synthetic LoRA training outcomes")
    return parser.parse_args()


def main() -> None:
    _parse_args()
    try:
        report = analyze()
    except Exception as exc:
        print(f"[synthetic-summary] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    write_reports(report)
    print("[synthetic-summary] status=synthetic_training_route_frozen")
    print(f"[synthetic-summary] report >> {_OUT_MD}")


if __name__ == "__main__":
    main()
