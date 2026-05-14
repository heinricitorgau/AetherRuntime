"""Conservative regex/heuristic static analysis of C code.

No external dependencies.  Does NOT try to be a full C parser.
- Returns errors only when the evidence is strong.
- Returns warnings for patterns that are suspicious but not conclusive.

Public API
----------
analyse(code: str) -> AnalysisResult
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ── Data types ─────────────────────────────────────────────────────────────

@dataclass
class AnalysisResult:
    semantic_pass: bool
    risk_score: float          # 0.0 = clean, 1.0 = very risky
    warnings: list[str] = field(default_factory=list)
    errors: list[str]   = field(default_factory=list)
    signals: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "semantic_pass": self.semantic_pass,
            "risk_score": round(self.risk_score, 3),
            "warnings": self.warnings,
            "errors":   self.errors,
            "signals":  self.signals,
        }


# ── Comment/string masking ─────────────────────────────────────────────────

def _mask(code: str) -> str:
    """Replace string literals and comments with spaces (same length)."""
    out = list(code)
    i = 0
    while i < len(code):
        if code[i:i+2] == "//":
            j = code.find("\n", i)
            end = j if j >= 0 else len(code)
            for k in range(i, end):
                out[k] = " "
            i = end
        elif code[i:i+2] == "/*":
            j = code.find("*/", i + 2)
            end = (j + 2) if j >= 0 else len(code)
            for k in range(i, end):
                out[k] = " "
            i = end
        elif code[i] == '"':
            j = i + 1
            while j < len(code):
                if code[j] == "\\" :
                    j += 2
                    continue
                if code[j] == '"':
                    break
                j += 1
            for k in range(i, min(j + 1, len(code))):
                out[k] = " "
            i = j + 1
        elif code[i] == "'":
            j = i + 1
            if j < len(code) and code[j] == "\\":
                j += 2
            else:
                j += 1
            if j < len(code) and code[j] == "'":
                j += 1
            for k in range(i, j):
                out[k] = " "
            i = j
        else:
            i += 1
    return "".join(out)


# ── Declaration helpers ────────────────────────────────────────────────────

def _declared_vars(code: str) -> dict[str, str]:
    """
    Very rough: collect {varname: type_string} from simple declarations.
    Only catches: int x; float y; char z; char buf[N]; int arr[N];
    """
    result: dict[str, str] = {}
    pat = re.compile(
        r"\b(int|float|double|char|long|unsigned|short)\s+"
        r"(\*?\s*\w+)\s*(?:\[([^\]]*)\])?\s*(?:=|;|,|\))",
    )
    for m in pat.finditer(_mask(code)):
        base_type = m.group(1)
        varname   = m.group(2).lstrip("*").strip()
        array_dim = m.group(3)  # None if not an array
        full_type = base_type + ("[]" if array_dim is not None else "")
        result[varname] = full_type
    return result


# ── Individual checks ──────────────────────────────────────────────────────

def _check_markdown_fence(code: str) -> list[str]:
    if "```" in code:
        return ["code still contains markdown fence (```)"]
    return []


def _check_missing_return(code: str) -> list[str]:
    masked = _mask(code)
    # Find main body
    main_m = re.search(r"\bint\s+main\s*\([^)]*\)\s*\{", masked)
    if not main_m:
        return []
    body = code[main_m.end():]
    if "return" not in body:
        return ["main() has no return statement"]
    return []


def _check_scanf_string_to_non_array(code: str) -> tuple[list[str], list[str]]:
    """scanf(\"%s\", ...) writing to a non-char-array variable."""
    warnings: list[str] = []
    errors:   list[str] = []
    decls = _declared_vars(code)

    for m in re.finditer(r'\bscanf\s*\(\s*"([^"]*)"([^)]*)\)', code):
        fmt   = m.group(1)
        args  = m.group(2)
        specs = re.findall(r"%[^%\s*]", fmt)
        arg_list = [a.strip().lstrip("&") for a in args.split(",") if a.strip()]

        for spec, arg in zip(specs, arg_list):
            varname = re.sub(r"[\[\]&* ]", "", arg)
            declared = decls.get(varname)
            if spec == "%s":
                # Must be char[]
                if declared and declared != "char[]":
                    errors.append(f"scanf(\"%s\") into non-char variable '{varname}' (declared as {declared})")
                elif not declared:
                    warnings.append(f"scanf(\"%s\") into '{varname}' — type unknown, check manually")
            elif spec in ("%d", "%i"):
                if declared and "float" in declared or declared == "double":
                    errors.append(f"scanf(\"%d\") into float/double variable '{varname}'")
            elif spec in ("%f", "%lf"):
                if declared and declared == "int":
                    errors.append(f"scanf(\"{spec}\") into int variable '{varname}'")

    return warnings, errors


def _check_strcmp_usage(code: str) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors:   list[str] = []

    if "strcmp" not in code:
        return warnings, errors

    has_string_h = "#include <string.h>" in code or '#include "string.h"' in code
    if not has_string_h:
        warnings.append("strcmp used but #include <string.h> not found")

    decls = _declared_vars(code)
    for m in re.finditer(r"\bstrcmp\s*\(\s*([^,)]+),\s*([^)]+)\)", _mask(code)):
        for raw_arg in (m.group(1), m.group(2)):
            arg = raw_arg.strip().lstrip("&")
            varname = re.sub(r"[\[\] *]", "", arg).split("[")[0]
            declared = decls.get(varname)
            if declared and declared == "int":
                errors.append(f"strcmp argument '{varname}' declared as int (not a string)")

    return warnings, errors


def _check_rand_srand(code: str) -> list[str]:
    warnings: list[str] = []
    if re.search(r"\brand\s*\(", code):
        if not re.search(r"\bsrand\s*\(", code):
            warnings.append("rand() used without srand() — results will not be random")
        elif not re.search(r"\btime\s*\(", code):
            warnings.append("srand() called without time(NULL) seed — fixed seed every run")
    return warnings


def _check_time_include(code: str) -> list[str]:
    warnings: list[str] = []
    if re.search(r"\btime\s*\(", code):
        if "#include <time.h>" not in code and '#include "time.h"' not in code:
            warnings.append("time() used but #include <time.h> not found")
    return warnings


def _check_infinite_loop(code: str) -> list[str]:
    warnings: list[str] = []
    masked = _mask(code)

    while_ones = list(re.finditer(r"\bwhile\s*\(\s*1\s*\)", masked))
    for m in while_ones:
        # Look for break in the loop body
        start = code.find("{", m.end())
        if start < 0:
            continue
        depth = 0
        body_chars = []
        for i in range(start, len(code)):
            if code[i] == "{":
                depth += 1
            elif code[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            body_chars.append(code[i])
        body = "".join(body_chars)
        if not re.search(r"\b(break|return|exit)\b", body):
            warnings.append("while(1) loop has no visible break/return/exit — possible infinite loop")

    return warnings


def _check_array_negative_index(code: str) -> list[str]:
    warnings: list[str] = []
    masked = _mask(code)

    # numbers[i - 1] where i iterates from 0 — OOB risk
    # Heuristic: look for arr[i - 1] or arr[i-1]
    if re.search(r"\w+\s*\[\s*\w+\s*-\s*1\s*\]", masked):
        # Check if there's a loop starting from 0
        if re.search(r"for\s*\([^;]*=\s*0\s*;", masked):
            warnings.append("array[i-1] accessed in loop starting from i=0 — potential out-of-bounds at first iteration")

    return warnings


def _check_char_used_as_string(code: str) -> list[str]:
    """char playAgain; but used with scanf(\"%s\", &playAgain)."""
    warnings: list[str] = []
    decls = _declared_vars(code)

    for m in re.finditer(r'\bscanf\s*\(\s*"([^"]*)"([^)]*)\)', code):
        fmt  = m.group(1)
        args = m.group(2)
        if "%s" not in fmt:
            continue
        for raw in args.split(","):
            varname = re.sub(r"[& *\[\]]", "", raw.strip())
            declared = decls.get(varname)
            if declared == "char":   # single char, not array
                warnings.append(
                    f"scanf(\"%s\") into single char '{varname}' — use char buf[N] instead"
                )

    return warnings


def _check_unique_random_risk(code: str) -> list[str]:
    """
    Heuristic: generating unique random numbers with naive do-while or simple
    modulo without proper uniqueness check is risky.
    """
    warnings: list[str] = []
    if not re.search(r"\brand\s*\(", code):
        return warnings

    # Unique number generation without checking: rand() % N without a seen[] array
    if re.search(r"rand\s*\(\s*\)\s*%", code):
        has_seen = bool(re.search(r"\b(seen|used|chosen|picked)\s*\[", code, re.IGNORECASE))
        has_sort  = bool(re.search(r"\bsort\b", code, re.IGNORECASE))
        if not has_seen and not has_sort:
            warnings.append(
                "rand()% used but no 'seen[]' uniqueness tracking found — may generate duplicates"
            )

    return warnings


def _check_always_false_condition(code: str) -> list[str]:
    """Catch obvious tautologies / contradictions."""
    warnings: list[str] = []
    masked = _mask(code)

    # e.g. if (x == 'Y' || x == 'y') but x was read with scanf("%d", &x)
    # Too risky to auto-detect generally; just catch literal `if (0)` / `if (false)`
    if re.search(r"\bif\s*\(\s*0\s*\)", masked):
        warnings.append("if(0) found — dead code block")
    if re.search(r"\bwhile\s*\(\s*0\s*\)", masked):
        warnings.append("while(0) found — loop body never executes")

    return warnings


# ── Aggregator ─────────────────────────────────────────────────────────────

_ERROR_WEIGHT   = 0.35
_WARNING_WEIGHT = 0.08
_MAX_SCORE      = 1.0


def analyse(code: str) -> AnalysisResult:
    """Run all checks and return an AnalysisResult."""
    warnings: list[str] = []
    errors:   list[str] = []
    signals:  dict[str, Any] = {}

    # Errors
    errors.extend(_check_markdown_fence(code))

    w, e = _check_scanf_string_to_non_array(code)
    warnings.extend(w)
    errors.extend(e)

    w, e = _check_strcmp_usage(code)
    warnings.extend(w)
    errors.extend(e)

    # Warnings
    warnings.extend(_check_missing_return(code))
    warnings.extend(_check_rand_srand(code))
    warnings.extend(_check_time_include(code))
    warnings.extend(_check_infinite_loop(code))
    warnings.extend(_check_array_negative_index(code))
    warnings.extend(_check_char_used_as_string(code))
    warnings.extend(_check_unique_random_risk(code))
    warnings.extend(_check_always_false_condition(code))

    # Signals (informational, no weight)
    signals["has_rand"]       = bool(re.search(r"\brand\s*\(", code))
    signals["has_strcmp"]     = "strcmp" in code
    signals["has_scanf_s"]    = bool(re.search(r'scanf\s*\(\s*"%s"', code))
    signals["has_while1"]     = bool(re.search(r"while\s*\(\s*1\s*\)", code))
    signals["has_string_h"]   = "#include <string.h>" in code
    signals["has_time_h"]     = "#include <time.h>" in code
    signals["loc"]            = code.count("\n") + 1

    raw_score = min(
        _MAX_SCORE,
        len(errors) * _ERROR_WEIGHT + len(warnings) * _WARNING_WEIGHT,
    )
    semantic_pass = len(errors) == 0

    return AnalysisResult(
        semantic_pass=semantic_pass,
        risk_score=raw_score,
        warnings=warnings,
        errors=errors,
        signals=signals,
    )
