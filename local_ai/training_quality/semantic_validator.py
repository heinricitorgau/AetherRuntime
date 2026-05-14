"""Semantic validator: thin orchestration layer over static_analysis.

Applies acceptance rules (max warnings, strict mode) and produces
a structured validation record per training sample.

Public API
----------
validate(rec: dict, strict: bool, max_warnings: int) -> dict
"""
from __future__ import annotations

import os
import re

from static_analysis import analyse


_DEFAULT_MAX_WARNINGS = 4
_STRICT_MAX_WARNINGS  = 2


def _extract_code(rec: dict) -> str:
    """Extract raw C code from a training record's output field."""
    output = rec.get("output", "")
    m = re.search(r"```(?:c|C)?\s*\n(.*?)```", output, re.DOTALL)
    if m:
        return m.group(1).strip()
    return output.strip()


def _env_max_warnings(strict: bool) -> int:
    env = os.environ.get("CLAW_SEMANTIC_MAX_WARNINGS", "").strip()
    if env:
        try:
            return max(0, int(env))
        except ValueError:
            pass
    env_strict = os.environ.get("CLAW_SEMANTIC_STRICT", "").strip()
    if strict or env_strict == "1":
        return _STRICT_MAX_WARNINGS
    return _DEFAULT_MAX_WARNINGS


def validate(rec: dict, strict: bool = False, max_warnings: int | None = None) -> dict:
    """
    Validate a single training record semantically.

    Returns a dict with:
      id, type, semantic_accepted, rejection_reason,
      analysis (full AnalysisResult dict)
    """
    rec_id   = rec.get("id", "unknown")
    rec_type = rec.get("type", "unknown")

    if rec_type != "code_generation":
        return {
            "id": rec_id,
            "type": rec_type,
            "semantic_accepted": True,
            "rejection_reason": None,
            "analysis": None,
            "skipped": True,
        }

    code = _extract_code(rec)
    if not code:
        return {
            "id": rec_id,
            "type": rec_type,
            "semantic_accepted": False,
            "rejection_reason": "empty code",
            "analysis": None,
            "skipped": False,
        }

    result = analyse(code)
    mw = max_warnings if max_warnings is not None else _env_max_warnings(strict)

    rejection_reason: str | None = None
    if result.errors:
        rejection_reason = f"errors: {'; '.join(result.errors[:3])}"
    elif len(result.warnings) > mw:
        rejection_reason = (
            f"{len(result.warnings)} warnings > max {mw}: "
            + "; ".join(result.warnings[:3])
        )

    return {
        "id": rec_id,
        "type": rec_type,
        "semantic_accepted": rejection_reason is None,
        "rejection_reason": rejection_reason,
        "analysis": result.to_dict(),
        "skipped": False,
    }
