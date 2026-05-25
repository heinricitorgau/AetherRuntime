#!/usr/bin/env python3
"""Package validated generated solutions into isolated SFT and benchmark artifacts.

Input:
    local_ai/dataset_scaling/reports/accepted_generated_solutions.jsonl

Outputs:
    local_ai/dataset_scaling/reports/generated_sft_chatml.jsonl      -- SFT training records
    local_ai/dataset_scaling/reports/generated_benchmark_cases.jsonl -- benchmark task records
    local_ai/dataset_scaling/reports/generated_dataset_summary.json  -- statistics
    local_ai/dataset_scaling/reports/generated_dataset_card.md       -- documentation

These artifacts are ISOLATED candidate data — they must NOT be merged into the
production SFT corpus without a separate integration review.

Usage:
    python local_ai/dataset_scaling/package_generated_sft.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_REPO_ROOT = _LOCAL_AI.parent

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ── Paths ─────────────────────────────────────────────────────────────────────

_REPORTS_DIR   = _HERE / "reports"
_INPUT_FILE    = _REPORTS_DIR / "accepted_generated_solutions.jsonl"
_SFT_CHATML    = _REPORTS_DIR / "generated_sft_chatml.jsonl"
_BENCH_CASES   = _REPORTS_DIR / "generated_benchmark_cases.jsonl"
_SUMMARY_JSON  = _REPORTS_DIR / "generated_dataset_summary.json"
_DATASET_CARD  = _REPORTS_DIR / "generated_dataset_card.md"

# ── SFT system prompt (matches sft_chatml.jsonl convention) ───────────────────

_SYSTEM_PROMPT = (
    "You are a C programming assistant. "
    "Output exactly one complete C program."
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _build_instruction(prompt: str, sample_input: str, expected_tokens: list[str]) -> str:
    """Build an instruction string compatible with benchmark_cases.load_tasks().

    Embeds 'Sample input:' and 'Expected output contains:' markers so that
    _parse_instruction() can extract them at benchmark run time.
    """
    parts = [prompt.strip()]
    if sample_input:
        parts.append(f"\nSample input:\n{sample_input.strip()}")
    if expected_tokens:
        token_str = ", ".join(expected_tokens)
        parts.append(f"\nExpected output contains: {token_str}")
    return "\n".join(parts)


# ── Record builders ───────────────────────────────────────────────────────────

def _build_sft_record(rec: dict) -> dict:
    """Convert an accepted solution record to a ChatML SFT training record."""
    return {
        "messages": [
            {"role": "system",    "content": _SYSTEM_PROMPT},
            {"role": "user",      "content": rec["prompt"]},
            {"role": "assistant", "content": rec["reference_solution"]},
        ],
        "metadata": {
            "id":               rec["id"],
            "type":             "code_generation",
            "source":           "generated_synthetic_v3",
            "topic":            rec.get("topic", ""),
            "difficulty":       rec.get("difficulty", ""),
            "generation_model": rec.get("generation_model", ""),
        },
    }


def _build_benchmark_record(rec: dict) -> dict:
    """Convert an accepted solution record to a benchmark task record.

    The record includes both:
    - 'type' / 'instruction' fields required by benchmark_cases._record_to_task()
    - the structured spec fields (prompt, sample_input, etc.) for downstream use

    'instruction' embeds 'Sample input:' and 'Expected output contains:' markers
    so that _parse_instruction() extracts them correctly at evaluation time.
    """
    prompt                 = rec["prompt"]
    sample_input           = rec.get("sample_input", "")
    expected_output_contains = rec.get("expected_output_contains", [])
    checker_rules          = rec.get("checker_rules", {})

    instruction = _build_instruction(prompt, sample_input, expected_output_contains)

    return {
        # Fields required by benchmark_cases._record_to_task():
        "id":          rec["id"],
        "type":        "code_generation",
        "instruction": instruction,
        "metadata": {
            "topic":      rec.get("topic", ""),
            "difficulty": rec.get("difficulty", ""),
            "source":     "generated_synthetic_v3",
        },
        # Structured spec fields (for tooling and documentation):
        "topic":                   rec.get("topic", ""),
        "difficulty":              rec.get("difficulty", ""),
        "prompt":                  prompt,
        "sample_input":            sample_input,
        "expected_output_contains": expected_output_contains,
        "required_features":       rec.get("required_features", []),
        "checker_rules":           checker_rules,
        # Validation provenance:
        "compile_verified":  rec.get("validation", {}).get("compile",  {}).get("ok",     False),
        "runtime_verified":  rec.get("validation", {}).get("runtime",  {}).get("ok",     False),
        "semantic_verified": rec.get("validation", {}).get("semantic", {}).get("passed", False),
        "generation_model":  rec.get("generation_model", ""),
        "generated_at":      rec.get("generated_at", ""),
    }


def _build_summary(records: list[dict]) -> dict:
    """Aggregate statistics over all accepted records."""
    by_topic      = Counter(r.get("topic", "unknown")      for r in records)
    by_difficulty = Counter(r.get("difficulty", "unknown") for r in records)

    compile_verified  = sum(
        1 for r in records if r.get("validation", {}).get("compile",  {}).get("ok",     False)
    )
    runtime_verified  = sum(
        1 for r in records if r.get("validation", {}).get("runtime",  {}).get("ok",     False)
    )
    semantic_verified = sum(
        1 for r in records if r.get("validation", {}).get("semantic", {}).get("passed", False)
    )

    return {
        "total_records":          len(records),
        "by_topic":               dict(sorted(by_topic.items())),
        "by_difficulty":          dict(sorted(by_difficulty.items())),
        "compile_verified_count": compile_verified,
        "runtime_verified_count": runtime_verified,
        "semantic_verified_count": semantic_verified,
        "generated_at":           _now(),
    }


def _build_dataset_card(summary: dict) -> str:
    """Generate the markdown dataset card."""
    ts           = summary["generated_at"]
    total        = summary["total_records"]
    compile_pct  = round(summary["compile_verified_count"]  / total * 100) if total else 0
    runtime_pct  = round(summary["runtime_verified_count"]  / total * 100) if total else 0
    semantic_pct = round(summary["semantic_verified_count"] / total * 100) if total else 0

    topic_rows = "\n".join(
        f"| `{t}` | {n} |" for t, n in sorted(summary["by_topic"].items())
    )
    diff_rows = "\n".join(
        f"| `{d}` | {n} |" for d, n in sorted(summary["by_difficulty"].items())
    )

    return f"""# Generated Candidate Dataset — V3

**Generated**: `{ts}`
**Records**: {total}
**Status**: ISOLATED CANDIDATE — not yet merged into production SFT corpus

---

## Dataset Purpose

This dataset extends the training corpus for Qwen2.5-Coder-3B-Instruct with
synthetically generated C programming tasks.  It was created to address the
limited size of the original exam-based corpus (~41 tasks) and to provide more
coverage across topics and difficulty levels.

All records were generated using deterministic template-based synthesis
(`generate_tasks.py`, `generate_reference_solutions.py`) and were fully
validated before packaging.

---

## Generation Method

- **Task generation**: `dataset_scaling/generate_tasks.py` — deterministic
  template-based generation, no LLM hallucination.
- **Reference solutions**: `dataset_scaling/generate_reference_solutions.py`
  — hand-written C programs; no model-generated code in the training targets.
- **Validation**: `dataset_scaling/validate_reference_solutions.py` — compile
  with `gcc -std=c99`, runtime execution with sample input, semantic static
  analysis, structure check.
- **Generation model tag**: `template_reference_v1`

---

## Validation Results

| Check | Count | Pass Rate |
|-------|------:|----------:|
| Compile (gcc -std=c99) | {summary["compile_verified_count"]}/{total} | {compile_pct}% |
| Runtime (sample I/O match) | {summary["runtime_verified_count"]}/{total} | {runtime_pct}% |
| Semantic (static analysis) | {summary["semantic_verified_count"]}/{total} | {semantic_pct}% |

---

## Coverage

### By Topic

| Topic | Records |
|-------|--------:|
{topic_rows}

### By Difficulty

| Difficulty | Records |
|------------|--------:|
{diff_rows}

---

## Limitations

1. **Synthetic distribution**: tasks follow a small number of formula templates.
   The variety is narrower than real exam questions.
2. **No multi-function tasks**: all tasks produce a single `int main()` program
   without helper functions, unlike the harder exam tasks.
3. **No interactive I/O patterns**: tasks use simple `scanf`/`printf`.
4. **Not student-authored**: the reference solutions may not match the
   vocabulary or style patterns seen in real student answers.
5. **No cross-topic tasks**: each record belongs to exactly one topic bucket.

---

## Why It Is Isolated

This dataset is kept separate from the production SFT corpus
(`local_ai/training_quality/reports/sft_chatml.jsonl`) because:

- It has not been reviewed for quality parity with real exam tasks.
- The distribution does not match the target benchmark distribution.
- Mixing synthetic data without weighting experiments can degrade performance
  on the real test set.
- An integration experiment (LoRA comparison benchmark) must confirm
  improvement before promotion.

---

## How to Use Safely

### 1. Isolated benchmark evaluation

Run against a LoRA adapter to check if the model already generalises:

```bash
python local_ai/benchmark/run_baseline.py \\
    --benchmark generated_c_tasks_v1 \\
    --dry-run       # preview tasks without calling proxy
```

### 2. Experimental SFT training

Reference this dataset as `generated_sft_candidate_v1` in a training job.
Keep the resulting adapter isolated and compare against the base model before
any promotion:

```json
// local_ai/config/training_jobs.json (example entry — do NOT add yet)
"generated_sft_experiment_v1": {{
    "model": "qwen3b_local",
    "dataset": "generated_sft_candidate_v1",
    "output_dir": "local_ai/sft/artifacts/generated_sft_v1",
    "epochs": 2
}}
```

### 3. Promotion criteria

Before merging into the production corpus:
- Benchmark delta on `c_exam_2025_strict_seeded` must be >= 0 (no regression)
- At least one topic coverage gap in the real test set must show improvement
- A human review of 5 randomly sampled tasks must confirm correctness

---

*Generated by `local_ai/dataset_scaling/package_generated_sft.py`*
"""


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if not _INPUT_FILE.exists():
        print(f"[package] ERROR: input not found: {_INPUT_FILE}")
        sys.exit(1)

    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    records = _read_jsonl(_INPUT_FILE)
    print(f"[package] loaded {len(records)} accepted records from {_INPUT_FILE.name}")

    # Filter: only process records that are actually accepted
    records = [r for r in records if r.get("validation", {}).get("accepted", False)]
    print(f"[package] {len(records)} records with validation.accepted=true")

    if not records:
        print("[package] ERROR: no accepted records found.")
        sys.exit(1)

    # ── SFT ChatML ────────────────────────────────────────────────────────────
    sft_records = [_build_sft_record(r) for r in records]
    _write_jsonl(_SFT_CHATML, sft_records)
    print(f"[package] generated_sft_chatml.jsonl   → {len(sft_records)} records")

    # ── Benchmark cases ───────────────────────────────────────────────────────
    bench_records = [_build_benchmark_record(r) for r in records]
    _write_jsonl(_BENCH_CASES, bench_records)
    print(f"[package] generated_benchmark_cases.jsonl → {len(bench_records)} records")

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = _build_summary(records)
    _write_json(_SUMMARY_JSON, summary)
    print(f"[package] generated_dataset_summary.json → {_SUMMARY_JSON.name}")

    # ── Dataset card ──────────────────────────────────────────────────────────
    card_md = _build_dataset_card(summary)
    _DATASET_CARD.write_text(card_md, encoding="utf-8")
    print(f"[package] generated_dataset_card.md      → {_DATASET_CARD.name}")

    # ── Final summary ─────────────────────────────────────────────────────────
    print(f"\n[package] DONE")
    print(f"  SFT records:       {len(sft_records)}")
    print(f"  Benchmark records: {len(bench_records)}")
    print(f"  By topic:          {dict(summary['by_topic'])}")
    print(f"  By difficulty:     {dict(summary['by_difficulty'])}")
    print(f"  Compile verified:  {summary['compile_verified_count']}/{len(records)}")
    print(f"  Runtime verified:  {summary['runtime_verified_count']}/{len(records)}")
    print(f"  Semantic verified: {summary['semantic_verified_count']}/{len(records)}")
    print(f"\nNext steps:")
    print(f"  python local_ai/config/validate_profiles.py")
    print(f"  python local_ai/benchmark/run_baseline.py --benchmark generated_c_tasks_v1 --dry-run")


if __name__ == "__main__":
    main()
