# Semantic Audit Report

Generated: 2026-05-14T10:57:08+00:00
Input: `C:\Users\User\OneDrive\Desktop\research-claw-code\local_ai\ingest\output\training\splits\accepted\combined.jsonl`

## Summary

| Metric | Count |
|--------|-------|
| code_generation records checked | 16 |
| Semantic accepted | 16 |
| Semantic rejected | 0 |
| Skipped (non-code_gen) | 25 |
| Max warnings threshold | 4 |
| Strict mode | False |

## Top Warning Categories

- rand()% used but no 'seen[]' uniqueness: 3
- rand() used without srand() — results: 1
- array[i-1] accessed in loop starting from: 1

## Rejected Records

None. All code_generation records passed semantic validation.

## Why Compile Pass Is Not Enough

A program can compile and even produce output while still containing semantic bugs:

- `scanf("%s", &intVar)` — writes string bytes into an int, silent memory corruption
- `strcmp(intVar, ...)` — compares memory addresses, not string content
- `rand()` without `srand()` — always returns the same sequence
- `while(1)` without break — program hangs on interactive input in a non-interactive test
- `array[i-1]` in a loop starting at i=0 — reads before the array

These bugs produce wrong answers or undefined behavior even when compilation succeeds.

## Next Steps

1. Manually review `semantic_rejected.jsonl` — some rejections may be false positives
2. Fix or regenerate rejected records with a better model or prompt
3. Use `semantic_accepted.jsonl` as the clean fine-tuning corpus

## Limitations

- Analysis is heuristic, not a full C parser — may miss some bugs or flag false positives
- Does not check algorithmic correctness (wrong formula, wrong logic)
- Does not verify that the output matches the exam problem specification
- Manual review of rejected records is always recommended