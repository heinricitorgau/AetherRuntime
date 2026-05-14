#!/usr/bin/env python3
"""Check that generated C code contains required keywords from the eval case.

Checks two layers:
  1. checker_rules.keywords  — C constructs the solution must use (scanf, for, etc.)
  2. expected_behavior.output_contains — strings the program output must produce
     (checked statically: are they present in string literals or printf calls?)

Writes reports/keyword_report.json.

Usage:
    python local_ai/training_quality/keyword_validator.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from _common import (
    load_code_gen_records,
    load_eval_case,
    now_iso,
    record_code,
    write_report,
)


def _check_code_keywords(code: str, keywords: list[str]) -> dict:
    lower = code.lower()
    found   = [k for k in keywords if str(k).lower() in lower]
    missing = [k for k in keywords if str(k).lower() not in lower]
    score = len(found) / len(keywords) if keywords else 1.0
    return {"required": keywords, "found": found, "missing": missing, "score": round(score, 3)}


def _check_output_literals(code: str, tokens: list[str]) -> dict:
    """Check that expected output tokens appear in string literals inside printf/puts calls."""
    # Extract string literal content from the code
    string_contents = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', code)
    all_strings = " ".join(string_contents).lower()

    found   = [t for t in tokens if str(t).lower() in all_strings]
    missing = [t for t in tokens if str(t).lower() not in all_strings]
    score = len(found) / len(tokens) if tokens else 1.0
    return {"expected": tokens, "found": found, "missing": missing, "score": round(score, 3)}


def validate_one(rec: dict, case: dict) -> dict:
    code = record_code(rec)
    checker = case.get("checker_rules", {})
    behavior = case.get("expected_behavior", {})

    code_keywords = checker.get("keywords", [])
    output_tokens = behavior.get("output_contains", [])

    code_check   = _check_code_keywords(code, code_keywords)
    output_check = _check_output_literals(code, output_tokens)

    combined_score = (code_check["score"] + output_check["score"]) / 2 if (code_keywords or output_tokens) else 1.0
    ok = combined_score >= 0.5

    return {
        "id": rec["id"],
        "ok": ok,
        "combined_score": round(combined_score, 3),
        "code_keywords": code_check,
        "output_literals": output_check,
    }


def run() -> dict:
    records = load_code_gen_records()
    results = []

    for rec in records:
        case = load_eval_case(rec["id"])
        if not case:
            results.append({"id": rec["id"], "ok": False, "combined_score": 0.0,
                            "code_keywords": {}, "output_literals": {}, "note": "eval case not found"})
            continue

        r = validate_one(rec, case)
        status = "ok" if r["ok"] else "FAIL"
        missing_kw = r["code_keywords"].get("missing", [])
        print(f"  [{status}] {rec['id']}  score={r['combined_score']:.2f}  missing_kw={missing_kw}")
        results.append(r)

    passed = sum(1 for r in results if r["ok"])
    report = {
        "validator": "keyword",
        "timestamp": now_iso(),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    path = write_report(report, "keyword_report.json")
    print(f"\n[keyword] {passed}/{len(results)} passed  -> {path}")
    return report


def main() -> None:
    run()


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
