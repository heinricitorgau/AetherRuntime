#!/usr/bin/env python3
"""Run compiled executables with sample inputs and check outputs.

Depends on compile_report.json existing (run compile_validator first).
Writes reports/runtime_report.json.

Usage:
    python local_ai/training_quality/runtime_validator.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from _common import (
    load_code_gen_records,
    load_eval_case,
    load_report,
    now_iso,
    write_report,
)


# ── Core run ───────────────────────────────────────────────────────────────

def run_one(exe: str, sample_input: str, timeout: int = 8) -> dict:
    stdin_data = sample_input if sample_input.endswith("\n") else sample_input + "\n"
    # Replace literal \n escape sequences from JSON strings
    stdin_data = stdin_data.replace("\\n", "\n")
    try:
        result = subprocess.run(
            [exe],
            input=stdin_data,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        output = (result.stdout + result.stderr).strip()
        return {"ok": result.returncode == 0, "output": output[:2000], "timed_out": False}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": f"timeout after {timeout}s", "timed_out": True}
    except Exception as exc:
        return {"ok": False, "output": str(exc)[:200], "timed_out": False}


def _check_output(output: str, case: dict) -> dict:
    """Check output against expected_behavior."""
    behavior = case.get("expected_behavior", {})
    expected_tokens = behavior.get("output_contains", [])

    found = [str(t) for t in expected_tokens if str(t).lower() in output.lower()]
    missing = [str(t) for t in expected_tokens if str(t).lower() not in output.lower()]

    score = len(found) / len(expected_tokens) if expected_tokens else 1.0
    return {
        "expected_tokens": expected_tokens,
        "found": found,
        "missing": missing,
        "match_score": round(score, 3),
    }


# ── Batch ──────────────────────────────────────────────────────────────────

def run(timeout: int = 8) -> dict:
    compile_report = load_report("compile_report.json")
    if not compile_report:
        print("[runtime] compile_report.json not found — run compile_validator first", file=sys.stderr)
        sys.exit(1)

    exe_map = {r["id"]: r["exe"] for r in compile_report.get("results", []) if r.get("exe")}

    records = load_code_gen_records()
    results = []

    for rec in records:
        case_id = rec["id"]
        exe = exe_map.get(case_id)
        if not exe:
            results.append({"id": case_id, "ok": False, "message": "no executable (compile failed)", "output": "", "match": {}})
            continue

        case = load_eval_case(case_id)
        sample_input = str(case.get("sample_input", ""))
        run_result = run_one(exe, sample_input, timeout=timeout)

        match = _check_output(run_result["output"], case)
        ok = run_result["ok"] and match["match_score"] > 0

        status = "ok" if ok else ("TIMEOUT" if run_result["timed_out"] else "FAIL")
        print(f"  [{status}] {case_id}  match={match['match_score']:.2f}  missing={match['missing']}")
        results.append({
            "id": case_id,
            "ok": ok,
            "timed_out": run_result["timed_out"],
            "output": run_result["output"],
            "match": match,
        })

    passed = sum(1 for r in results if r["ok"])
    report = {
        "validator": "runtime",
        "timestamp": now_iso(),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    path = write_report(report, "runtime_report.json")
    print(f"\n[runtime] {passed}/{len(results)} passed  -> {path}")
    return report


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Runtime-validate compiled training records")
    parser.add_argument("--timeout", type=int, default=8)
    args = parser.parse_args()
    run(timeout=args.timeout)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
