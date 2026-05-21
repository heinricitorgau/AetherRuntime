#!/usr/bin/env python3
"""Augment round_geometry_v1/retry_chatml.jsonl with plain-prompt training pairs.

The repair-format training (prompt + failure hints → program) does NOT transfer well
to inference time, where the benchmark only sends the plain task instruction.

This script appends plain-prompt pairs:
    user    = original task instruction only (matches inference format exactly)
    assistant = complete, correct C program

Result: chatml contains both repair-format AND plain-prompt examples.
The LoRA learns to generate complete programs in BOTH contexts.
"""
import json
from pathlib import Path
import sys

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent

if str(_LOCAL_AI.parent) not in sys.path:
    sys.path.insert(0, str(_LOCAL_AI.parent))

from local_ai.shared.jsonl import read_jsonl, write_jsonl

_ROUND_DIR  = _HERE / "rounds" / "round_geometry_v1"
_CHATML     = _ROUND_DIR / "retry_chatml.jsonl"
_DATASET    = _ROUND_DIR / "retry_dataset.jsonl"

_BENCH_PROMPTS = _LOCAL_AI / "benchmark" / "prompts"
_SYSTEM_BENCH  = None
for _fname in ("code_gen_strict_v2.txt", "code_gen_strict.txt", "code_gen_v1.txt"):
    _p = _BENCH_PROMPTS / _fname
    if _p.exists():
        _SYSTEM_BENCH = _p.read_text(encoding="utf-8").strip()
        break
if _SYSTEM_BENCH is None:
    # Fallback: mirror the benchmark default
    _SYSTEM_BENCH = (
        "You are a competitive programming code generator. "
        "Output exactly ONE complete compilable C99 program. "
        "Never output helper functions only. "
        "Always include int main() with scanf/printf."
    )

# User-message suffix injected by benchmark_lora.py at inference time
_BENCH_USER_SUFFIX = "\n\nWrite the full program, not just helper functions."


def main() -> None:
    if not _DATASET.exists():
        print(f"[augment] ERROR: {_DATASET} not found.")
        sys.exit(1)
    if not _CHATML.exists():
        print(f"[augment] ERROR: {_CHATML} not found. Run package_retry_dataset.py --round first.")
        sys.exit(1)

    # Load current chatml records (repair-format)
    existing = read_jsonl(_CHATML)
    print(f"[augment] Current retry_chatml.jsonl: {len(existing)} repair-format records")

    # Load source dataset records (have corrected_output + original_prompt)
    dataset = read_jsonl(_DATASET)

    # Build plain-prompt pairs for each record with a valid corrected_output
    plain_records = []
    for r in dataset:
        prompt     = (r.get("original_prompt") or "").strip()
        corrected  = (r.get("corrected_output") or "").strip()
        meta       = r.get("meta", {})
        task_id    = meta.get("task_id", "")

        if not prompt or not corrected:
            print(f"  [skip] {task_id}: missing prompt or corrected_output")
            continue

        # user message matches benchmark_lora.py exactly:
        #   instruction.strip() + "\n\nWrite the full program, not just helper functions."
        bench_user = prompt + _BENCH_USER_SUFFIX

        plain_records.append({
            "messages": [
                {"role": "system",    "content": _SYSTEM_BENCH},
                {"role": "user",      "content": bench_user},
                {"role": "assistant", "content": corrected},
            ],
            "metadata": {
                "id":           task_id,
                "type":         "plain_code_generation",
                "source":       "geometry_plain_sft",
                "failure_type": r.get("failure_type", ""),
                "round":        "round_geometry_v1",
                "year":         meta.get("year", 0),
                "topic":        meta.get("topic", ""),
                "score_before": meta.get("score", 0),
                "note":         "plain-prompt pair for inference-format alignment",
            },
        })
        print(f"  [add] {task_id}: plain-prompt pair added")

    if not plain_records:
        print("[augment] WARNING: no plain records to add.")
        return

    # Duplicate plain-prompt records 3x so gradient updates are proportional
    # (6 records total + 9 duplicated = 15 training records → ~7 optimizer steps per epoch)
    DUP_FACTOR = 3
    plain_duped = plain_records * DUP_FACTOR

    # Merge: repair-format + plain-prompt (duplicated)
    merged = existing + plain_duped
    write_jsonl(_CHATML, merged)

    print(f"\n[augment] retry_chatml.jsonl updated:")
    print(f"  repair-format records: {len(existing)}")
    print(f"  plain-prompt records:  {len(plain_records)} x{DUP_FACTOR} = {len(plain_duped)}")
    print(f"  total:                 {len(merged)}")
    print(f"  Output: {_CHATML}")
    print(f"\nNext step:")
    print(f"  python local_ai/sft/train_lora.py --round round_geometry_v1")


if __name__ == "__main__":
    main()
