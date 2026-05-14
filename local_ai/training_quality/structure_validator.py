#!/usr/bin/env python3
"""Static structural analysis of generated C code.

Checks (no compiler needed):
  - has #include directives
  - has int main()
  - balanced braces {}
  - balanced parentheses ()
  - no truncation markers (code ends mid-expression)
  - scanf format specifiers match argument count
  - no obvious placeholder text (TODO, FIXME, ...)
  - at least one loop or conditional (for exam problems)

Writes reports/structure_report.json.

Usage:
    python local_ai/training_quality/structure_validator.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from _common import (
    load_code_gen_records,
    now_iso,
    record_code,
    write_report,
)


# ── Individual checks ──────────────────────────────────────────────────────

def _mask_strings_and_comments(code: str) -> str:
    """Replace string literals and comments with spaces (preserving length)."""
    result = list(code)
    i = 0
    while i < len(result):
        ch = code[i]
        if code[i:i+2] == "//":
            j = code.find("\n", i)
            end = j if j >= 0 else len(code)
            for k in range(i, end):
                result[k] = " "
            i = end
        elif code[i:i+2] == "/*":
            j = code.find("*/", i + 2)
            end = j + 2 if j >= 0 else len(code)
            for k in range(i, end):
                result[k] = " "
            i = end
        elif ch == '"':
            j = i + 1
            while j < len(code) and code[j] != '"':
                if code[j] == "\\":
                    j += 1
                j += 1
            for k in range(i, min(j + 1, len(code))):
                result[k] = " "
            i = j + 1
        else:
            i += 1
    return "".join(result)


def check_has_include(code: str) -> tuple[bool, str]:
    ok = "#include" in code
    return ok, "" if ok else "missing #include"


def check_has_main(code: str) -> tuple[bool, str]:
    ok = bool(re.search(r"\bint\s+main\s*\(", code))
    return ok, "" if ok else "missing int main()"


def check_balanced_braces(code: str) -> tuple[bool, str]:
    masked = _mask_strings_and_comments(code)
    depth = 0
    for ch in masked:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False, "unmatched closing brace"
    ok = depth == 0
    return ok, "" if ok else f"unbalanced braces (net depth={depth})"


def check_balanced_parens(code: str) -> tuple[bool, str]:
    masked = _mask_strings_and_comments(code)
    depth = 0
    for ch in masked:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False, "unmatched closing paren"
    ok = depth == 0
    return ok, "" if ok else f"unbalanced parens (net depth={depth})"


def check_not_truncated(code: str) -> tuple[bool, str]:
    stripped = code.rstrip()
    if not stripped:
        return False, "empty code"
    last_char = stripped[-1]
    if last_char not in ("}", ";"):
        return False, f"code ends with {last_char!r} — likely truncated"
    # Heuristic: code ending mid-identifier (e.g. "c = sqrt((x4")
    if re.search(r"\w$", stripped) and last_char not in ("}",):
        return False, "code may be truncated (ends mid-token)"
    return True, ""


def check_no_placeholders(code: str) -> tuple[bool, str]:
    patterns = [r"\bTODO\b", r"\bFIXME\b", r"\bXXX\b", r"\.\.\.", r"<your code here>", r"<fill in>"]
    found = [p for p in patterns if re.search(p, code, re.IGNORECASE)]
    ok = len(found) == 0
    return ok, "" if ok else f"placeholder text found: {found}"


def check_has_control_flow(code: str) -> tuple[bool, str]:
    has = bool(re.search(r"\b(for|while|if)\s*\(", code))
    return has, "" if has else "no loops or conditionals found"


def check_scanf_format(code: str) -> tuple[bool, str]:
    """Rough check: scanf/fscanf format string specifier count vs argument count."""
    issues = []
    for m in re.finditer(r'\bscanf\s*\(\s*"([^"]*)"(.*?)\);', code, re.DOTALL):
        fmt, args_str = m.group(1), m.group(2)
        specifiers = re.findall(r"%[^%\s]", fmt)
        args = [a.strip() for a in args_str.split(",") if a.strip()]
        if specifiers and len(args) != len(specifiers):
            issues.append(
                f"scanf format has {len(specifiers)} specifiers but {len(args)} args"
            )
    ok = len(issues) == 0
    return ok, "; ".join(issues) if issues else ""


# ── Aggregate ──────────────────────────────────────────────────────────────

_CHECKS = [
    ("has_include",       check_has_include,       True),   # (name, fn, blocking)
    ("has_main",          check_has_main,           True),
    ("balanced_braces",   check_balanced_braces,    True),
    ("balanced_parens",   check_balanced_parens,    True),
    ("not_truncated",     check_not_truncated,      True),
    ("no_placeholders",   check_no_placeholders,    False),
    ("has_control_flow",  check_has_control_flow,   False),
    ("scanf_format",      check_scanf_format,       False),
]


def validate_one(rec: dict) -> dict:
    code = record_code(rec)
    checks = {}
    issues = []
    blocking_fail = False

    for name, fn, blocking in _CHECKS:
        ok, msg = fn(code)
        checks[name] = {"ok": ok, "msg": msg}
        if not ok:
            issues.append(msg or name)
            if blocking:
                blocking_fail = True

    total    = len(_CHECKS)
    passed   = sum(1 for c in checks.values() if c["ok"])
    score    = passed / total
    ok_final = not blocking_fail and score >= 0.625  # at least 5/8 checks

    return {
        "id":      rec["id"],
        "ok":      ok_final,
        "score":   round(score, 3),
        "issues":  issues,
        "checks":  checks,
    }


def run() -> dict:
    records = load_code_gen_records()
    results = []

    for rec in records:
        r = validate_one(rec)
        status = "ok" if r["ok"] else "FAIL"
        print(f"  [{status}] {rec['id']}  score={r['score']:.2f}  issues={r['issues']}")
        results.append(r)

    passed = sum(1 for r in results if r["ok"])
    report = {
        "validator": "structure",
        "timestamp": now_iso(),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    path = write_report(report, "structure_report.json")
    print(f"\n[structure] {passed}/{len(results)} passed  -> {path}")
    return report


def main() -> None:
    run()


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
