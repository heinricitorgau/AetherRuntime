# Benchmark Trend Report

Generated: `2026-06-25T05:58:53+00:00`  
Total runs: 85  
Models tracked: 2

## `qwen2.5-coder:14b`

- Runs: 11
- Trend: **improving** (first 66.5 → latest 93.8)
- Latest-pair regression verdict: **regression** (`model_eval_qwen25_coder_14b_c_exam_2025_strict_seeded_20260625_114958` → `model_eval_qwen25_coder_14b_generated_c_tasks_v1_20260625_115605`)
  - regression: 3 task(s) newly broken

| Run | Timestamp | Accepted | Avg | Compile | Runtime |
|-----|-----------|---------:|----:|--------:|--------:|
| `model_eval_qwen25_coder_14b_c_exam_2025_strict_seeded_20260625_082302` | 2026-06-25T00:29:22+00:00 | 3 | 66.5 | 0.75 | 0.5 |
| `override_probe_14b` | 2026-06-25T01:04:37+00:00 | 3 | 66.5 | 0.75 | 0.5 |
| `override_probe_14b_fixed` | 2026-06-25T01:29:10+00:00 | 3 | 66.5 | 0.75 | 0.5 |
| `model_eval_qwen25_coder_14b_c_exam_2025_strict_seeded_20260625_093121` | 2026-06-25T01:37:30+00:00 | 3 | 66.5 | 0.75 | 0.5 |
| `model_eval_qwen25_coder_14b_c_exam_2025_strict_seeded_20260625_095548` | 2026-06-25T02:01:54+00:00 | 3 | 66.5 | 0.75 | 0.5 |
| `model_eval_qwen25_coder_14b_generated_c_tasks_v1_20260625_100158` | 2026-06-25T02:39:03+00:00 | 38 | 95.8 | 0.95 | 0.95 |
| `model_eval_qwen25_coder_14b_c_exam_2025_strict_seeded_20260625_114958` | 2026-06-25T03:56:01+00:00 | 3 | 66.5 | 0.75 | 0.5 |
| `model_eval_qwen25_coder_14b_generated_c_tasks_v1_20260625_115605` | 2026-06-25T04:31:27+00:00 | 37 | 93.8 | 0.925 | 0.925 |

## `qwen2.5-coder:3b`

- Runs: 74
- Trend: **improving** (first 0.0 → latest 79.4)
- Latest-pair regression verdict: **regression** (`model_eval_qwen25_coder_3b_c_exam_2025_strict_seeded_20260625_113719` → `model_eval_qwen25_coder_3b_generated_c_tasks_v1_20260625_113845`)
  - regression: avg score dropped by 3.9
  - regression: compile pass-rate dropped by 0.175
  - regression: runtime pass-rate dropped by 0.125
  - regression: 4 task(s) newly broken

| Run | Timestamp | Accepted | Avg | Compile | Runtime |
|-----|-----------|---------:|----:|--------:|--------:|
| `model_eval_qwen25_coder_3b_c_exam_2025_strict_seeded_20260625_081718` | 2026-06-25T00:23:02+00:00 | 3 | 66.5 | 0.75 | 0.5 |
| `override_probe_3b` | 2026-06-25T00:57:27+00:00 | 3 | 66.5 | 0.75 | 0.5 |
| `override_probe_3b_fixed` | 2026-06-25T01:22:05+00:00 | 4 | 85.2 | 1.0 | 0.75 |
| `model_eval_qwen25_coder_3b_c_exam_2025_strict_seeded_20260625_092948` | 2026-06-25T01:31:21+00:00 | 4 | 83.2 | 1.0 | 0.75 |
| `model_eval_qwen25_coder_3b_c_exam_2025_strict_seeded_20260625_094401` | 2026-06-25T01:45:21+00:00 | 4 | 83.2 | 1.0 | 0.75 |
| `model_eval_qwen25_coder_3b_generated_c_tasks_v1_20260625_094524` | 2026-06-25T01:55:46+00:00 | 34 | 83.0 | 0.85 | 0.675 |
| `model_eval_qwen25_coder_3b_c_exam_2025_strict_seeded_20260625_113719` | 2026-06-25T03:38:43+00:00 | 4 | 83.2 | 1.0 | 0.75 |
| `model_eval_qwen25_coder_3b_generated_c_tasks_v1_20260625_113845` | 2026-06-25T03:49:57+00:00 | 33 | 79.4 | 0.825 | 0.625 |

## Guardrails

- Read-only over existing run reports; does not run models or change scoring.
- Regression verdicts come from the canonical `regression_policy`.
