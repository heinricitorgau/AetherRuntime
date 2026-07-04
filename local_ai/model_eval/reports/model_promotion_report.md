# Model Promotion Report

Generated: `2026-06-25T05:51:49+00:00`  
Baseline: `qwen25_coder_3b`  
Decision: **manual_review**  
Promotion level: `off_ladder`  
Recommendation: **manual review required for qwen25_coder_14b**  
Reason: strict benchmark regressed (-16.7 avg) while generated benchmark materially improved (+14.4 avg); conflicting evidence requires human decision  
Registry updated: `C:\Users\User\OneDrive\Desktop\research-claw-code\local_ai\model_eval\models\approved_models.json`

## Policy

| Setting | Value |
|---------|------:|
| strict_weight | 0.6 |
| generated_weight | 0.4 |
| require_override_valid | True |
| material_score_gain | 3.0 |
| promotion_levels | reject, candidate, safe, default |

Strict benchmark: `c_exam_2025_strict_seeded`  
Generated benchmark: `generated_c_tasks_v1`

## Candidate Decisions

### `qwen25_coder_14b` → manual_review

- Promotion level: `off_ladder`
- Weighted score delta: -4.26
- Override valid: True

**Strict benchmark**

| Metric | Delta |
|--------|------:|
| avg_score_delta | -16.7 |
| accepted_delta | -1 |
| compile_delta | -0.25 |
| runtime_delta | -0.25 |
| semantic_delta | 0.0 |

**Generated benchmark**

| Metric | Delta |
|--------|------:|
| avg_score_delta | 14.4 |
| accepted_delta | 4 |
| compile_delta | 0.1 |
| runtime_delta | 0.3 |
| semantic_delta | 0.0 |

**Reasons**

- strict benchmark regressed (-16.7 avg) while generated benchmark materially improved (+14.4 avg)
- conflicting evidence requires human decision

## Guardrails

- Recommendation comes from `promotion_policy.py`; nothing is hard-coded.
- A strict regression with a material generated gain resolves to `manual_review`.
- `invalid_model_override` blocks promotion entirely.
- This script does not train, change benchmark scoring, datasets, routing, or adapters.
