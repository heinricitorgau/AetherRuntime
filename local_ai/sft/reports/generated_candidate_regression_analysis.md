# Generated Candidate Regression Analysis

Generated: `2026-05-25T19:28:01+00:00`
Adapter: `local_ai\sft\artifacts\generated_candidate_v1`
Status: **reject**

## Conclusion

generated_candidate_v1 status = reject. Do not promote, do not use as default, and keep it only as an ablation artifact.

- Do not promote.
- Do not use as default.
- Keep as ablation artifact.
- Do not continue training this full generated_sft_candidate_v1 adapter.

## Strict Benchmark

- Accepted delta: 0
- Avg delta: -3.7
- Runtime delta: -0.25
- Largest drop: `2025_midterm_004 (82.0 -> 67.0, delta -15.0)`

| Task | Base | LoRA | Delta | Runtime Regressed | Compile Regressed | LoRA Missing Tokens |
|---|---|---|---|---|---|---|
| 2025_midterm_001 | 70.0 | 70.0 | 0.0 | False | False | 0.607 |
| 2025_midterm_002 | 77.0 | 77.0 | 0.0 | False | False | 2 2, 11111, 222 |
| 2025_midterm_003 | 85.0 | 85.0 | 0.0 | False | False | area |
| 2025_midterm_004 | 82.0 | 67.0 | -15.0 | True | False | Numbers, win, points, Pick |

## Generated Benchmark

- Accepted delta: -1
- Avg delta: -1.7
- Runtime delta: -0.025
- Compile delta: -0.025

| Task | Topic | Difficulty | Base | LoRA | Delta | Runtime Regressed | Compile Regressed |
|---|---|---|---|---|---|---|---|
| synthetic_v3_game_simulation_010 | game_simulation | medium | 85.0 | 15.0 | -70.0 | True | True |
| synthetic_v3_game_simulation_001 | game_simulation | medium | 15.0 | 15.0 | 0.0 | False | False |
| synthetic_v3_game_simulation_002 | game_simulation | medium | 15.0 | 15.0 | 0.0 | False | False |
| synthetic_v3_game_simulation_003 | game_simulation | easy | 65.0 | 65.0 | 0.0 | False | False |
| synthetic_v3_game_simulation_004 | game_simulation | hard | 75.0 | 75.0 | 0.0 | False | False |
| synthetic_v3_game_simulation_005 | game_simulation | hard | 15.0 | 15.0 | 0.0 | False | False |
| synthetic_v3_game_simulation_006 | game_simulation | hard | 15.0 | 15.0 | 0.0 | False | False |
| synthetic_v3_game_simulation_007 | game_simulation | easy | 65.0 | 65.0 | 0.0 | False | False |
| synthetic_v3_game_simulation_008 | game_simulation | easy | 75.0 | 75.0 | 0.0 | False | False |
| synthetic_v3_game_simulation_009 | game_simulation | easy | 15.0 | 15.0 | 0.0 | False | False |

## By Topic

| Topic | Count | Avg Delta | Accepted Delta | Runtime Regr. | Compile Regr. | Largest Drop |
|---|---|---|---|---|---|---|
| game_simulation | 10 | -7.0 | -1 | 1 | 1 | synthetic_v3_game_simulation_010 (85.0 -> 15.0, delta -70.0) |
| geometry | 10 | 0.0 | 0 | 0 | 0 | synthetic_v3_geometry_001 (85.0 -> 85.0, delta 0.0) |
| pattern_generation | 10 | 0.0 | 0 | 0 | 0 | synthetic_v3_pattern_generation_001 (85.0 -> 85.0, delta 0.0) |
| series_calculation | 10 | 0.0 | 0 | 0 | 0 | synthetic_v3_series_calculation_001 (85.0 -> 85.0, delta 0.0) |

## By Difficulty

| Difficulty | Count | Avg Delta | Accepted Delta | Runtime Regr. | Compile Regr. | Largest Drop |
|---|---|---|---|---|---|---|
| easy | 17 | 0.0 | 0 | 0 | 0 | synthetic_v3_game_simulation_003 (65.0 -> 65.0, delta 0.0) |
| hard | 13 | 0.0 | 0 | 0 | 0 | synthetic_v3_game_simulation_004 (75.0 -> 75.0, delta 0.0) |
| medium | 10 | -7.0 | -1 | 1 | 1 | synthetic_v3_game_simulation_010 (85.0 -> 15.0, delta -70.0) |

## Regression Pattern

- Concentrated topic(s): game_simulation
- Runtime regression: True
- Compile regression: True
- Model output style changed: True
- Likely generated candidate over-regularization: True
- Both strict and generated benchmarks regressed, so this is not just synthetic overfit.
- Strict regression is concentrated in the game simulation task 2025_midterm_004 runtime behavior.
- Generated regression is dominated by game_simulation_010, where LoRA output loses compile/runtime correctness.
- The small global generated avg drop is caused by a narrow but severe game_simulation drop, not broad topic collapse.

## Next Strategy

### topic_specific_small_adapter
- Train pattern_only_candidate_v1 or series_only_candidate_v1 instead of all 40 generated tasks.
- Avoid game_simulation in the next candidate until game runtime behavior is guarded.

### reduce_dataset_noise
- Remove or audit low-score generated benchmark cases.
- Use only high-confidence generated tasks with stable compile/runtime outcomes.

### build_filtered_generated_corpus
- Prefer accepted_by_base=false but reference_solution verified tasks when targeting improvement.
- Alternatively build topic-specific selected sets rather than training on all 40 at once.
- Keep strict benchmark and generated benchmark comparison mandatory for every candidate.
