# Generated Benchmark Analysis

Generated: `2026-05-25T17:17:07+00:00`
Run: `strict_20260523_205251`
Run directory: `C:\Users\User\OneDrive\Desktop\research-claw-code\local_ai\benchmark\reports\runs\strict_20260523_205251`

## Summary

- Tasks: 40
- Accepted: 34/40
- Rejected: 6
- Average score: 82.5
- Low score cases (< 60): 6
- Compile failures: 6
- Runtime failures: 12
- Semantic failures: 2
- Keyword failures: 0

## Decision Answers

- Isolated evaluation: Yes, with caveats. The generated benchmark is balanced across four topics and exposes useful compile/runtime gaps. Golden comparison skipping is expected because this run has 40 generated tasks while the golden baseline has 4 tasks.
- Candidate training corpus: generated_sft_candidate_v1 is suitable as an isolated candidate corpus only if it uses validated reference solutions, keeps these benchmark outputs out of training, and preserves a held-out generated evaluation split. Do not train on failed model outputs from this benchmark run.
- Topics needing more data or checker work: game_simulation, geometry, pattern_generation, series_calculation
- Task spec issues: No confirmed task_spec_issue was detected among the six unaccepted cases. However, runtime token mismatches in geometry and pattern_generation should be audited before those exact tasks are used as promotion-quality evaluation.

## By Topic

| Topic | Count | Accepted | Rejected | Avg | Low | Compile Fail | Runtime Fail | Semantic Fail | Keyword Fail |
|---|---|---|---|---|---|---|---|---|---|
| game_simulation | 10 | 8 | 2 | 72 | 2 | 2 | 4 | 2 | 0 |
| geometry | 10 | 8 | 2 | 80 | 2 | 2 | 4 | 0 | 0 |
| pattern_generation | 10 | 10 | 0 | 92 | 0 | 0 | 2 | 0 | 0 |
| series_calculation | 10 | 8 | 2 | 86 | 2 | 2 | 2 | 0 | 0 |

## By Difficulty

| Difficulty | Count | Accepted | Rejected | Avg | Low | Compile Fail | Runtime Fail | Semantic Fail | Keyword Fail |
|---|---|---|---|---|---|---|---|---|---|
| easy | 17 | 16 | 1 | 88.82 | 1 | 1 | 3 | 0 | 0 |
| hard | 13 | 11 | 2 | 83.85 | 2 | 2 | 4 | 0 | 0 |
| medium | 10 | 7 | 3 | 70 | 3 | 3 | 5 | 2 | 0 |

## Failed Cases

| ID | Topic | Difficulty | Score | Failed Checks | Compile Evidence | Missing Tokens |
|---|---|---|---|---|---|---|
| synthetic_v3_game_simulation_001 | game_simulation | medium | 15 | proxy, truncation, structure, compile, runtime, semantic | no code extracted | Numbers, Pick, points |
| synthetic_v3_game_simulation_002 | game_simulation | medium | 15 | proxy, truncation, structure, compile, runtime, semantic | no code extracted | Guess, number, points |
| synthetic_v3_geometry_002 | geometry | easy | 30 | compile, runtime | C:\Users\User\AppData\Local\Temp\bench_build_kp7jvfc5\synthetic_v3_geometry_002.c:17:5: er | area, 6.000 |
| synthetic_v3_geometry_010 | geometry | hard | 30 | compile, runtime | C:\Users\User\AppData\Local\Temp\bench_build_kp7jvfc5\synthetic_v3_geometry_010.c:17:5: er | area, 6.000 |
| synthetic_v3_series_calculation_004 | series_calculation | hard | 30 | compile, runtime | C:\Users\User\AppData\Local\Temp\bench_build_kp7jvfc5\synthetic_v3_series_calculation_004. | result |
| synthetic_v3_series_calculation_008 | series_calculation | medium | 30 | compile, runtime | C:\Users\User\AppData\Local\Temp\bench_build_kp7jvfc5\synthetic_v3_series_calculation_008. | result |

## Low Score Classification

| ID | Topic | Difficulty | Score | Classification | Evidence |
|---|---|---|---|---|---|
| synthetic_v3_game_simulation_001 | game_simulation | medium | 15 | model_generation_failure | proxy/empty response prevented code extraction; structure check reported empty response; semantic errors: empty code; compile: no code extra |
| synthetic_v3_game_simulation_002 | game_simulation | medium | 15 | model_generation_failure | proxy/empty response prevented code extraction; structure check reported empty response; semantic errors: empty code; compile: no code extra |
| synthetic_v3_geometry_002 | geometry | easy | 30 | model_generation_failure | generated code does not compile cleanly under strict C99; compile: compile error (1 errors); missing runtime tokens: area, 6.000 |
| synthetic_v3_geometry_010 | geometry | hard | 30 | model_generation_failure | generated code does not compile cleanly under strict C99; compile: compile error (1 errors); missing runtime tokens: area, 6.000 |
| synthetic_v3_series_calculation_004 | series_calculation | hard | 30 | model_generation_failure | generated code does not compile cleanly under strict C99; compile: compile error (1 errors); missing runtime tokens: result |
| synthetic_v3_series_calculation_008 | series_calculation | medium | 30 | model_generation_failure | generated code does not compile cleanly under strict C99; compile: compile error (1 errors); missing runtime tokens: result |

## Recommendations

- Treat `generated_c_tasks_v1` as a useful isolated evaluation set, not as a golden baseline replacement.
- Use `generated_sft_candidate_v1` only from validated reference solutions and keep a held-out split for generated benchmark evaluation.
- Audit game_simulation timeouts and the geometry/pattern runtime token expectations before relying on those checks for promotion decisions.
- Do not train on the six failed benchmark outputs; they are model/proxy failures, not trusted repair targets.
