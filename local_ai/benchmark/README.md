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
| **Keyword** | Does the code use the required C constructs (`for`, `scanf`, `rand`, …)? |

A compile pass alone is **not enough**. A program can compile cleanly and still:
- Write garbage due to a wrong `scanf` format specifier
- Hang forever on a `while(1)` loop without `break`
- Produce a deterministic pseudo-random sequence because `rand()` was called without `srand()`
- Silently corrupt memory with `array[i-1]` when `i=0`

Runtime output matching catches wrong-answer programs; semantic analysis catches the subtle ones.

---

## Why deterministic evaluation matters

| Problem with non-deterministic eval | How this benchmark avoids it |
|-------------------------------------|------------------------------|
| GPT judge gives different verdicts on re-run | All checks are rule-based |
| Soft scoring hides compile errors | compile/runtime/semantic are separate binary flags |
| Temperature > 0 makes scores unstable | Default `temperature=0.0` for all runs |
| Different test inputs between runs | `sample_input` comes from the eval case JSON — fixed per task |
| Manual review is not reproducible | Fully automated, no human in the loop |

---

## Difference between compile / runtime / semantic correctness

```
Structure      The code "looks like" valid C (has #include, has int main, balanced braces).
               Does NOT mean it compiles or runs correctly.

Compile        gcc -std=c99 -Wall accepts the code with exit code 0.
               Does NOT mean the output is correct.

Runtime        The compiled binary produces the expected output tokens when given
               the sample input. This catches wrong-answer programs.

Semantic       Static analysis: scanf type mismatch, strcmp on int, rand without srand,
               while(1) without break, array[i-1] OOB, etc.
               This catches bugs that compile silently and may even produce some output.
```

Example: A series-sum program that uses `int` accumulator instead of `double` will compile
cleanly, run without crashing, produce output — but the numeric values will be wrong, and
the runtime check will catch the mismatch with `expected_tokens`.

---

## Reproducibility

All results depend only on:
1. The model weights (fixed by model name + Ollama state)
2. The task definitions in `eval_cases/c_exam/*.json` (versioned in git)
3. The system prompt in `prompts/` (versioned in git)
4. `temperature=0.0` (passed to every API call)

Given the same inputs, every check produces the same verdict.

---

## File Structure

```
local_ai/benchmark/
  _bench_common.py            shared utilities (proxy, compile, score)
  benchmark_cases.py          task loader from eval_cases/c_exam/*.json
  run_baseline.py             main entry point — run model, save results
  scoring.py                  aggregate metrics + comparison tool
  prompts/
    code_gen_v1.txt           standard system prompt (used by default)
    code_gen_brief.txt        minimal prompt variant
    code_gen_stepwise.txt     chain-of-thought variant
  reports/
    runs/<run_id>/
      meta.json               run configuration
      results.jsonl           per-case results
      report.json             aggregate metrics
      report.md               human-readable summary
      passed_cases.jsonl      accepted cases (score >= 60)
      failed_cases.jsonl      rejected cases
    baseline_report.json      copy of latest run report (top-level shortcut)
    baseline_report.md        copy of latest run report (markdown)
    passed_cases.jsonl        top-level shortcut
    failed_cases.jsonl        top-level shortcut
```

---

## Quick Start

```powershell
# Terminal 1: start proxy
cd local_ai
python proxy.py --model qwen2.5-coder:3b

# Terminal 2: run benchmark (all 19 tasks)
python local_ai/benchmark/run_baseline.py

# Run with specific model and run ID
python local_ai/benchmark/run_baseline.py `
    --model qwen2.5-coder:3b `
    --run-id baseline_3b `
    --max-tokens 2048

# Run only 2021 tasks (quick smoke test)
python local_ai/benchmark/run_baseline.py --filter 2021

# Skip compile+runtime (proxy response quality only)
python local_ai/benchmark/run_baseline.py --no-compile

# Dry run — list tasks without API calls
python local_ai/benchmark/run_baseline.py --dry-run

# Re-score an existing run
python local_ai/benchmark/scoring.py --run-id baseline_3b

# Compare two runs
python local_ai/benchmark/scoring.py --compare baseline_3b lora_3b_v1

# List all benchmark tasks
python local_ai/benchmark/benchmark_cases.py --list
```

---

## Score Formula

Weights are identical to the training_quality pipeline for cross-run comparability:

| Check | Points |
|-------|-------:|
| Structure (has include, has main, balanced, complete) | 15 |
| Keywords (required C constructs) | 15 |
| Compile | 40 |
| Runtime (output token match) | 30 |
| **Total** | **100** |

**Accepted**: score ≥ 60.

---

## Benchmark Dimensions

### compile
```
gcc -std=c99 -Wall -o <exe> <src> -lm
```
Pass = exit code 0. Uses msys2 PATH prefix on Windows for DLL resolution.

### runtime
```
echo <sample_input> | <exe>
```
Checks that every token in `expected_behavior.output_contains` appears in stdout.
Match ratio = found/total. Pass = match_ratio > 0.

### semantic
Heuristic static analysis without a full C parser. Checks:

**Errors** (always fail):
- `scanf("%s")` writing into a non-`char[]` variable
- `scanf("%d")` writing into a `float`/`double`
- `` ` `` code fence still present in output

**Warnings** (counted; fail if > threshold):
- `rand()` without `srand()`
- `srand()` without `time(NULL)`
- `rand()%` without uniqueness tracking
- `while(1)` without `break`/`return`/`exit`
- `array[i-1]` in a loop starting from `i=0`

### keyword
Checks `checker_rules.keywords` from the eval case. Pass = at least 50% of required
keywords found in the generated code.

### timeout
Two kinds of timeout:
- **Proxy timeout**: model took longer than `--timeout` seconds to respond
- **Binary timeout**: compiled program ran longer than `--run-timeout` seconds

### truncation
Checks that the response is a complete program:
- Ends with `}`
- `{` count equals `}` count

---

## Adding a New Prompt Variant

1. Create `prompts/my_prompt.txt` with the system prompt text
2. Run: `python local_ai/benchmark/run_baseline.py --prompt-file local_ai/benchmark/prompts/my_prompt.txt --run-id my_run`
3. Compare: `python local_ai/benchmark/scoring.py --compare baseline_3b my_run`

---

## Comparing Baseline vs Fine-tuned Model

```powershell
# Baseline run
python local_ai/benchmark/run_baseline.py `
    --model qwen2.5-coder:3b --run-id baseline_3b

# After fine-tuning and loading the adapter:
python local_ai/benchmark/run_baseline.py `
    --model qwen2.5-coder:3b-lora-v1 --run-id lora_3b_v1

# Side-by-side comparison
python local_ai/benchmark/scoring.py --compare baseline_3b lora_3b_v1
```

The comparison table shows per-dimension pass rates and average score for each run.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAW_MODEL` | `qwen2.5-coder:3b` | Model name |
| `CLAW_PROXY_URL` | `http://127.0.0.1:8082` | Proxy base URL |
| `CLAW_BENCHMARK_MAX_TOKENS` | `1536` | Max tokens per response |
| `CLAW_BENCHMARK_TIMEOUT` | `90` | Proxy request timeout (seconds) |

---

*Offline-first. No cloud API. All checks deterministic.*
