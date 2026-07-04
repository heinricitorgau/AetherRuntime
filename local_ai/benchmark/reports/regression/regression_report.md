# Benchmark Regression Report

Generated: `2026-06-25T05:47:48+00:00`  
Base run: `strict_20260514_222958`  
New run: `strict_20260514_223526`  
Verdict: **regression**

## Policy

| Threshold | Value |
|-----------|------:|
| accepted_drop_tolerance | 0 |
| avg_score_drop_tolerance | 1.0 |
| rate_drop_tolerance | 0.0 |
| per_task_drop_tolerance | 20 |
| max_newly_broken | 0 |
| improvement_avg_score_gain | 1.0 |

## Metrics

| Metric | Delta |
|--------|------:|
| accepted_delta | -1 |
| avg_score_delta | -11.8 |
| compile_delta | -0.25 |
| runtime_delta | 0.0 |
| newly_broken | 1 |
| newly_fixed | 0 |
| tasks_compared | 4 |

## Regression Reasons

- accepted dropped by 1
- avg score dropped by 11.8
- compile pass-rate dropped by 0.250
- 1 task(s) newly broken
- 1 task(s) dropped > 20 pts (2025_midterm_004)

## Improvement Reasons

None.

## Newly Broken

| Task | Base | New |
|------|-----:|----:|
| `2025_midterm_004` | 64 | 17 |

## Largest Single-Task Drop

- Task: `2025_midterm_004`
- Base: 64.0 → New: 17.0 (delta -47.0)

## Guardrails

- Verdict derived from the regression policy; nothing hard-coded.
- Read-only over existing run reports; does not run models or change scoring.
- `regression` exits non-zero so promotion gates and CI can block automatically.
