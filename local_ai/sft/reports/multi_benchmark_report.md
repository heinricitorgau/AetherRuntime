# Multi-Benchmark LoRA Report

Generated: `2026-05-26T10:58:25+00:00`
Adapter: `local_ai\sft\artifacts\pattern_only_candidate_v1`
Decision: **regression**

## Reasons

- both strict and generated benchmarks regress
- extra benchmarks have no regression: pattern_only_benchmark_v1

## Benchmark Deltas

| Benchmark | State | Accepted Delta | Avg Delta | Runtime Delta | Compile Delta | Semantic Delta |
|-----------|-------|---------------:|----------:|--------------:|--------------:|---------------:|
| c_exam_2025_strict_seeded | regression | -1 | -13.7 | -0.25 | -0.25 | 0.0 |
| generated_c_tasks_v1 | regression | -1 | -1.7 | -0.025 | -0.025 | 0.0 |
| pattern_only_benchmark_v1 | no_change | 0 | 0.0 | 0.0 | 0.0 | 0.0 |

## Absolute Metrics

| Benchmark | Base Accepted | LoRA Accepted | Base Avg | LoRA Avg | Base Runtime | LoRA Runtime |
|-----------|--------------:|--------------:|---------:|---------:|-------------:|-------------:|
| c_exam_2025_strict_seeded | 4/4 | 3/4 | 78.5 | 64.8 | 0.75 | 0.5 |
| generated_c_tasks_v1 | 33/40 | 32/40 | 71.2 | 69.5 | 0.825 | 0.8 |
| pattern_only_benchmark_v1 | 10/10 | 10/10 | 85.0 | 85.0 | 1.0 | 1.0 |

## Guardrails

- No default adapter promotion.
- No formal SFT corpus modification.
- No benchmark scoring modification.
- No automatic adapter promotion.
- Existing adapter artifacts are not overwritten.

## Raw Reports

- `c_exam_2025_strict_seeded`: `C:\Users\User\OneDrive\Desktop\research-claw-code\local_ai\sft\reports\multi_benchmark_runs\c_exam_2025_strict_seeded\comparison_report.json`
- `generated_c_tasks_v1`: `C:\Users\User\OneDrive\Desktop\research-claw-code\local_ai\sft\reports\multi_benchmark_runs\generated_c_tasks_v1\comparison_report.json`
- `pattern_only_benchmark_v1`: `C:\Users\User\OneDrive\Desktop\research-claw-code\local_ai\sft\reports\multi_benchmark_runs\pattern_only_benchmark_v1\comparison_report.json`
