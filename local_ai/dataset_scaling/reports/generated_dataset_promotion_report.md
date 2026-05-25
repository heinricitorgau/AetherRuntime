# Generated Dataset Promotion Report

Generated: `2026-05-25T17:25:23+00:00`
Dataset: `generated_sft_candidate_v1`
Decision: **promote_to_candidate_training**
Candidate-training-ready: **True**

## Reasons

- validated generated solutions meet candidate-training threshold
- generated benchmark acceptance and avg_score meet gate threshold
- all topic acceptance rates are >= 70%
- dataset card exists and dataset config is isolated=true

## Metrics

| Metric | Value |
|--------|------:|
| records | 40 |
| generated_solution_accepted | 40 |
| generated_solution_rejected | 0 |
| generated_solution_acceptance_rate | 1.0 |
| benchmark_tasks | 40 |
| benchmark_accepted | 34 |
| benchmark_rejected | 6 |
| benchmark_acceptance_rate | 0.85 |
| benchmark_avg_score | 82.5 |
| min_topic_acceptance_rate | 0.8 |
| low_score_cases | 6 |
| compile_verified_count | 40 |
| runtime_verified_count | 40 |
| semantic_verified_count | 40 |
| dataset_card_exists | True |
| dataset_isolated | True |

## Weak Topics / Audit Signals

| Topic | Accept Rate | Low Score | Compile Fail | Runtime Fail |
|-------|------------:|----------:|-------------:|-------------:|
| game_simulation | 0.8 | 2 | 2 | 4 |
| geometry | 0.8 | 2 | 2 | 4 |
| pattern_generation | 1.0 | 0 | 0 | 2 |
| series_calculation | 0.8 | 2 | 2 | 2 |

## Risks

- Benchmark has weak or noisy topic signals; review weak_topics before promotion-quality use.
- Benchmark contains 6 low-score model outputs; do not train on failed outputs.
- Candidate-training-ready does not mean default corpus; keep this data isolated until guarded experiments pass.

## Recommended Next Action

Create a guarded, isolated LoRA experiment using generated_sft_candidate_v1; compare against base on both generated_c_tasks_v1 and the existing strict exam benchmark before any adapter promotion.

## Guardrails

- Isolated candidate only.
- Not default corpus.
- Use with guarded benchmark comparison.
- Do not use failed benchmark outputs for training.
- This script does not modify SFT corpus, training jobs, benchmark scoring, or generated task data.
