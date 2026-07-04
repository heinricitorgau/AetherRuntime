#!/usr/bin/env python3
"""Compare local coding models on stable benchmark profiles.

This script performs benchmark evaluation only. It does not train LoRA,
modify scoring, change routing policy, or promote datasets/adapters.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_REPO_ROOT = _LOCAL_AI.parent
_REPORT_DIR = _HERE / "reports"

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from promotion_policy import evaluate_comparison  # noqa: E402
_OUT_JSON = _REPORT_DIR / "model_comparison.json"
_OUT_MD = _REPORT_DIR / "model_comparison.md"
_RUNS_DIR = _LOCAL_AI / "benchmark" / "reports" / "runs"
_BENCHMARK_RUNNER = _LOCAL_AI / "benchmark" / "run_baseline.py"

BASELINE_ALIAS = "qwen25_coder_3b"
DEFAULT_BENCHMARKS = [
    "c_exam_2025_strict_seeded",
    "generated_c_tasks_v1",
]
DEFAULT_MODELS = [
    "qwen25_coder_3b",
    "qwen25_coder_14b",
    "qwen3_coder_30b",
]

MODEL_CATALOG: dict[str, dict[str, str]] = {
    "qwen25_coder_3b": {
        "display_name": "Qwen2.5-Coder-3B-Instruct",
        "hf_model": "Qwen/Qwen2.5-Coder-3B-Instruct",
        "ollama_model": "qwen2.5-coder:3b",
    },
    "qwen25_coder_14b": {
        "display_name": "Qwen2.5-Coder-14B-Instruct",
        "hf_model": "Qwen/Qwen2.5-Coder-14B-Instruct",
        "ollama_model": "qwen2.5-coder:14b",
    },
    "qwen3_coder_30b": {
        "display_name": "Qwen3-Coder-30B-A3B-Instruct",
        "hf_model": "Qwen/Qwen3-Coder-30B-A3B-Instruct",
        "ollama_model": "qwen3-coder:30b",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _http_json(url: str, timeout: int = 5) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def _proxy_preflight(proxy_url: str, attempts: int = 3, sleep_seconds: int = 2) -> dict[str, Any]:
    """Check proxy readiness without performing model discovery."""
    base_url = proxy_url.rstrip("/")
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            health = _http_json(f"{base_url}/health")
            config = _http_json(f"{base_url}/config")
            return {
                "proxy_url": proxy_url,
                "proxy_preflight_ok": True,
                "proxy_preflight_attempts": attempt,
                "proxy_health_status": health.get("status"),
                "proxy_model": config.get("configured_ollama_model")
                or config.get("configured_model")
                or config.get("model")
                or health.get("model"),
                "proxy_full_timeout": config.get("full_timeout")
                or config.get("configured_full_timeout")
                or config.get("effective_request_timeout"),
                "proxy_first_token_timeout": config.get("first_token_timeout")
                or config.get("effective_first_token_timeout"),
                "proxy_error": "",
            }
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < attempts:
                time.sleep(sleep_seconds)
    return {
        "proxy_url": proxy_url,
        "proxy_preflight_ok": False,
        "proxy_preflight_attempts": attempts,
        "proxy_health_status": None,
        "proxy_model": None,
        "proxy_full_timeout": None,
        "proxy_first_token_timeout": None,
        "proxy_error": last_error or "proxy preflight failed",
    }


def _benchmark_command(
    alias: str,
    benchmark: str,
    run_id: str,
    proxy_url: str,
    timeout: int,
) -> list[str]:
    return [
        sys.executable,
        str(_BENCHMARK_RUNNER),
        "--benchmark",
        benchmark,
        "--model-override",
        MODEL_CATALOG[alias]["ollama_model"],
        "--run-id",
        run_id,
        "--proxy-url",
        proxy_url,
        "--timeout",
        str(timeout),
    ]


def _metric_result(
    alias: str,
    benchmark: str,
    run_id: str,
    report: dict[str, Any],
    proxy_preflight: dict[str, Any],
) -> dict[str, Any]:
    rates = report.get("rates") or {}
    model_override_valid = report.get("model_override_valid")
    status = "invalid_model_override" if model_override_valid is False else "completed"
    result = {
        "model_alias": alias,
        "model": MODEL_CATALOG[alias]["display_name"],
        "ollama_model": MODEL_CATALOG[alias]["ollama_model"],
        "benchmark": benchmark,
        "run_id": run_id,
        "status": status,
        "tasks": int(report.get("cases_run") or 0),
        "accepted": int(report.get("accepted") or 0),
        "avg_score": float(report.get("average_score") or 0.0),
        "compile_rate": float(rates.get("compile_pass_rate") or 0.0),
        "runtime_rate": float(rates.get("runtime_pass_rate") or 0.0),
        "semantic_rate": float(rates.get("semantic_pass_rate") or 0.0),
        "requested_model": report.get("requested_model")
        or (report.get("meta") or {}).get("requested_model")
        or MODEL_CATALOG[alias]["ollama_model"],
        "effective_model": report.get("effective_model")
        or (report.get("meta") or {}).get("effective_model"),
        "proxy_config_model": report.get("proxy_config_model")
        or (report.get("meta") or {}).get("proxy_config_model"),
        "model_override_valid": model_override_valid,
        "report_path": str(_RUNS_DIR / run_id / "report.json"),
    }
    result.update(proxy_preflight)
    return result


def _run_benchmark(
    alias: str,
    benchmark: str,
    proxy_url: str,
    timeout: int,
    dry_run: bool,
) -> dict[str, Any]:
    run_id = f"model_eval_{alias}_{_safe_name(benchmark)}_{_run_stamp()}"
    command = _benchmark_command(alias, benchmark, run_id, proxy_url, timeout)
    proxy_preflight = {
        "proxy_url": proxy_url,
        "proxy_preflight_ok": None,
        "proxy_preflight_attempts": 0,
        "proxy_health_status": None,
        "proxy_model": None,
        "proxy_full_timeout": None,
        "proxy_first_token_timeout": None,
        "proxy_error": "",
    }
    print("[model-eval] $ " + subprocess.list2cmdline(command), flush=True)
    if dry_run:
        return {
            "model_alias": alias,
            "model": MODEL_CATALOG[alias]["display_name"],
            "ollama_model": MODEL_CATALOG[alias]["ollama_model"],
            "benchmark": benchmark,
            "run_id": run_id,
            "status": "planned",
            "command": command,
            "requested_model": MODEL_CATALOG[alias]["ollama_model"],
            "effective_model": None,
            "proxy_config_model": None,
            "model_override_valid": None,
            **proxy_preflight,
        }

    proxy_preflight = _proxy_preflight(proxy_url)
    if not proxy_preflight["proxy_preflight_ok"]:
        return {
            "model_alias": alias,
            "model": MODEL_CATALOG[alias]["display_name"],
            "ollama_model": MODEL_CATALOG[alias]["ollama_model"],
            "benchmark": benchmark,
            "run_id": run_id,
            "status": "proxy_unavailable",
            "error_message": "proxy preflight failed",
            "command": command,
            "requested_model": MODEL_CATALOG[alias]["ollama_model"],
            "effective_model": None,
            "proxy_config_model": proxy_preflight.get("proxy_model"),
            "model_override_valid": None,
            **proxy_preflight,
        }

    completed = subprocess.run(
        command,
        cwd=str(_REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    report_path = _RUNS_DIR / run_id / "report.json"
    if completed.returncode != 0 or not report_path.exists():
        error_parts = []
        if completed.returncode != 0:
            error_parts.append(f"benchmark subprocess exited with code {completed.returncode}")
        if not report_path.exists():
            error_parts.append("benchmark report was not produced")
        return {
            "model_alias": alias,
            "model": MODEL_CATALOG[alias]["display_name"],
            "ollama_model": MODEL_CATALOG[alias]["ollama_model"],
            "benchmark": benchmark,
            "run_id": run_id,
            "status": "benchmark_failed",
            "error_message": "; ".join(error_parts),
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
            "report_path": str(report_path),
            "requested_model": MODEL_CATALOG[alias]["ollama_model"],
            "effective_model": None,
            "proxy_config_model": proxy_preflight.get("proxy_model"),
            "model_override_valid": None,
            **proxy_preflight,
        }
    return _metric_result(alias, benchmark, run_id, _load_json(report_path, {}), proxy_preflight)


def _aggregate(alias: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [row for row in results if row.get("status") == "completed"]
    expected = len(results)
    tasks = sum(int(row.get("tasks") or 0) for row in completed)
    if completed and len(completed) < expected:
        status = "partial"
    elif completed and len(completed) == expected:
        status = "completed"
    elif results and all(row.get("status") == "planned" for row in results):
        status = "planned"
    elif results and all(row.get("status") == "proxy_unavailable" for row in results):
        status = "proxy_unavailable"
    elif results and all(row.get("status") == "invalid_model_override" for row in results):
        status = "invalid_model_override"
    elif results:
        status = "benchmark_failed"
    else:
        status = "no_results"

    def weighted(key: str) -> float | None:
        if not tasks:
            return None
        return round(
            sum(float(row.get(key) or 0.0) * int(row.get("tasks") or 0) for row in completed)
            / tasks,
            4,
        )

    return {
        "model_alias": alias,
        "model": MODEL_CATALOG[alias]["display_name"],
        "ollama_model": MODEL_CATALOG[alias]["ollama_model"],
        "status": status,
        "benchmarks_completed": len(completed),
        "benchmarks_expected": expected,
        "tasks": tasks,
        "accepted": sum(int(row.get("accepted") or 0) for row in completed),
        "avg_score": weighted("avg_score"),
        "compile_rate": weighted("compile_rate"),
        "runtime_rate": weighted("runtime_rate"),
        "semantic_rate": weighted("semantic_rate"),
    }


def _delta(value: Any, baseline: Any) -> float | int | None:
    if value is None or baseline is None:
        return None
    return round(float(value) - float(baseline), 4)


def _with_deltas(aggregates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baseline = next((row for row in aggregates if row["model_alias"] == BASELINE_ALIAS), None)
    for row in aggregates:
        row["vs_baseline"] = {
            "accepted_delta": _delta(row.get("accepted"), baseline.get("accepted") if baseline else None),
            "avg_score_delta": _delta(row.get("avg_score"), baseline.get("avg_score") if baseline else None),
            "compile_rate_delta": _delta(row.get("compile_rate"), baseline.get("compile_rate") if baseline else None),
            "runtime_rate_delta": _delta(row.get("runtime_rate"), baseline.get("runtime_rate") if baseline else None),
            "semantic_rate_delta": _delta(row.get("semantic_rate"), baseline.get("semantic_rate") if baseline else None),
        }
    return aggregates


def _comparison_answer(
    higher: dict[str, Any] | None,
    lower: dict[str, Any] | None,
    label: str,
) -> str:
    if not higher or not lower or higher.get("status") != "completed" or lower.get("status") != "completed":
        return f"{label}: insufficient completed benchmark data."
    return (
        f"{label}: avg score delta {_delta(higher['avg_score'], lower['avg_score']):+.2f}, "
        f"accepted delta {int(higher['accepted']) - int(lower['accepted']):+d}, "
        f"runtime delta {_delta(higher['runtime_rate'], lower['runtime_rate']):+.3f}."
    )


def _conclusions(
    aggregates: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    by_alias = {row["model_alias"]: row for row in aggregates}
    baseline = by_alias.get(BASELINE_ALIAS)
    model14 = by_alias.get("qwen25_coder_14b")
    model30 = by_alias.get("qwen3_coder_30b")

    q1 = _comparison_answer(model14, baseline, "14B vs 3B")
    q2 = _comparison_answer(model30, model14, "30B vs 14B")

    completed_larger = [
        row for row in (model14, model30)
        if row and row.get("status") == "completed"
    ]
    if not baseline or baseline.get("status") != "completed" or not completed_larger:
        q3 = "Insufficient evidence: larger-model benchmark runs are incomplete or failed."
    else:
        best = max(completed_larger, key=lambda row: float(row.get("avg_score") or 0.0))
        avg_gain = float(best.get("avg_score") or 0.0) - float(baseline.get("avg_score") or 0.0)
        runtime_gain = float(best.get("runtime_rate") or 0.0) - float(baseline.get("runtime_rate") or 0.0)
        if avg_gain >= 3.0 and runtime_gain >= 0:
            q3 = (
                "Model capability is the primary bottleneck: a larger model improves aggregate "
                "score without reducing runtime correctness."
            )
        elif avg_gain <= 1.0:
            q3 = (
                "Infrastructure/task/checker effects remain significant: larger models do not "
                "materially improve the same stable benchmarks."
            )
        else:
            q3 = "Mixed evidence: both model capability and benchmark/infrastructure effects contribute."

    # Recommendation is NOT hard-coded here. It is derived from the model
    # promotion policy (promotion_policy.evaluate_comparison), which weighs the
    # strict AND generated benchmarks together. A strict regression combined
    # with a material generated gain resolves to manual_review, not "stay on 3B".
    policy_decision = evaluate_comparison(
        {
            "baseline_model": BASELINE_ALIAS,
            "results": results,
            "models": aggregates,
        }
    )
    recommendation = policy_decision["recommendation"]
    reason = policy_decision["recommendation_reason"]
    promotion_decision = policy_decision["decision"]

    if promotion_decision == "promote_default":
        q4 = "Yes."
    elif promotion_decision == "manual_review":
        q4 = "Manual review."
    else:
        q4 = "Not yet."

    return {
        "q1_14b_vs_3b": q1,
        "q2_30b_vs_14b": q2,
        "q3_model_or_infrastructure": q3,
        "q4_upgrade_3b_to_14b": q4,
        "promotion_decision": promotion_decision,
        "recommendation": recommendation,
        "recommendation_reason": reason,
    }


def compare_models(
    aliases: list[str],
    benchmarks: list[str],
    proxy_url: str,
    ollama_url: str,
    timeout: int,
    dry_run: bool,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []

    for alias in aliases:
        for benchmark in benchmarks:
            results.append(_run_benchmark(alias, benchmark, proxy_url, timeout, dry_run))

    aggregates = _with_deltas(
        [_aggregate(alias, [row for row in results if row["model_alias"] == alias]) for alias in aliases]
    )
    return {
        "timestamp": _now(),
        "baseline_model": BASELINE_ALIAS,
        "models_requested": aliases,
        "benchmarks": benchmarks,
        "proxy_url": proxy_url,
        "ollama_url": ollama_url,
        "dry_run": dry_run,
        "execution_strategy": "direct_run_baseline_without_model_discovery",
        "results": results,
        "models": aggregates,
        "answers": _conclusions(aggregates, results),
        "guardrails": {
            "trains_lora": False,
            "changes_benchmark_scoring": False,
            "changes_routing_policy": False,
            "promotes_adapter": False,
            "promotes_synthetic_dataset": False,
        },
    }


def _fmt(value: Any, percent: bool = False) -> str:
    if value is None:
        return "-"
    if percent:
        return f"{float(value):.1%}"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Model Replacement Benchmark",
        "",
        f"Generated: `{report['timestamp']}`",
        f"Baseline: `{report['baseline_model']}`",
        "",
        "## Execution Strategy",
        "",
        "Models are not pre-filtered by `compare_models.py`. The script directly calls "
        "`run_baseline.py --model-override ...` and records benchmark subprocess failures "
        "as `benchmark_failed` without stopping the full comparison.",
        "",
        "Before each benchmark subprocess, the script checks proxy `/health` and `/config` "
        "with retry. If the proxy preflight fails, that benchmark is recorded as "
        "`proxy_unavailable` and the subprocess is not started.",
        "",
        "| Model | Ollama Model | Strategy |",
        "|-------|--------------|----------|",
    ]
    for alias in report["models_requested"]:
        lines.append(
            f"| {MODEL_CATALOG[alias]['display_name']} | "
            f"{MODEL_CATALOG[alias]['ollama_model']} | direct benchmark run |"
        )

    lines += [
        "",
        "## Aggregate Comparison",
        "",
        "| Model | Status | Tasks | Accepted | Avg Score | Compile | Runtime | Semantic | vs Baseline Avg |",
        "|-------|--------|------:|---------:|----------:|--------:|--------:|---------:|----------------:|",
    ]
    for row in report["models"]:
        lines.append(
            f"| {row['model']} | {row['status']} | {row['tasks']} | {row['accepted']} | "
            f"{_fmt(row['avg_score'])} | {_fmt(row['compile_rate'], True)} | "
            f"{_fmt(row['runtime_rate'], True)} | {_fmt(row['semantic_rate'], True)} | "
            f"{_fmt(row['vs_baseline']['avg_score_delta'])} |"
        )

    lines += [
        "",
        "## Per-Benchmark Results",
        "",
        "| Model | Benchmark | Status | Tasks | Accepted | Avg Score | Compile | Runtime | Semantic | Requested Model | Effective Model | Override Valid | Proxy OK | Proxy Model | Proxy Full Timeout | Proxy First Token Timeout | Error | Proxy Error |",
        "|-------|-----------|--------|------:|---------:|----------:|--------:|--------:|---------:|-----------------|-----------------|---------------:|---------:|-------------|-------------------:|--------------------------:|-------|-------------|",
    ]
    for row in report["results"]:
        error = str(row.get("error_message") or "").replace("|", "\\|")
        proxy_error = str(row.get("proxy_error") or "").replace("|", "\\|")
        lines.append(
            f"| {row['model']} | {row['benchmark']} | {row['status']} | "
            f"{row.get('tasks', '-')} | {row.get('accepted', '-')} | {_fmt(row.get('avg_score'))} | "
            f"{_fmt(row.get('compile_rate'), True)} | {_fmt(row.get('runtime_rate'), True)} | "
            f"{_fmt(row.get('semantic_rate'), True)} | {row.get('requested_model') or '-'} | "
            f"{row.get('effective_model') or '-'} | {_fmt(row.get('model_override_valid'))} | "
            f"{_fmt(row.get('proxy_preflight_ok'))} | "
            f"{row.get('proxy_model') or '-'} | {_fmt(row.get('proxy_full_timeout'))} | "
            f"{_fmt(row.get('proxy_first_token_timeout'))} | {error} | {proxy_error} |"
        )

    answers = report["answers"]
    lines += [
        "",
        "## Questions",
        "",
        f"- Q1: {answers['q1_14b_vs_3b']}",
        f"- Q2: {answers['q2_30b_vs_14b']}",
        f"- Q3: {answers['q3_model_or_infrastructure']}",
        f"- Q4: {answers['q4_upgrade_3b_to_14b']}",
        "",
        "## Recommendation",
        "",
        f"**{answers['recommendation']}**",
        "",
        answers["recommendation_reason"],
        "",
        "## Guardrails",
        "",
        "- Benchmark evaluation only; no LoRA training.",
        "- Benchmark scoring unchanged.",
        "- Routing policy unchanged.",
        "- No adapter or synthetic dataset promotion.",
    ]
    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any]) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _OUT_MD.write_text(_markdown(report), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare local coding models on stable benchmarks")
    parser.add_argument("--models", nargs="+", choices=sorted(MODEL_CATALOG), default=DEFAULT_MODELS)
    parser.add_argument("--benchmarks", nargs="+", default=DEFAULT_BENCHMARKS)
    parser.add_argument("--proxy-url", default=os.environ.get("CLAW_PROXY_URL", "http://127.0.0.1:8082"))
    parser.add_argument("--ollama-url", default=os.environ.get("CLAW_OLLAMA_URL", "http://127.0.0.1:11435"))
    parser.add_argument("--timeout", type=int, default=660)
    parser.add_argument("--dry-run", action="store_true", help="Write a planned comparison without running benchmarks")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        report = compare_models(
            aliases=args.models,
            benchmarks=args.benchmarks,
            proxy_url=args.proxy_url,
            ollama_url=args.ollama_url,
            timeout=args.timeout,
            dry_run=args.dry_run,
        )
        write_reports(report)
    except Exception as exc:
        print(f"[model-eval] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"[model-eval] recommendation={report['answers']['recommendation']}")
    print(f"[model-eval] report >> {_OUT_MD}")


if __name__ == "__main__":
    main()
