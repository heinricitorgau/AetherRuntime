# Dataset Card — C Programming SFT Corpus

**Version**: 1.2  
**Created**: 2026-05-14  
**Generation model**: `qwen2.5-coder:3b` via Ollama (local, offline)

> **Before fine-tuning, read the [Known Issues](#known-issues) section.**
> At least 9 records have confirmed quality problems.

---

## Quick Summary

| | |
|--|--|
| Total SFT records | **41** |
| code_generation | 16 (exam problems + generated C solutions) |
| concept_summary | 25 (exam text + generated explanations) |
| Years | 2021–2025 |
| Estimated total tokens | ~17,000 |
| Runtime-verified solutions | 12 / 16 (75%) |
| Human-reviewed | **No** |

---

## Build Pipeline

```
5 exam PDFs
  └─ pdf_to_html → html_cleaner → chunker ──────────────────┐
                                                             │
19 eval case JSONs ──────────────────────────────────────────┴──→ combined.jsonl (44)
                                                                         │
                                                             split_training.py
                                                    ┌────────────┬────────┴────────┐
                                                  train        val               test
                                               (2021–23)     (2024)            (2025)
                                                    └────────────┴─────────────────┘
                                                                 │
                                         run_pipeline.py  (structure → keyword
                                                           → compile → runtime → score)
                                                                 │
                                                     accepted_only.py (score ≥ 60)
                                                                 │
                                         audit_accepted_dataset.py (semantic)
                                                                 │
                                generate_answers.py + fill_concept_summaries.py
                                                                 │
                                         package_sft_dataset.py ──→ sft_*.jsonl
```

---

## Dataset Statistics

### Records by split

| Split | Total | code_generation | concept_summary | Years |
|-------|------:|----------------:|----------------:|-------|
| train | 27 | 12 | 15 | 2021, 2022, 2023 |
| val   |  7 |  3 |  4 | 2024 |
| test  | 10 |  4 |  6 | 2025 |
| **SFT total** | **41** | **16** | **25** | — |

3 records rejected before packaging (compile errors).

### Token statistics (estimated, chars ÷ 4)

| | Prompt | Completion |
|--|-------:|-----------:|
| Min | 29 | 123 |
| Max | 446 | 758 |
| Average | 154 | 267 |
| **Corpus total** | | **~17,250** |

code_generation avg completion: ~312 tokens  
concept_summary avg completion: ~238 tokens

### code_generation topic distribution

| Topic | Count | Difficulty |
|-------|------:|-----------|
| Series Calculation | 5 | medium |
| Pattern Generation | 5 | medium |
| Geometry (triangles, points, lines, circles) | 4 | hard |
| Game Simulation (betting, guessing, tug-war) | 2 | hard |

### code_generation per-record quality

All 19 records (16 accepted + 3 excluded). Sorted by score.  
Columns: C = compile pass, Runtime = match ratio or failure mode, K = keyword score, Sem = semantic warnings, Tier.

| ID | Topic | Split | Score | C | Runtime | K | Sem | Tier |
|----|-------|-------|------:|---|---------|---|-----|------|
| `2023_exam1_001` | Series Calc | train | 93 | ✓ | 1.00 | 0.50 | clean | **High** |
| `2024_exam1_001` | Series Calc | val   | 93 | ✓ | 1.00 | 0.50 | clean | **High** |
| `2021_exam1_001` | Series Calc | train | 91 | ✓ | 1.00 | 0.40 | clean | **High** |
| `2022_exam1_003` | Geometry    | train | 90 | ✓ | 0.75 | 0.88 | clean | **High** |
| `2021_exam1_002` | Pattern Gen | train | 86 | ✓ | 0.80 | 0.47 | clean | **High** |
| `2021_exam1_003` | Geometry    | train | 86 | ✓ | 0.67 | 0.73 | clean | **High** |
| `2024_exam1_002` | Pattern Gen | val   | 85 | ✓ | 0.75 | 0.50 | clean | **High** |
| `2023_exam1_002` | Pattern Gen | train | 83 | ✓ | 0.67 | 0.50 | clean | **High** |
| `2025_midterm_003` | Geometry  | test  | 81 | ✓ | 0.50 | 0.75 | clean | **High** |
| `2024_exam1_003` | Game Sim   | val   | 75 | ✓ | 0.33 | 0.67 | 1 warn | **High** |
| `2022_exam1_002` | Pattern Gen | train | 72 | ✓ | 0.40 | 0.33 | clean | **High** |
| `2025_midterm_002` | Pattern Gen | test | 72 | ✓ | 0.40 | 0.33 | clean | **High** |
| `2022_exam1_004` | Game Sim (Tug War) | train | 68 | ✓ | **TIMEOUT** | 0.88 | 2 warns | Medium |
| `2025_midterm_004` | Game Sim (Guess) | test | 65 | ✓ | **TIMEOUT** | 0.65 | 2 warns | Medium |
| `2022_exam1_001` | Series Calc | train | 63 | ✓ | wrong out | 0.50 | clean | Medium |
| `2025_midterm_001` | Series Calc | test | 63 | ✓ | wrong out | 0.50 | clean | Medium |
| `2023_exam1_004` | Game Sim    | train | 30 | ✗ | — | 1.00 | n/a | *Excluded* |
| `2021_exam1_004` | Game Sim (Betting) | train | 28 | ✗ | — | 0.83 | n/a | *Excluded* |
| `2023_exam1_003` | Geometry    | train | 24 | ✗ | — | 0.62 | n/a | *Excluded* |

Runtime ratio = fraction of expected output tokens matched. `wrong out` = compiled and ran, but output incorrect. `—` = not run (compile failed).

Semantic warnings present in 3 records:
- `2022_exam1_004` — `rand()` without `srand()`, `rand%` without uniqueness check
- `2025_midterm_004` — `array[i-1]` potential OOB, `rand%` without uniqueness check
- `2024_exam1_003` — `rand%` without uniqueness check

---

## Data Sources

### Source 1 — Structured eval cases (`eval_case`, 19 records)

- **Files**: `local_ai/eval_cases/c_exam/*.json`
- **Content**: Exam problems with prompt, required_features, sample_input,
  expected_behavior, checker_rules, difficulty, points
- **Coverage**: exam1 (2021–2024), midterm (2025)
- **C solutions**: Generated by `qwen2.5-coder:3b` via `generate_answers.py`

### Source 2 — PDF-extracted chunks (`pdf_chunk`, 25 records)

- **Files**: 5 exam PDFs → `pdf_to_html.py` → `html_cleaner.py` → `chunker.py`
- **Chunk boundaries**: Detected at numbered question starts (`1.`, `2.`, …)
- **Content quality varies** (see Known Issues below)

| Chunk type | Count | Quality |
|------------|------:|---------|
| Exam header only (`_0000`) | 5 | Low — no instructional content |
| Exam question text | 20 | Medium — unstructured, no sample I/O |

- **Explanations**: Generated by `qwen2.5-coder:3b` via `fill_concept_summaries.py`

---

## Validation Results

### code_generation pipeline

| Stage | Result | Method |
|-------|--------|--------|
| Structure | 19 / 19 | `#include`, `int main()`, balanced braces |
| Keyword | 15 / 19 | Required C constructs from `checker_rules` |
| Compile | 16 / 19 | `gcc -std=c99 -Wall` (msys2 ucrt64 15.2.0) |
| Runtime | 12 / 16 | Run with `sample_input`, check `output_contains` |
| Semantic | 16 / 16 | Heuristic: scanf types, rand/srand, OOB, infinite loops |
| **Accepted** | **16 / 19** | Score ≥ 60/100 AND semantic pass |

Score weights: Compile 40 · Runtime 30 · Keyword 15 · Structure 15  
Average accepted score: **70.9 / 100**  
Score range (accepted): 63–93

### concept_summary pipeline

Compile and runtime validation were **not applied** (no executable output).  
Only checked for: non-empty output, correct JSON structure.

---

## Known Issues

### code_generation — 4 records with runtime failures (included)

These records compile and score ≥ 60, but produce wrong output:

| ID | Failure | Missing tokens |
|----|---------|----------------|
| `2022_exam1_001` | Wrong output | `324096` |
| `2022_exam1_004` | **Timeout** | `Welcome`, `Tug War`, `Enter`, `winner` |
| `2025_midterm_001` | Wrong output | `0.607` (series sum incorrect) |
| `2025_midterm_004` | **Timeout** | `Numbers`, `win`, `points`, `Pick` |

The two timeout cases contain `while(1)` game loops that block on `scanf` in
non-interactive mode. Their logic may also be incomplete.

**Recommendation**: Filter these out before fine-tuning with `--threshold 70`.

### concept_summary — 5 low-quality exam header records

The `_0000` chunk of each exam file contains only the exam title and point total:

```
C Programming Exam I - 3A Student No: Name:
Part 3: Program (80 points)
```

The model hallucinated C programming explanations unrelated to this content.
These 5 records teach the wrong input → output mapping.

Affected IDs: `c_exam1_programming_202{1,2,3,4}_cleaned_0000`,
`c_midterm_programming_2025_cleaned_0000`

**Recommendation**: Remove these 5 records before fine-tuning.

### concept_summary — inconsistent output language

Some concept_summary completions are in Chinese, others in English, depending
on how the model interpreted the prompt. This inconsistency will confuse the
model during fine-tuning if target language is English.

**Recommendation**: Review `sft_chatml.jsonl` concept_summary completions and
filter or re-generate with an explicit `Respond in English only.` system prompt.

### Dataset size

16 code_generation records is too small for meaningful generalization.
Realistic outcome: style alignment (C99 formatting, function structure, I/O
patterns). Do not expect the model to learn new algorithms from this corpus.

---

## Record Quality Tiers

| Tier | Criteria | Estimated count |
|------|----------|----------------:|
| **High** | Compiles + runtime pass + semantic clean | 12 |
| **Medium** | Compiles + semantic pass, runtime fail | 4 |
| **Low** | concept_summary exam headers | 5 |
| **Excluded** | Compile error | 3 |

For best fine-tuning signal: use Tier High (12 records) only.  
To get High-only: `--threshold 70` + remove the 5 `_0000` concept records.

---

## Before Fine-tuning Checklist

- [ ] Decide on `--threshold`: 60 (41 records) vs 70 (removes 4 runtime-fail code_gen)
- [ ] Remove 5 exam-header concept_summary records (`*_0000`)
- [ ] Decide on language: filter or regenerate mixed-language concept_summary
- [ ] Choose format: ChatML (TRL/Axolotl/Unsloth), Alpaca (LLaMA-Factory), or minimal
- [ ] Consider `--strip-code-fences` if your tokenizer handles raw C better than markdown

---

## Output Formats

All formats in `local_ai/training_quality/reports/`:

### `sft_chatml.jsonl` — ChatML (recommended for HuggingFace ecosystem)

```json
{
  "messages": [
    {"role": "system",    "content": "You are a C programming assistant. Output exactly one complete C99 program. Do not explain."},
    {"role": "user",      "content": "<problem statement>"},
    {"role": "assistant", "content": "<C program or explanation>"}
  ],
  "metadata": {"id": "2021_exam1_002", "year": 2021, "topic": "Pattern Generation", "difficulty": "medium"}
}
```

Use with: HuggingFace TRL `SFTTrainer`, Axolotl, Unsloth.

### `sft_alpaca.jsonl` — Alpaca

```json
{"instruction": "...", "input": "", "output": "...", "metadata": {...}}
```

Use with: LLaMA-Factory, FastChat.

### `sft_instruction_output.jsonl` — Minimal

```json
{"prompt": "<system>\n\n<problem>", "completion": "<answer>", "metadata": {...}}
```

---

## Sample Record

Record `2021_exam1_001` from `sft_chatml.jsonl` (High tier, runtime match 1.00):

**user**
```
Write a program that reads n and calculates the sum of the following series:
1 - 2/3 + 6/7 - ... + n!/(n²+n+1)

Formula: Sum from i=1 to n of: (-1)^(i+1) * i! / (i²+i+1)

Example: When n=11, f(11) = 270944.7015728441

Required features:
  - Read integer input n
  - Compute factorial for each term
  - Calculate series sum with correct alternating signs
  - Output result with appropriate precision
```

**assistant** (truncated)
````
```c
#include <stdio.h>
#include <math.h>

unsigned long long factorial(int num) {
    unsigned long long result = 1;
    for (int i = 2; i <= num; ++i) result *= i;
    return result;
}

int main() {
    int n;
    printf("Enter an integer n between 1 and 20: ");
    scanf("%d", &n);
    double sum = 0.0;
    // ... (full program: 34 LOC, compiles clean, runtime match 1.00)
}
```
````

**metadata**
```json
{"id": "2021_exam1_001", "type": "code_generation", "source": "eval_case",
 "year": 2021, "topic": "Series Calculation", "difficulty": "medium", "points": 12, "exam": "exam1"}
```

---

## Fine-tuning Configuration Hints

These are starting-point suggestions for a 41-record corpus on a consumer GPU. Adjust based on your base model and hardware.

| Parameter | Suggested value | Rationale |
|-----------|----------------|-----------|
| Batch size (effective) | 8–16 | Accumulate gradients; corpus is tiny |
| Epochs | 3–5 | More epochs compensate for small data; watch for overfitting |
| Learning rate | 1e-4 – 2e-4 | Conservative; lower for 7B+ models |
| LR scheduler | cosine with warmup | Standard for SFT |
| Warmup ratio | 0.05 – 0.1 | Short warmup over ~4 steps |
| LoRA rank | 8–16 | Low rank sufficient for style alignment |
| LoRA alpha | 16–32 | Set to 2× rank |
| Max sequence length | 512 | Covers all records; longest completion ~760 tokens |
| Format | ChatML (`sft_chatml.jsonl`) | Best supported across Axolotl/Unsloth/TRL |

Expected outcome: C99 style alignment and I/O pattern consistency. This corpus is **too small** for the model to generalize to new algorithms.

---

## System Prompts

| Type | System prompt |
|------|---------------|
| `code_generation` | You are a C programming assistant. Output exactly one complete C99 program. Do not explain. |
| `concept_summary` | You are a concise C programming tutor. Explain clearly and briefly. |

---

## Limitations

| Limitation | Impact |
|------------|--------|
| All answers AI-generated, no human review | Unknown correctness rate |
| 4 accepted code_gen records fail runtime | May reinforce wrong patterns |
| 5 concept_summary records are header noise | Hallucinated outputs |
| Mixed language in concept_summary | Training instability |
| 16 code_gen records total | Style alignment only, no generalization |
| Topics biased toward series/pattern problems | Overfitting risk |
| Single course context (3A, Taiwan university) | Domain-specific only |

---

## Intended Use

**Suitable for:**
- Offline, low-resource fine-tuning experiments (1–7B models)
- C99 code style and format alignment
- Curriculum-specific assistant for this exact course

**Not suitable for:**
- Production code generation
- General-purpose C programming assistance
- Any benchmark evaluation

---

## File Structure

```
local_ai/
  DATASET_CARD.md
  eval_cases/c_exam/*.json              19 structured exam problems
  ingest/output/
    *.chunks.json                       25 PDF-extracted chunks
    training/
      combined.jsonl                    44 raw records
      splits/
        train.jsonl                     27 records (2021–2023)
        val.jsonl                        7 records (2024)
        test.jsonl                      10 records (2025)
        accepted/combined.jsonl         41 validated records
  training_quality/reports/
    semantic_accepted_filled.jsonl      41 records, all outputs filled
    sft_chatml.jsonl                    final SFT corpus — ChatML
    sft_alpaca.jsonl                    final SFT corpus — Alpaca
    sft_instruction_output.jsonl        final SFT corpus — minimal
    score_report.json                   per-record quality scores
    semantic_report.json                semantic audit (warnings, errors per record)
    semantic_report.md                  human-readable audit summary
    sft_package_summary.json            packaging stats
```

---

## Reproducibility

```powershell
# Terminal 1: start proxy
cd local_ai
python proxy.py --model qwen2.5-coder:3b

# Terminal 2: rebuild corpus
python local_ai/ingest/prepare_training.py
python local_ai/ingest/split_training.py
python local_ai/training_quality/run_pipeline.py --threshold 60
python local_ai/training_quality/audit_accepted_dataset.py
python local_ai/ingest/generate_answers.py --skip-existing
python local_ai/training_quality/fill_concept_summaries.py --skip-existing
python local_ai/training_quality/package_sft_dataset.py `
    --input local_ai/training_quality/reports/semantic_accepted_filled.jsonl

# Stricter build (removes 4 runtime-fail code_gen records)
python local_ai/training_quality/run_pipeline.py --threshold 70
```

---

*Generated 2026-05-14. Model: qwen2.5-coder:3b (Ollama). No cloud API used.*
