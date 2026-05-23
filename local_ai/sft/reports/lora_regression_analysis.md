# LoRA Regression Analysis

Generated: 2026-05-23T18:15:20+00:00
Source report timestamp: 2026-05-23T18:15:09+00:00
Adapter: `local_ai\sft\artifacts\retry_geometry_v3_guarded`
Verdict: **no_change**

## Executive Answer

- Accepted stayed 4/4 -> 4/4.
- Compile stayed 1.0 -> 1.0.
- Runtime dropped 0.75 -> 0.75.
- Avg score delta is 0.0 points; task-score reconstruction gives 0.0.
- Largest damage: `2025_midterm_001` (Series Calculation), delta 0 points.

## Per-Task Delta

| Task | Topic | Base | LoRA | Delta | Compile | Runtime | Semantic | Keyword | New Missing Tokens |
|------|-------|-----:|-----:|------:|---------|---------|----------|---------|--------------------|
| 2025_midterm_001 | Series Calculation | 70 | 70 | 0 | pass->pass | fail->fail | pass->pass | pass->pass | - |
| 2025_midterm_002 | Pattern Generation | 77 | 77 | 0 | pass->pass | pass->pass | pass->pass | pass->pass | - |
| 2025_midterm_003 | Geometry - Triangle Enumeration | 85 | 85 | 0 | pass->pass | pass->pass | pass->pass | pass->pass | - |
| 2025_midterm_004 | Game Simulation - Even/Odd Guessing | 82 | 82 | 0 | pass->pass | pass->pass | pass->pass | pass->pass | - |

## Regression Tasks

No task-level regressions detected.
## Damage Attribution

- Interference verdict: **no_task_level_regression_detected**.
- Geometry regression tasks: -.
- Non-geometry regression tasks: -.
- Runtime pass-to-fail tasks: -.
- Assessment: The adapter preserves compile, semantic, and keyword checks but changes runtime behavior. The largest drop is on a geometry task, which is direct evidence that retry_geometry_v1 is not safe to promote as-is.

The average -4.5 is explained by task deltas: 2025_midterm_001=0, 2025_midterm_002=0, 2025_midterm_003=0, 2025_midterm_004=0. The large runtime failure is 2025_midterm_003: base produced `6.000`, LoRA produced repeated `4.146`, so both `area` and `6.000` became missing.

## Keep Or Reject

- Keep for production/default: **True**.
- Keep for analysis only: **False**.
- Recommendation: Adapter is acceptable to retain as a candidate.

## Next Training Strategy

- lower_epochs: The adapter preserved syntax but changed runtime behavior, a classic overfit signal.
- lower_learning_rate: Reduce behavioral drift while still nudging geometry repairs.
- lower_lora_rank: Constrain adapter capacity so a tiny repair set cannot dominate general task behavior.
- mix_base_sft_samples: Blend neutral base examples to preserve non-target runtime behavior.
- add_anti_regression_examples: Include tasks 2025_midterm_001/002/004 and the base-passing geometry behavior as guardrails.

## Non-Goals

This analysis did not modify `train_lora.py` or benchmark scoring.
