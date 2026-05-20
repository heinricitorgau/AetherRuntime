"""Unified failure taxonomy for coding model analysis.

Each category maps to observable signals in benchmark check results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class FailureCategory:
    name: str
    description: str
    signals: tuple[str, ...]  # human-readable signal keys for documentation


TAXONOMY: tuple[FailureCategory, ...] = (
    FailureCategory(
        name="syntax_error",
        description="Code contains C syntax errors caught by the compiler.",
        signals=("checks.compile.errors contains syntax/parse errors",),
    ),
    FailureCategory(
        name="runtime_error",
        description="Code compiles but crashes or produces wrong output at runtime.",
        signals=("checks.compile.passed=True", "checks.runtime.passed=False"),
    ),
    FailureCategory(
        name="truncation",
        description="Model output was cut off before the solution was complete.",
        signals=("checks.truncation.passed=False",),
    ),
    FailureCategory(
        name="logic_error",
        description="Output matches expected form but runtime values are wrong.",
        signals=("checks.runtime.match_ratio > 0 and < 1",),
    ),
    FailureCategory(
        name="missing_entrypoint",
        description="No `int main()` function present in generated code.",
        signals=("checks.structure.issues contains 'missing int main'",),
    ),
    FailureCategory(
        name="partial_generation",
        description="Proxy returned empty or near-empty response (connection error).",
        signals=("checks.proxy.passed=False", "extracted_code is empty"),
    ),
    FailureCategory(
        name="hallucinated_function",
        description="Code calls functions that do not exist in standard C (e.g. undeclared identifiers).",
        signals=("compile error: undeclared identifier",),
    ),
    FailureCategory(
        name="algorithm_mismatch",
        description="Wrong algorithm applied — structure and syntax correct but approach is wrong.",
        signals=("checks.runtime.match_ratio=0", "checks.compile.passed=True"),
    ),
    FailureCategory(
        name="geometry_reasoning",
        description="Failure specifically on geometry / distance / coordinate problems.",
        signals=("task_meta.topic contains geometry/distance", "runtime fail"),
    ),
    FailureCategory(
        name="array_bounds",
        description="Array indexing or sizing errors causing compile or runtime failure.",
        signals=("compile/runtime error with array/index",),
    ),
    FailureCategory(
        name="io_format_error",
        description="Output format does not match expected (wrong precision, separators, etc.).",
        signals=("checks.runtime.match_ratio > 0", "missing values with format mismatch"),
    ),
)

CATEGORY_NAMES: tuple[str, ...] = tuple(c.name for c in TAXONOMY)


def classify(record: dict) -> list[str]:
    """Return a list of failure category names that apply to *record*.

    A record may match multiple categories.  The caller receives the full
    list and can take the first (highest-priority) match or aggregate all.
    """
    cats: list[str] = []
    checks = record.get("checks", {})

    proxy_ok   = checks.get("proxy",      {}).get("passed", True)
    trunc_ok   = checks.get("truncation", {}).get("passed", True)
    struct     = checks.get("structure",  {})
    compile_c  = checks.get("compile",    {})
    runtime_c  = checks.get("runtime",    {})

    extracted  = (record.get("extracted_code") or "").strip()
    topic      = (record.get("task_meta", {}) or {}).get("topic", "").lower()
    comp_errs  = compile_c.get("errors", [])
    struct_issues = struct.get("issues", [])
    match_ratio = runtime_c.get("match_ratio", 0.0) or 0.0

    # partial_generation — proxy failed or empty response
    if not proxy_ok or not extracted:
        cats.append("partial_generation")

    # truncation
    if not trunc_ok:
        cats.append("truncation")

    # missing_entrypoint
    if any("missing int main" in i for i in struct_issues):
        cats.append("missing_entrypoint")

    if compile_c.get("passed") is False:
        errs_str = " ".join(comp_errs).lower()

        # hallucinated_function — undeclared identifiers
        if "undeclared" in errs_str or "implicit declaration" in errs_str:
            cats.append("hallucinated_function")

        # array_bounds
        if "array" in errs_str or "subscript" in errs_str or "index" in errs_str:
            cats.append("array_bounds")

        # stray backtick / markdown fence → syntax_error
        if "stray" in errs_str or "error: expected" in errs_str:
            cats.append("syntax_error")

        # linker error without main → already covered by missing_entrypoint
        # generic compile failure not yet classified
        if not cats or cats == ["partial_generation"] or cats == ["truncation"]:
            cats.append("syntax_error")

    elif compile_c.get("passed") is True:
        if runtime_c.get("passed") is False:
            if 0 < match_ratio < 1.0:
                # produced *some* output but not all correct
                cats.append("io_format_error" if match_ratio > 0.5 else "logic_error")
            else:
                # geometry topics → geometry_reasoning
                if any(k in topic for k in ("geometry", "distance", "nearest", "point", "triangle")):
                    cats.append("geometry_reasoning")
                else:
                    cats.append("algorithm_mismatch")

    # Fallback: if nothing matched, mark as runtime_error
    if not cats:
        cats.append("runtime_error")

    return cats


def primary(record: dict) -> str:
    """Return the single most-specific failure category for *record*."""
    cats = classify(record)
    # Priority order mirrors taxonomy definition order
    for cat in CATEGORY_NAMES:
        if cat in cats:
            return cat
    return cats[0] if cats else "runtime_error"
