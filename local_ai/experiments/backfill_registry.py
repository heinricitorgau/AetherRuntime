#!/usr/bin/env python3
"""Backfill experiment registry entries from existing benchmark run reports."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from local_ai.experiments.register_run import REGISTRY_DIR, register_run
from local_ai.shared.paths import BENCHMARK_REPORTS, CONFIG_DIR, GOLDEN_DIR


RUNS_DIR = BENCHMARK_REPORTS / "runs"
GOLDEN_FILE = GOLDEN_DIR / "golden_baseline.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_load_json(path: Path) -> dict[str, Any]:
    try:
        return _load_json(path)
    except Exception:
        return {}


def _load_config(name: str) -> dict[str, Any]:
    return _safe_load_json(CONFIG_DIR / f"{name}.json")


def _registry_path(run_id: str) -> Path:
    return REGISTRY_DIR / f"{run_id}.json"


def _model_profile_for_report(report: dict[str, Any]) -> str | None:
    model_name = (
        report.get("model")
        or report.get("meta", {}).get("model")
        or ""
    )
    models = _load_config("models")
    for profile_name, profile in models.items():
        if model_name in {
            profile.get("ollama_model"),
            profile.get("hf_model"),
        }:
            return profile_name
    return None


def _task_ids(report: dict[str, Any]) -> list[str]:
    return [str(item.get("id") or "") for item in report.get("results", [])]


def _benchmark_profile_for_report(report: dict[str, Any], model_profile: str | None) -> str | None:
    task_ids = _task_ids(report)
    cases_run = int(report.get("cases_run") or len(task_ids) or 0)
    benchmarks = _load_config("benchmarks")
    meta_prompt = str(report.get("meta", {}).get("prompt_profile") or "")
    strict_version = str(report.get("meta", {}).get("strict_prompt_version") or "")

    if cases_run == 4 and any(tid.startswith("2025_midterm_") for tid in task_ids):
        if "c_exam_2025_strict_seeded" in benchmarks:
            return "c_exam_2025_strict_seeded"
    if cases_run == 16 and any("_exam2_" in tid for tid in task_ids):
        if "c_exam2_all_strict_seeded" in benchmarks:
            return "c_exam2_all_strict_seeded"

    for profile_name, profile in benchmarks.items():
        if model_profile and profile.get("model") != model_profile:
            continue
        prompt_profile = str(profile.get("prompt_profile") or "")
        if meta_prompt == "strict_code_only" and "strict_code_only" in prompt_profile:
            if strict_version and strict_version not in prompt_profile:
                continue
            return profile_name
    return None


def _dataset_profile_for_benchmark(benchmark_profile: str | None) -> str | None:
    if not benchmark_profile:
        return None
    profile = _load_config("benchmarks").get(benchmark_profile, {})
    dataset = profile.get("dataset")
    return str(dataset) if dataset else None


def _timeout_rate(report: dict[str, Any]) -> float:
    results = report.get("results", [])
    if not results:
        return 0.0
    timed_out = 0
    for result in results:
        checks = result.get("checks", {})
        if (
            checks.get("proxy", {}).get("timed_out")
            or checks.get("runtime", {}).get("timed_out")
        ):
            timed_out += 1
    return round(timed_out / len(results), 3)


def _metadata_from_report(run_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    # The run directory is the stable benchmark run identity. Some early
    # reports used a generic internal run_id such as "run", which is not
    # suitable for a searchable registry key.
    run_id = run_dir.name
    rates = report.get("rates", {})
    meta = report.get("meta", {})
    model_profile = _model_profile_for_report(report)
    benchmark_profile = _benchmark_profile_for_report(report, model_profile)
    dataset_profile = _dataset_profile_for_benchmark(benchmark_profile)

    return {
        "run_id": run_id,
        "timestamp": report.get("timestamp"),
        "run_type": "benchmark",
        "model_profile": model_profile,
        "model": report.get("model") or meta.get("model"),
        "benchmark_profile": benchmark_profile,
        "dataset_profile": dataset_profile,
        "accepted": report.get("accepted"),
        "cases_run": report.get("cases_run"),
        "avg_score": report.get("average_score"),
        "compile_rate": rates.get("compile_pass_rate"),
        "runtime_rate": rates.get("runtime_pass_rate"),
        "semantic_rate": rates.get("semantic_pass_rate"),
        "keyword_rate": rates.get("keyword_pass_rate"),
        "timeout_rate": _timeout_rate(report),
        "strict_code_only": meta.get("strict_code_only"),
        "prompt_profile": meta.get("prompt_profile"),
        "strict_prompt_version": meta.get("strict_prompt_version"),
        "backfilled_from": str(run_dir / "report.json"),
        "linked_reports": {
            "run_report_json": str(run_dir / "report.json"),
            "run_report_md": str(run_dir / "report.md"),
            "results_jsonl": str(run_dir / "results.jsonl"),
            "raw_outputs_jsonl": str(run_dir / "raw_outputs.jsonl"),
        },
        "config_profiles": {
            "benchmark": benchmark_profile,
            "model": model_profile,
            "dataset": dataset_profile,
            "prompt": meta.get("prompt_profile"),
            "strict_prompt_version": meta.get("strict_prompt_version"),
        },
    }


def _golden_run_id() -> str | None:
    golden = _safe_load_json(GOLDEN_FILE)
    run_id = golden.get("run_id")
    return str(run_id) if run_id else None


def backfill_registry(*, dry_run: bool = False) -> dict[str, Any]:
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    skipped: list[str] = []
    missing_reports: list[str] = []
    errors: list[dict[str, str]] = []
    golden_run_id = _golden_run_id()
    golden_registered = False

    if not RUNS_DIR.exists():
        return {
            "created": created,
            "skipped": skipped,
            "missing_reports": [str(RUNS_DIR)],
            "errors": errors,
            "golden_run_id": golden_run_id,
            "golden_registered": False,
        }

    for run_dir in sorted(p for p in RUNS_DIR.iterdir() if p.is_dir()):
        report_path = run_dir / "report.json"
        if not report_path.exists():
            missing_reports.append(str(report_path))
            continue
        try:
            report = _load_json(report_path)
            metadata = _metadata_from_report(run_dir, report)
            run_id = str(metadata["run_id"])
            if _registry_path(run_id).exists():
                skipped.append(run_id)
                if golden_run_id == run_id:
                    golden_registered = True
                continue
            if not dry_run:
                registered = register_run(metadata)
                created.append(str(registered["run_id"]))
                if golden_run_id == registered["run_id"]:
                    golden_registered = True
            else:
                created.append(run_id)
                if golden_run_id == run_id:
                    golden_registered = True
        except Exception as exc:
            errors.append({"run_dir": str(run_dir), "error": str(exc)})

    if golden_run_id and _registry_path(golden_run_id).exists():
        golden_registered = True

    return {
        "created": created,
        "skipped": skipped,
        "missing_reports": missing_reports,
        "errors": errors,
        "golden_run_id": golden_run_id,
        "golden_registered": golden_registered,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill experiment registry from benchmark reports")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created")
    args = parser.parse_args()

    result = backfill_registry(dry_run=args.dry_run)
    print(f"[backfill] created={len(result['created'])} skipped={len(result['skipped'])} errors={len(result['errors'])}")
    if result["golden_run_id"]:
        status = "yes" if result["golden_registered"] else "no"
        print(f"[backfill] golden_run_id={result['golden_run_id']} registered={status}")
    for run_id in result["created"]:
        marker = "would create" if args.dry_run else "created"
        print(f"  {marker}: {run_id}")
    for err in result["errors"]:
        print(f"  ERROR {err['run_dir']}: {err['error']}", file=sys.stderr)
    if result["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
