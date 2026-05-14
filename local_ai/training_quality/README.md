# Training Quality Pipeline

Validates generated C code training records before fine-tuning.

## Why compile pass is not enough

A program can compile cleanly and even produce some output while containing semantic bugs that make it wrong training signal:

| Bug | Effect |
|-----|--------|
| `scanf("%s", &intVar)` | Writes string bytes into an int — silent memory corruption |
| `strcmp(intVar, ...)` | Compares memory addresses, not string content |
| `rand()` without `srand()` | Always returns the same pseudo-random sequence |
| `rand() %` without uniqueness tracking | May generate duplicate "unique" numbers |
| `while(1)` without break | Program hangs on interactive input in automated tests |
| `array[i-1]` when i starts at 0 | Reads one slot before the array start |
| Wrong scanf format specifier | Silent type confusion, undefined behavior |

These bugs produce wrong answers or UB even when compilation succeeds.

---

## Pipeline stages

```
structure_validator.py   ->  structure_report.json
keyword_validator.py     ->  keyword_report.json
compile_validator.py     ->  compile_report.json      (requires gcc)
runtime_validator.py     ->  runtime_report.json      (requires compile)
score_records.py         ->  score_report.json
accepted_only.py         ->  splits/accepted/
                             (removes records with score < threshold)
audit_accepted_dataset.py -> semantic_report.json
                             semantic_report.md
                             semantic_accepted.jsonl
                             semantic_rejected.jsonl
```

Run entire pipeline:
```
python local_ai/training_quality/run_pipeline.py --threshold 60
```

Then run semantic audit:
```
python local_ai/training_quality/audit_accepted_dataset.py
```

---

## Semantic validation

### Checks in `static_analysis.py`

**Errors** (always reject):

- Code still contains markdown fence (` ``` `)
- `scanf("%s")` writing to a non-`char[]` variable
- `scanf("%d")` writing to a `float`/`double` variable
- `strcmp()` argument declared as `int`

**Warnings** (counted against threshold):

- `rand()` without `srand()` call
- `srand()` without `time(NULL)` seed
- `time()` without `#include <time.h>`
- `strcmp` without `#include <string.h>`
- `rand() %` without seen-array uniqueness check
- `while(1)` loop with no visible `break`/`return`/`exit`
- `array[i-1]` in a loop starting from `i=0`
- `scanf("%s")` into a single `char` variable (not an array)
- `main()` has no `return` statement
- `if(0)` / `while(0)` dead code

### Acceptance rules

Default: accept if 0 errors AND warnings <= 4

Configurable:

| Method | Effect |
|--------|--------|
| `--strict` flag | max warnings = 2 |
| `--max-warnings N` | override threshold to N |
| `CLAW_SEMANTIC_MAX_WARNINGS=N` env var | same override |
| `CLAW_SEMANTIC_STRICT=1` env var | same as --strict |

### Usage

```powershell
# Default audit (max 4 warnings)
python local_ai/training_quality/audit_accepted_dataset.py

# Strict mode (max 2 warnings)
python local_ai/training_quality/audit_accepted_dataset.py --strict

# Custom threshold
python local_ai/training_quality/audit_accepted_dataset.py --max-warnings 1

# Custom input/output
python local_ai/training_quality/audit_accepted_dataset.py `
    --input local_ai/ingest/output/training/splits/accepted/combined.jsonl `
    --out-dir local_ai/training_quality/reports
```

### Output files

| File | Contents |
|------|----------|
| `semantic_report.json` | Full results, per-record analysis |
| `semantic_report.md` | Human-readable summary with rejection reasons |
| `semantic_accepted.jsonl` | Records that passed semantic validation |
| `semantic_rejected.jsonl` | Records that failed — review before discarding |

---

## Limitations

- Heuristic analysis, not a full C parser — may miss bugs or flag false positives
- Does not check algorithmic correctness (wrong formula, wrong loop bounds)
- Does not verify that the output matches the exam problem specification
- Type inference is approximate (regex-based, not a real type system)

## Next steps

1. Manually review `semantic_rejected.jsonl` — some may be false positives
2. Fix or regenerate rejected records with a better model or prompt
3. Use `semantic_accepted.jsonl` as the clean fine-tuning corpus
4. Consider adding a human-review step for records with `risk_score > 0.3`
