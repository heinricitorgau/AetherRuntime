"""package_retry_dataset.py — package retry training records into SFT ChatML format.

Reads:
    local_ai/analysis/reports/retry_training_dataset.jsonl

Writes:
    local_ai/analysis/reports/retry_sft_chatml.jsonl   (records with corrected_output)
    local_ai/analysis/reports/retry_needs_correction.jsonl  (records missing corrected_output)

Only records that have a validated corrected_output are written to retry_sft_chatml.jsonl.
Records without corrected_output are written to retry_needs_correction.jsonl for human/model
correction via generate_retry_answers.py.

ChatML format is identical to local_ai/training_quality/reports/sft_chatml.jsonl:
    {"messages": [system, user, assistant], "metadata": {...}}
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
if str(_LOCAL_AI.parent) not in sys.path:
    sys.path.insert(0, str(_LOCAL_AI.parent))

from local_ai.shared.jsonl import read_jsonl, write_jsonl

RETRY_DATASET  = _HERE / "reports" / "retry_training_dataset.jsonl"
OUTPUT_CHATML  = _HERE / "reports" / "retry_sft_chatml.jsonl"
OUTPUT_NEEDS   = _HERE / "reports" / "retry_needs_correction.jsonl"

_SYSTEM = (
    "You are a C programming repair assistant. "
    "Output exactly one complete C program. "
    "Include all necessary #include directives. "
    "Always include int main(). "
    "No explanations outside the code. "
    "No markdown fences."
)


# ── validator ─────────────────────────────────────────────────────────────────

def _count_braces(text: str) -> tuple[int, int]:
    return text.count("{"), text.count("}")


def validate_c(code: str) -> list[str]:
    """Return a list of violation strings; empty list means the code is valid."""
    violations: list[str] = []
    if "#include" not in code:
        violations.append("missing #include")
    if not re.search(r"\bint\s+main\s*\(", code):
        violations.append("missing int main")
    if "return 0" not in code and "return(0)" not in code:
        violations.append("missing return 0")
    opens, closes = _count_braces(code)
    if opens != closes:
        violations.append(f"unbalanced braces ({opens} open, {closes} close)")
    # Must not be just the bad_output (check it's not a tiny fragment)
    if len(code.strip()) < 50:
        violations.append("code too short (< 50 chars) — likely a fragment")
    return violations


# ── user message builder ──────────────────────────────────────────────────────

def _build_user_msg(record: dict) -> str:
    parts: list[str] = []

    prompt = (record.get("original_prompt") or "").strip()
    if prompt:
        parts.append(prompt)

    parts.append("")
    parts.append(f"[Failure type: {record.get('failure_type', 'unknown')}]")

    hint = (record.get("improvement_hint") or "").strip()
    if hint:
        parts.append(f"[Repair hint: {hint}]")

    expected = (record.get("expected_behavior") or "").strip()
    if expected:
        parts.append(f"[Expected: {expected}]")

    return "\n".join(parts)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if not RETRY_DATASET.exists():
        print(f"[package] ERROR: {RETRY_DATASET} not found. Run generate_retry_dataset.py first.")
        sys.exit(1)

    records = read_jsonl(RETRY_DATASET)
    print(f"[package] Loaded {len(records)} retry records")

    chatml_records: list[dict] = []
    needs_correction: list[dict] = []

    for r in records:
        corrected = (r.get("corrected_output") or "").strip()

        if not corrected:
            needs_correction.append(r)
            continue

        violations = validate_c(corrected)
        if violations:
            print(f"  [skip] {r.get('meta', {}).get('task_id', '?')} — "
                  f"corrected_output invalid: {violations}")
            needs_correction.append(r)
            continue

        user_msg = _build_user_msg(r)
        meta = r.get("meta", {})

        chatml_records.append({
            "messages": [
                {"role": "system",    "content": _SYSTEM},
                {"role": "user",      "content": user_msg},
                {"role": "assistant", "content": corrected},
            ],
            "metadata": {
                "id":           meta.get("task_id", ""),
                "type":         "retry_code_generation",
                "source":       "retry_sft",
                "failure_type": r.get("failure_type", ""),
                "year":         meta.get("year", 0),
                "topic":        meta.get("topic", ""),
                "score_before": meta.get("score", 0),
            },
        })

    OUTPUT_CHATML.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUTPUT_CHATML, chatml_records)
    write_jsonl(OUTPUT_NEEDS,  needs_correction)

    print(f"\n[package] Results:")
    print(f"  retry_sft_chatml.jsonl      : {len(chatml_records)} records")
    print(f"  retry_needs_correction.jsonl: {len(needs_correction)} records")
    print(f"  Output : {OUTPUT_CHATML}")
    print(f"  Needs correction: {OUTPUT_NEEDS}")

    if needs_correction:
        print(f"\n[package] Run generate_retry_answers.py to produce corrected_output for "
              f"{len(needs_correction)} remaining records, then re-run this script.")


if __name__ == "__main__":
    main()
