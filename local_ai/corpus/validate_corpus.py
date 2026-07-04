#!/usr/bin/env python3
"""Validate corpus integrity (V10).

Checks every corpus record for required fields, valid status/level enums, and
lifecycle consistency (e.g. human_verified must carry a reviewer; golden must
have been human_verified first; review-stage items must be in_review). Read-only.

Outputs:
  reports/corpus_validation.json
  reports/corpus_validation.md

Exit code 1 if any errors are found.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import corpus_lib as cl  # noqa: E402


def _validate_item(item: dict) -> list[str]:
    errs: list[str] = []
    tid = item.get("task_id", "<no id>")

    for f in cl.REQUIRED_FIELDS:
        if f not in item:
            errs.append(f"{tid}: missing field '{f}'")

    status = item.get("review_status")
    level = item.get("verification_level")
    stage = item.get("_stage")

    if status not in cl.VALID_STATUSES:
        errs.append(f"{tid}: invalid review_status '{status}'")
    if level is not None and level not in cl.VALID_LEVELS:
        errs.append(f"{tid}: invalid verification_level '{level}'")

    # Lifecycle consistency.
    if level in ("human_verified", "golden") and not item.get("reviewer"):
        errs.append(f"{tid}: {level} requires a reviewer")
    if level == "golden":
        actions = {h.get("action") for h in item.get("history", [])}
        if "approve" not in actions:
            errs.append(f"{tid}: golden without a prior human approve in history")
    if stage == "review" and status != "in_review":
        errs.append(f"{tid}: in review/ but status is '{status}'")
    if stage == "verified" and status not in ("candidate", "approved", "golden"):
        errs.append(f"{tid}: in verified/ but status is '{status}'")
    if item.get("history") is None:
        errs.append(f"{tid}: missing append-only history")
    return errs


def validate() -> dict:
    items = cl.all_items()
    errors: list[str] = []
    for item in items:
        errors.extend(_validate_item(item))
    return {
        "timestamp": cl.now(),
        "total": len(items),
        "error_count": len(errors),
        "decision": "pass" if not errors else "fail",
        "errors": errors,
    }


def _markdown(report: dict) -> str:
    lines = ["# Corpus Validation Report", "",
             f"Generated: `{report['timestamp']}`",
             f"Decision: **{report['decision']}**",
             f"Items: {report['total']}  Errors: {report['error_count']}", "", "## Errors", ""]
    if report["errors"]:
        for e in report["errors"]:
            lines.append(f"- {e}")
    else:
        lines.append("None — corpus integrity holds.")
    return "\n".join(lines) + "\n"


def main() -> None:
    cl.ensure_dirs()
    report = validate()
    (cl.REPORTS_DIR / "corpus_validation.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (cl.REPORTS_DIR / "corpus_validation.md").write_text(_markdown(report), encoding="utf-8")
    print(f"[validate-corpus] decision={report['decision']} items={report['total']} "
          f"errors={report['error_count']}")
    print(f"[validate-corpus] >> {cl.REPORTS_DIR / 'corpus_validation.md'}")
    sys.exit(0 if report["decision"] == "pass" else 1)


if __name__ == "__main__":
    main()
