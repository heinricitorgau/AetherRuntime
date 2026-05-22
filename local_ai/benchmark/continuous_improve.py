#!/usr/bin/env python3
"""Continuously generate, evaluate, and repair benchmark answers until Ctrl+C.

This runner is intentionally simple and resumable:
  - every model response is appended to raw_outputs.jsonl
  - every scored attempt is appended to attempts.jsonl
  - the best answer seen for each case is rewritten to best_cases.jsonl/report.json

It talks to the existing local proxy and reuses the benchmark scoring utilities.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_REPO_ROOT))

from _bench_common import (  # noqa: E402
    PROMPTS_DIR,
    REPORTS_DIR,
    call_proxy,
    check_keywords,
    check_output_tokens,
    check_structure,
    compile_code,
    compute_score,
    extract_c,
    find_compiler,
    is_truncated,
    load_prompt_file,
    now_iso,
    run_exe,
    run_ts,
    semantic_check,
)
from benchmark_cases import load_tasks  # noqa: E402

DEFAULT_PROXY = "http://127.0.0.1:8082"
DEFAULT_MODEL = "qwen2.5-coder:3b"
DEFAULT_MAX_TOKENS = 768
DEFAULT_TIMEOUT = 660
DEFAULT_RUN_TIMEOUT = 8
ACCEPT_THRESHOLD = 60


def check_summary(checks: dict[str, Any]) -> str:
    """Return a compact failure summary suitable for repair prompts and logs."""
    lines: list[str] = []
    for name in ("proxy", "truncation", "structure", "compile", "runtime", "semantic", "keyword"):
        check = checks.get(name, {})
        passed = bool(check.get("passed"))
        if passed:
            continue
        detail = (
            check.get("note")
            or check.get("message")
            or check.get("issues")
            or check.get("errors")
            or check.get("missing")
            or "failed"
        )
        if isinstance(detail, list):
            detail = "; ".join(str(item) for item in detail[:6])
        lines.append(f"- {name}: {detail}")
    return "\n".join(lines) if lines else "- no failed checks"


def build_repair_prompt(task: dict[str, Any], previous_code: str, result: dict[str, Any]) -> str:
    """Ask the model to improve a failed answer using deterministic checker feedback."""
    score = result.get("score", 0)
    failures = check_summary(result.get("checks", {}))
    return (
        "Improve the C answer for the same programming task.\n"
        "Return exactly one complete C99 program. Do not explain. Do not include markdown.\n\n"
        "Original task:\n"
        f"{task['instruction']}\n\n"
        f"Previous score: {score}/100\n"
        "Checker feedback:\n"
        f"{failures}\n\n"
        "Previous code:\n"
        f"{previous_code}\n\n"
        "Write a corrected complete C99 program now."
    )


def evaluate_text(
    *,
    task: dict[str, Any],
    raw_response: str,
    compiler: str | None,
    work_dir: Path,
    run_timeout: int,
) -> dict[str, Any]:
    """Score a raw model response using the same checks as the baseline runner."""
    code, extract_method = extract_c(raw_response)
    structure = check_structure(code) if code else {
        "ok": False,
        "score": 0.0,
        "issues": ["empty response"],
    }
    truncated = is_truncated(code) if code else True

    if compiler and code:
        compile_result = compile_code(code, task["id"], work_dir, compiler)
    else:
        reason = "no compiler available" if not compiler else "no code extracted"
        compile_result = {"ok": False, "message": reason, "errors": [], "warnings": [], "exe": None}

    if compile_result.get("exe"):
        runtime = run_exe(compile_result["exe"], task["sample_input"], timeout=run_timeout)
        output_tokens = check_output_tokens(runtime["output"], task["expected_tokens"])
        runtime_check = {
            "passed": runtime["ok"] and output_tokens["match_ratio"] > 0,
            "timed_out": runtime["timed_out"],
            "match_ratio": output_tokens["match_ratio"],
            "found": output_tokens["found"],
            "missing": output_tokens["missing"],
            "output_head": runtime["output"][:400],
        }
    else:
        runtime_check = {
            "passed": False,
            "timed_out": False,
            "match_ratio": 0.0,
            "found": [],
            "missing": task["expected_tokens"],
            "output_head": "",
            "note": "not run (compile failed or no compiler)",
        }

    keyword = check_keywords(code, task["expected_keywords"])
    semantic = semantic_check(code) if code else {
        "passed": False,
        "warnings": [],
        "errors": ["empty code"],
        "risk_score": 1.0,
    }
    score = compute_score(
        structure_score=float(structure["score"]),
        keyword_score=float(keyword["score"]),
        compile_ok=bool(compile_result["ok"]),
        runtime_ratio=float(runtime_check["match_ratio"]),
    )

    checks = {
        "truncation": {"passed": not truncated, "note": "ok" if not truncated else "truncated"},
        "structure": {
            "passed": bool(structure["ok"]),
            "score": structure["score"],
            "issues": structure.get("issues", []),
        },
        "compile": {
            "passed": bool(compile_result["ok"]),
            "message": compile_result["message"],
            "errors": compile_result.get("errors", [])[:5],
            "warnings": compile_result.get("warnings", [])[:3],
        },
        "runtime": runtime_check,
        "semantic": semantic,
        "keyword": {
            "passed": keyword["score"] >= 0.5 if task["expected_keywords"] else True,
            "score": keyword["score"],
            "found": keyword["found"],
            "missing": keyword["missing"],
        },
    }

    total = int(score["total"])
    return {
        "id": task["id"],
        "timestamp": now_iso(),
        "extract_method": extract_method,
        "extracted_code": code,
        "checks": checks,
        "score": total,
        "score_breakdown": score["breakdown"],
        "accepted": total >= ACCEPT_THRESHOLD,
        "task_meta": {
            "topic": task["topic"],
            "difficulty": task["difficulty"],
            "points": task["points"],
            "year": task["year"],
            "exam": task["exam"],
        },
    }


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_report(path: Path, *, best_by_case: dict[str, dict[str, Any]], meta: dict[str, Any]) -> None:
    best = list(best_by_case.values())
    accepted = sum(1 for item in best if item.get("accepted"))
    avg_score = round(sum(float(item.get("score", 0)) for item in best) / len(best), 2) if best else 0.0
    report = {
        "timestamp": now_iso(),
        "meta": meta,
        "cases_seen": len(best),
        "accepted": accepted,
        "average_best_score": avg_score,
        "best": best,
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def task_order(tasks: list[dict[str, Any]], shuffle: bool) -> list[dict[str, Any]]:
    ordered = list(tasks)
    if shuffle:
        random.shuffle(ordered)
    return ordered


def run_loop(args: argparse.Namespace) -> None:
    tasks = load_tasks(source=args.source, filter_ids=args.filter)
    if not tasks:
        print("[continuous] no tasks found", file=sys.stderr)
        sys.exit(1)

    prompt_path = Path(args.prompt_file) if args.prompt_file else PROMPTS_DIR / "code_gen_strict_v2.txt"
    system_prompt = (
        load_prompt_file(prompt_path)
        if prompt_path.exists()
        else "You are a C programming assistant. Output exactly one complete C99 program. Do not explain."
    )

    run_id = args.run_id or f"improve_{run_ts()}"
    out_dir = args.output_dir or REPORTS_DIR / "runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    compiler = None if args.no_compile else find_compiler()
    work_dir = Path(tempfile.mkdtemp(prefix="continuous_improve_"))
    best_by_case: dict[str, dict[str, Any]] = {}
    meta = {
        "run_id": run_id,
        "model": args.model,
        "proxy_url": args.proxy_url,
        "source": args.source,
        "filter": args.filter,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "timeout": args.timeout,
        "run_timeout": args.run_timeout,
        "max_repairs": args.max_repairs,
        "prompt_file": str(prompt_path),
        "compiler": compiler,
        "started_at": now_iso(),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[continuous] run_id={run_id} tasks={len(tasks)} model={args.model}")
    print(f"[continuous] output={out_dir}")
    print("[continuous] press Ctrl+C to stop; partial results are saved after every attempt")

    iteration = 0
    attempts_path = out_dir / "attempts.jsonl"
    raw_path = out_dir / "raw_outputs.jsonl"
    best_path = out_dir / "best_cases.jsonl"
    report_path = out_dir / "report.json"

    try:
        while True:
            for task in task_order(tasks, args.shuffle):
                iteration += 1
                prompt = task["instruction"]
                previous_code = ""
                best_for_task = best_by_case.get(task["id"])
                if best_for_task and not args.restart_each_cycle:
                    previous_code = best_for_task.get("extracted_code", "")
                    prompt = build_repair_prompt(task, previous_code, best_for_task)

                for repair_attempt in range(args.max_repairs + 1):
                    label = "generate" if repair_attempt == 0 and not previous_code else f"repair{repair_attempt}"
                    print(f"[{iteration}] {task['id']} {label} ...", end="", flush=True)
                    raw_response, proxy_error, latency_ms = call_proxy(
                        proxy_url=args.proxy_url,
                        model=args.model,
                        system=system_prompt,
                        user=prompt,
                        max_tokens=args.max_tokens,
                        timeout=args.timeout,
                        temperature=args.temperature,
                        skip_repair=True,
                    )
                    raw_record = {
                        "id": task["id"],
                        "iteration": iteration,
                        "repair_attempt": repair_attempt,
                        "timestamp": now_iso(),
                        "latency_ms": latency_ms,
                        "raw_response": raw_response,
                        "proxy_error": proxy_error,
                    }
                    append_jsonl(raw_path, raw_record)

                    if proxy_error:
                        result = {
                            "id": task["id"],
                            "timestamp": now_iso(),
                            "score": 0,
                            "accepted": False,
                            "checks": {"proxy": {"passed": False, "note": proxy_error}},
                            "extracted_code": "",
                        }
                    else:
                        result = evaluate_text(
                            task=task,
                            raw_response=raw_response,
                            compiler=compiler,
                            work_dir=work_dir,
                            run_timeout=args.run_timeout,
                        )
                        result["checks"]["proxy"] = {"passed": True, "note": "ok"}

                    result.update(
                        {
                            "model": args.model,
                            "iteration": iteration,
                            "repair_attempt": repair_attempt,
                            "latency_ms": latency_ms,
                        }
                    )
                    append_jsonl(attempts_path, result)

                    current_best = best_by_case.get(task["id"])
                    if current_best is None or int(result["score"]) >= int(current_best["score"]):
                        best_by_case[task["id"]] = result
                        write_jsonl(best_path, list(best_by_case.values()))
                        write_report(report_path, best_by_case=best_by_case, meta=meta)

                    status = "ACCEPT" if result["accepted"] else "try"
                    print(f" score={result['score']:3d} {status} {latency_ms}ms")

                    if result["accepted"] and args.stop_on_accepted:
                        break
                    if repair_attempt >= args.max_repairs:
                        break

                    previous_code = result.get("extracted_code", "") or raw_response
                    prompt = build_repair_prompt(task, previous_code, result)

                if args.sleep_seconds > 0:
                    time.sleep(args.sleep_seconds)
    except KeyboardInterrupt:
        print("\n[continuous] stopped by Ctrl+C")
    finally:
        meta["stopped_at"] = now_iso()
        (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        write_jsonl(best_path, list(best_by_case.values()))
        write_report(report_path, best_by_case=best_by_case, meta=meta)
        print(f"[continuous] saved report: {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Continuous model improvement loop")
    parser.add_argument("--source", default="test", help="Task source: test, accepted, all, or a JSONL path")
    parser.add_argument("--filter", "-f", nargs="*", help="Only run tasks whose id starts with these strings")
    parser.add_argument("--model", default=os.environ.get("CLAW_MODEL", "").strip() or DEFAULT_MODEL)
    parser.add_argument("--proxy-url", default=os.environ.get("CLAW_PROXY_URL", DEFAULT_PROXY))
    parser.add_argument("--max-tokens", type=int, default=int(os.environ.get("CLAW_BENCHMARK_MAX_TOKENS", DEFAULT_MAX_TOKENS)))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("CLAW_BENCHMARK_TIMEOUT_SECONDS", DEFAULT_TIMEOUT)))
    parser.add_argument("--run-timeout", type=int, default=DEFAULT_RUN_TIMEOUT)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-repairs", type=int, default=2, help="Repair attempts after each generation")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--prompt-file", default=None)
    parser.add_argument("--no-compile", action="store_true")
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument("--restart-each-cycle", action="store_true")
    parser.add_argument("--no-stop-on-accepted", dest="stop_on_accepted", action="store_false")
    parser.set_defaults(stop_on_accepted=True)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    args = parser.parse_args()
    run_loop(args)


if __name__ == "__main__":
    main()
