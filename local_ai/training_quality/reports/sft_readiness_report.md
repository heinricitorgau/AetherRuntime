# SFT Readiness Report

**Timestamp**: 2026-05-20T19:30:25+00:00
**Overall**: PASS — READY FOR SFT

---

## Dataset: PASS

| Check | Status | Detail |
|-------|:------:|--------|
| semantic_accepted_filled.jsonl | PASS | found |
| sft_chatml.jsonl | PASS | found |
| sft_alpaca.jsonl | PASS | found |
| sft_instruction_output.jsonl | PASS | found |
| total_records | PASS | 41 (need >= 40) |
| code_generation | PASS | 16 (need >= 16) |
| concept_summary | PASS | 25 (need >= 25) |

## Semantic: PASS

| Check | Status | Detail |
|-------|:------:|--------|
| semantic_rejected | PASS | 0 rejected (need 0) |
| semantic_accepted | PASS | 16 |
| checked | PASS | 16 |

## Benchmark: PASS

| Check | Status | Detail |
|-------|:------:|--------|
| golden_exists | PASS | ref=strict_20260515_052032 |
| accepted_all | PASS | 4/4 (need all) |
| avg_score_ge_80 | PASS | 84.2 (need >= 80) |
| compile_100pct | PASS | 100% (need 100%) |
| semantic_100pct | PASS | 100% (need 100%) |
| timeout_zero | PASS | 0% (need 0%) |

## Reproducibility: PASS

| Check | Status | Detail |
|-------|:------:|--------|
| golden_run_registered | PASS | strict_20260515_052032 found in experiment registry |

## Documentation: PASS

| Check | Status | Detail |
|-------|:------:|--------|
| README.md | PASS | found |
| DATASET_CARD.md | PASS | found |

---

**READY_FOR_SFT = true**