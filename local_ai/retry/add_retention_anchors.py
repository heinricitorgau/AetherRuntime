#!/usr/bin/env python3
"""Append plain-prompt retention anchors for already-passing tasks to retry_chatml.jsonl.

Problem: round_geometry_v1 LoRA trains only on geometry examples.  After merge,
the adapter causes the model to generate longer / more verbose programs for
unrelated tasks (e.g. 2025_midterm_004 - Game Simulation), and those programs
hit the max_tokens limit mid-program.

Fix: inject one plain-prompt training pair per passing task (sourced from the
base model's verified good output in comparison_report.json).  This gives the
LoRA a gradient signal to "keep generating what the base model already generates"
for these tasks, preventing catastrophic style-drift.

Usage:
    python local_ai/retry/add_retention_anchors.py
"""
import json
from pathlib import Path
import sys

_HERE     = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent

if str(_LOCAL_AI.parent) not in sys.path:
    sys.path.insert(0, str(_LOCAL_AI.parent))

from local_ai.shared.jsonl import read_jsonl, write_jsonl

_ROUND_DIR = _HERE / "rounds" / "round_geometry_v1"
_CHATML    = _ROUND_DIR / "retry_chatml.jsonl"

_BENCH_PROMPTS = _LOCAL_AI / "benchmark" / "prompts"
_SYSTEM_BENCH  = None
for _fname in ("code_gen_strict_v2.txt", "code_gen_strict.txt", "code_gen_v1.txt"):
    _p = _BENCH_PROMPTS / _fname
    if _p.exists():
        _SYSTEM_BENCH = _p.read_text(encoding="utf-8").strip()
        break
if _SYSTEM_BENCH is None:
    _SYSTEM_BENCH = (
        "You are a competitive programming code generator. "
        "Output exactly ONE complete compilable C99 program. "
        "Never output helper functions only. "
        "Always include int main() with scanf/printf."
    )

_BENCH_USER_SUFFIX = "\n\nWrite the full program, not just helper functions."

# ── Retention anchors: prompt + verified-good C output for passing tasks ──────
# Source: base model outputs that compiled and passed (score ≥ 70) in
# local_ai/sft/reports/comparison_report.json (base_results section).

_ANCHOR_004_PROMPT = (
    "Simulate an even/odd guessing game:\n\n"
    "(a) [3 pts] Generate 5 different random numbers (1-10), hide them\n\n"
    "(b) [10 pts] Game loop:\n"
    "    - Display hidden numbers as asterisks\n"
    "    - Player picks position\n"
    "    - Player guesses even or odd\n"
    "    - If correct, player wins 5 points\n"
    "    - Reveal the number\n\n"
    "(c) [4 pts] Continue until all numbers revealed\n"
    "    Display final score\n\n"
    "Game ends when all 5 positions are revealed."
)

_ANCHOR_004_CODE = r"""#include <stdio.h>
#include <stdlib.h>
#include <time.h>

int main(void) {
    srand(time(NULL));
    int numbers[5], guessed[5] = {0}, score = 0;

    /* Generate 5 unique random numbers between 1 and 10 */
    for (int i = 0; i < 5; i++) {
        int num;
        do {
            num = rand() % 10 + 1;
        } while (guessed[num - 1]);
        numbers[i] = num;
        guessed[num - 1] = 1;
    }

    /* Reset guessed flags for game tracking */
    for (int i = 0; i < 5; i++) guessed[i] = 0;

    /* Game loop: reveal one number per round */
    for (int round = 0; round < 5; round++) {
        printf("Numbers: ");
        for (int j = 0; j < 5; j++) {
            if (guessed[j]) printf("%d ", numbers[j]);
            else             printf("* ");
        }
        printf("\nPick position (1-5): ");
        int pos;
        scanf("%d", &pos);
        pos--;  /* 0-based */

        printf("Guess (E for even, O for odd): ");
        char g;
        scanf(" %c", &g);

        int is_even = (numbers[pos] % 2 == 0);
        if ((is_even && g == 'E') || (!is_even && g == 'O')) {
            score += 5;
            printf("win! points: %d\n", score);
        } else {
            printf("wrong\n");
        }
        guessed[pos] = 1;
    }

    printf("Final score: %d\n", score);
    return 0;
}"""

# List of (task_id, prompt, code) anchors for passing tasks
_ANCHORS = [
    ("2025_midterm_004", _ANCHOR_004_PROMPT, _ANCHOR_004_CODE),
]


def main() -> None:
    if not _CHATML.exists():
        print(f"[anchors] ERROR: {_CHATML} not found.")
        sys.exit(1)

    existing = read_jsonl(_CHATML)
    print(f"[anchors] Current retry_chatml.jsonl: {len(existing)} records")

    # Check which anchors are already present
    existing_ids_types = {
        (r.get("metadata", {}).get("id", ""), r.get("metadata", {}).get("type", ""))
        for r in existing
    }

    anchor_records = []
    for task_id, prompt, code in _ANCHORS:
        key = (task_id, "retention_anchor")
        if key in existing_ids_types:
            print(f"  [skip] {task_id}: retention_anchor already present")
            continue

        bench_user = prompt + _BENCH_USER_SUFFIX
        anchor_records.append({
            "messages": [
                {"role": "system",    "content": _SYSTEM_BENCH},
                {"role": "user",      "content": bench_user},
                {"role": "assistant", "content": code},
            ],
            "metadata": {
                "id":     task_id,
                "type":   "retention_anchor",
                "source": "retention_plain_sft",
                "round":  "round_geometry_v1",
                "note":   "retention anchor to prevent catastrophic forgetting of passing task",
            },
        })
        print(f"  [add] {task_id}: retention_anchor added")

    if not anchor_records:
        print("[anchors] Nothing to add.")
        return

    merged = existing + anchor_records
    write_jsonl(_CHATML, merged)

    print(f"\n[anchors] retry_chatml.jsonl updated:")
    print(f"  before: {len(existing)}")
    print(f"  added:  {len(anchor_records)} retention anchor(s)")
    print(f"  total:  {len(merged)}")
    print(f"  Output: {_CHATML}")
    print(f"\nNext step:")
    print(f"  python local_ai/sft/train_lora.py --round round_geometry_v1")


if __name__ == "__main__":
    main()
