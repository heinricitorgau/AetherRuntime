# Offline Benchmark System

Deterministic, offline-first evaluation of C code generation models.

---

## Philosophy

**Deterministic evaluation** means the same model + same prompt + same input always produces the same pass/fail verdict. There are no subjective grades, no random scores, no crowd-sourced ratings. Every check is a binary rule applied to the output.

This benchmark measures:

| Dimension | What it tests |
|-----------|--------------|
| **Proxy response** | Did the model respond at all, or did it time out? |
| **Truncation** | Is the generated code complete (balanced braces, ends with `}`)? |
| **Structure** | Does the code have `#include`, `int main`, balanced braces? |
| **Compile** | Does `gcc -std=c99 -Wall` accept the code without errors? |
| **Runtime** | Does the compiled binary produce the expected output tokens? |
| **Semantic** | Does static analysis pass (no `scanf` type mismatch, no infinite loops, etc.)? |
| **Keyword** | Does the code use the required C constructs (`for`, `scanf`, `rand`, ...)? |

A compile pass alone is **not enough**. A program can compile cleanly and still:
- Write garbage due to a wrong `scanf` format specifier
- Hang forever on a `while(1)` loop without `break`
- Produce a deterministic pseudo-random sequence because `rand()` was called without `srand()`
- Silently corrupt memory with `array[i-1]` when `i=0`

Runtime output matching catches wrong-answer programs; semantic analysis catches the subtle ones.

---

## Why a Baseline Run Is Needed Before Fine-tuning

Fine-tuning without a baseline is a common mistake. Without a pre-fine-tune measurement:

- You cannot tell whether SFT improved the model or just shifted it
- You cannot isolate regressions (e.g. compile rate drops after fine-tuning)
- You cannot prove the fine-tune was worth the training cost

The baseline establishes the **pre-fine-tune floor** on the same task distribution as the training data. After fine-tuning, run the same benchmark with the same run_id prefix and compare with `scoring.py --compare`.

---

## Why Strict Benchmark Prompting Matters

Small models (1B–7B) in instruction-following mode frequently produce output that wastes their entire token budget on:

- Long preambles: "Here is a C program that solves the problem..."
- Re-stating the problem: "The series is defined as..."
- Chinese explanations: self-narration in the training language
- Markdown structure: headers, bullet points, fenced sub-examples
- Redundant comments: inline documentation of every line

For a 3B model with `max_tokens=768`, a response that spends 400 tokens on explanation before writing the first line of code will often **truncate mid-function**. The result compiles with errors, scores 0 on compile+runtime, and the entire benchmark run appears broken.

The fix is **not to increase max_tokens** — that makes the model more likely to elaborate further. The fix is to change the system prompt to suppress non-code output.

`--strict-code-only` activates a stricter prompt and smaller token budget specifically calibrated for code-only output:

| Mode | System prompt | max_tokens | temperature |
|------|--------------|-----------|------------|
| standard | `code_gen_v1.txt` | 768 | 0.0 |
| `--strict-code-only` | `code_gen_strict.txt` | 384 | 0.1 |

The strict prompt explicitly bans explanations, Chinese text, markdown headings, and sample I/O repetition. 384 tokens is enough for most exam-level C programs (our dataset avg completion is 312 tokens of code).

---

## Small-Model Benchmark Optimization

Rules of thumb for benchmarking 1B–7B models on code generation:

**Token budget**

- A typical exam-level C solution is 200–400 tokens of actual code
- `max_tokens=768` leaves 370+ tokens of slack for prose — models fill it
- `max_tokens=384` forces early termination of prose, but code completes cleanly if prompted correctly
- Use `report_analysis.py` to measure `avg_code_ratio` before committing to a token budget

**Temperature**

- `temperature=0.0`: fully deterministic, same input always gives same output
  - Best for reproducibility, worst for quality on hard tasks
- `temperature=0.1`: tiny stochasticity, model stays focused, avoids mode collapse
  - Recommended for strict mode where prompt already constrains format
- `temperature >= 0.7`: model explores more, explanation rate increases, timeout risk rises

**Timeout**

- 3B models typically respond in 10–60 seconds per case on a mid-range GPU
- Default `--timeout=180` is safe for all cases including game simulation problems
- Measure `timeout_count` via `report_analysis.py`; if > 0, consider `--strict-code-only`
- A timeout is worse than a compile error for benchmarking — the case produces no signal

**Extraction fallback**

If the model does not use a ` ```c ``` ` fence, code extraction falls back to a heuristic (scan for `#include` + `int main` + balanced braces). Check `fence_usage_rate` in analysis; if < 80%, the strict prompt or a reminder line ("wrap your code in ```c") will help.

---

## Token Budget Engineering

The goal of token budget engineering is to maximize **useful tokens** (C code) while minimizing **waste tokens** (prose, markdown, explanation).

Measure the waste before optimizing:

    python local_ai/benchmark/report_analysis.py --run-id baseline_3b

Key metrics from the analysis report:

| Metric | Good | Warning | Action |
|--------|------|---------|--------|
| `avg_code_ratio` | > 70% | < 50% | Use `--strict-code-only` |
| `truncation_rate` | < 10% | > 20% | Increase `max_tokens` or use strict prompt |
| `timeout_rate` | 0% | > 10% | Reduce `max_tokens`, use strict prompt |
| `chinese_text_rate` | 0% | > 0% | Add "Respond in English only" to prompt |
| `fence_usage_rate` | > 90% | < 70% | Remind model: "Output only a single ```c block" |

After adding `--strict-code-only`:

    python local_ai/benchmark/run_baseline.py --strict-code-only --run-id strict_3b
    python local_ai/benchmark/report_analysis.py --compare baseline_3b strict_3b

The comparison table shows side-by-side improvement in code ratio and reduction in waste.

---

## Difference Between compile / runtime / semantic Correctness

    Structure      The code "looks like" valid C (has #include, has int main, balanced braces).
                   Does NOT mean it compiles or runs correctly.

    Compile        gcc -std=c99 -Wall accepts the code with exit code 0.
                   Does NOT mean the output is correct.

    Runtime        The compiled binary produces the expected output tokens when given
                   the sample input. This catches wrong-answer programs.

    Semantic       Static analysis: scanf type mismatch, strcmp on int, rand without srand,
                   while(1) without break, array[i-1] OOB, etc.
                   This catches bugs that compile silently and may even produce some output.

Example: A series-sum program that uses `int` accumulator instead of `double` will compile
cleanly, run without crashing, produce output — but the numeric values will be wrong, and
the runtime check will catch the mismatch with `expected_tokens`.

---

## Reproducibility

All results depend only on:
1. The model weights (fixed by model name + Ollama state)
2. The task definitions in `local_ai/ingest/output/training/splits/test_code_generation.jsonl` (versioned)
3. The system prompt in `prompts/` (versioned)
4. `temperature=0.0` (default) or `0.1` (strict mode)

Given the same inputs, every check produces the same verdict.

---

## File Structure

    local_ai/benchmark/
      _bench_common.py            shared utilities (proxy, compile, score, semantic_check)
      benchmark_cases.py          task loader from JSONL training splits
      run_baseline.py             main entry point -- run model, save results
      scoring.py                  aggregate metrics + comparison tool
      report_analysis.py          token waste / code ratio analysis
      prompts/
        code_gen_v1.txt           standard system prompt (default)
        code_gen_brief.txt        minimal variant
        code_gen_stepwise.txt     chain-of-thought variant
        code_gen_strict.txt       strict code-only prompt (used by --strict-code-only)
      reports/
        runs/<run_id>/
          meta.json               run configuration
          raw_outputs.jsonl       full model responses (no truncation -- for debug)
          results.jsonl           per-case evaluation records
          report.json             aggregate metrics
          report.md               human-readable benchmark summary
          passed_cases.jsonl      score >= 60
          failed_cases.jsonl      score < 60
          analysis_report.json    token waste analysis
          analysis_report.md      human-readable waste analysis
        baseline_report.json      copy of latest run (top-level shortcut)
        baseline_report.md        copy of latest run (markdown)
        passed_cases.jsonl        top-level shortcut
        failed_cases.jsonl        top-level shortcut

---

## Windows Setup

Requirements:
- Python 3.9+ (the version already used in this project)
- gcc via msys2 ucrt64: `C:\msys64\ucrt64\bin\gcc.exe`
- Ollama running with the target model loaded
- The proxy server running (`python local_ai/proxy.py --model qwen2.5-coder:3b`)

No additional Python packages are required. All benchmark code uses only the standard library.

gcc is auto-detected from:
1. `gcc` / `cc` on PATH
2. `C:\msys64\ucrt64\bin\gcc.exe`
3. `C:\msys64\mingw64\bin\gcc.exe`
4. `C:\MinGW\bin\gcc.exe`
5. `C:\TDM-GCC-64\bin\gcc.exe`

If gcc is not found, compile and runtime checks are skipped (structure, semantic, and keyword checks still run).

---

## Quick Start

Configured benchmark:

    python local_ai/benchmark/run_baseline.py --benchmark c_exam2_all_strict_seeded

The benchmark name resolves through `local_ai/config/benchmarks.json`; changing
task set, model, or prompt profile can be done through JSON profiles.

Terminal 1 (start proxy):

    cd local_ai
    python proxy.py --model qwen2.5-coder:3b

Terminal 2 (run benchmark):

    # Standard run (legacy 2025 test set, all 4 tasks)
    python local_ai/benchmark/run_baseline.py

    # Strict code-only run on the legacy 2025 test set
    python local_ai/benchmark/run_baseline.py --strict-code-only

    # Configured exam-II benchmark (2021-2024, all 16 tasks)
    python local_ai/benchmark/run_baseline.py --benchmark c_exam2_all_strict_seeded

    # Give the run a name to track it
    python local_ai/benchmark/run_baseline.py --run-id baseline_3b
    python local_ai/benchmark/run_baseline.py --strict-code-only --run-id strict_3b

    # Use all accepted training records (2021-2025, 16 tasks)
    python local_ai/benchmark/run_baseline.py --source accepted

    # Only run 2025 tasks
    python local_ai/benchmark/run_baseline.py --filter 2025

    # Skip compile and runtime (proxy response quality only)
    python local_ai/benchmark/run_baseline.py --no-compile

    # List tasks without making API calls
    python local_ai/benchmark/run_baseline.py --dry-run

After the run:

    # Analyse token waste and code ratio
    python local_ai/benchmark/report_analysis.py --run-id baseline_3b

    # Compare standard vs strict
    python local_ai/benchmark/report_analysis.py --compare baseline_3b strict_3b

    # Compare benchmark scores across runs
    python local_ai/benchmark/scoring.py --compare baseline_3b strict_3b

    # List available tasks
    python local_ai/benchmark/benchmark_cases.py --list

---

## Score Formula

Weights match the training_quality pipeline for cross-run comparability:

| Check | Points |
|-------|-------:|
| Structure (has include, has main, balanced, complete) | 15 |
| Keywords (required C constructs) | 15 |
| Compile | 40 |
| Runtime (output token match) | 30 |
| Total | 100 |

Accepted: score >= 60.

---

## Benchmark Dimensions

### compile

    gcc -std=c99 -Wall -o <exe> <src> -lm

Pass = exit code 0. Uses msys2 PATH prefix on Windows for DLL resolution.

### runtime

    echo <sample_input> | <exe>

Checks that every token in `expected_behavior.output_contains` appears in stdout.
Match ratio = found/total. Pass = match_ratio > 0.

### semantic

Heuristic static analysis without a full C parser:

Errors (always fail):
- scanf("%s") writing into a non-char[] variable
- scanf("%d") writing into a float/double
- code fence still present in output

Warnings (counted; fail if > threshold):
- rand() without srand()
- srand() without time(NULL)
- rand()% without uniqueness tracking
- while(1) without break/return/exit
- array[i-1] in a loop starting from i=0

### keyword

Checks checker_rules.keywords from the eval case. Pass = at least 50% of required
keywords found in the generated code.

### timeout

Two kinds of timeout:
- Proxy timeout: model took longer than --timeout seconds to respond
- Binary timeout: compiled program ran longer than --run-timeout seconds

### truncation

Checks that the response is a complete program:
- Ends with }
- { count equals } count

---

## Golden Baseline

A golden baseline is a locked, deterministic reference run. Once a model's output is stable
(consistent scores across multiple runs), lock it so every future run compares against a fixed floor.

### What is a golden baseline?

The golden baseline records the exact pre-fine-tune, pre-change performance of a specific
model + prompt configuration. It is not updated automatically — only when you explicitly
decide a new run should become the reference.

### Why it matters before fine-tuning

Without a golden baseline:
- You cannot tell whether SFT improved the model or just shifted it
- You cannot detect compile-rate regressions introduced by fine-tuning
- You cannot prove the fine-tune was worth the training cost

### How to lock a baseline

    python local_ai/benchmark/lock_golden_baseline.py --run-id strict_20260515_043031

Writes `golden/golden_baseline.json`. Running this again overwrites the previous golden.

### How to compare a run against the golden

    python local_ai/benchmark/compare_against_golden.py --run-id strict_20260515_050000

Writes `reports/runs/<run_id>/comparison_report.md` and `comparison_report.json`.

Every `run_baseline.py` run also auto-compares against `golden/golden_baseline.json`
(if it exists) and prints the verdict at the end of the run:

    [golden] matches golden  (golden: 4/4  78.5pts  ref=strict_20260515_043031)
    [golden] regression detected  (golden: 4/4  78.5pts  ref=strict_20260515_043031)
    [golden] improvement detected  (golden: 4/4  78.5pts  ref=strict_20260515_043031)

### Regression and improvement thresholds

| Signal | Condition |
|--------|-----------|
| regression | accepted drops, OR avg_score drops > 1.0pt, OR timeout_rate rises |
| improvement | accepted rises, OR avg_score rises > 1.0pt |
| matches golden | all metrics within tolerance |

### File layout

    golden/
      golden_baseline.json    locked reference metrics (committed to repo)

---

## Comparing Baseline vs Fine-tuned Model

    # Step 1: establish baseline before fine-tuning
    python local_ai/benchmark/run_baseline.py --run-id baseline_3b

    # Step 2: fine-tune (outside this benchmark)

    # Step 3: benchmark the fine-tuned model
    python local_ai/benchmark/run_baseline.py --model qwen2.5-coder:3b-lora-v1 --run-id lora_3b_v1

    # Step 4: compare
    python local_ai/benchmark/scoring.py --compare baseline_3b lora_3b_v1

The comparison table shows per-dimension pass rates and average score for each run.
A fine-tuned model should show improvement in compile_pass_rate and runtime_pass_rate
without regression in semantic_pass_rate.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| CLAW_MODEL | qwen2.5-coder:3b | Model name |
| CLAW_PROXY_URL | http://127.0.0.1:8082 | Proxy base URL |
| CLAW_BENCHMARK_MAX_TOKENS | 768 | Max tokens per response (standard mode) |
| CLAW_BENCHMARK_TIMEOUT_SECONDS | 180 | Proxy request timeout in seconds |

Note: --strict-code-only overrides max_tokens to 384 and temperature to 0.1
regardless of env var values.

---

*Offline-first. No cloud API. All checks deterministic.*
