# Governance Status

Generated: `2026-06-25T06:25:28+00:00`

## Cross-Layer Headline

- No resource promoted to default in any layer.
- Awaiting manual review — model: `qwen25_coder_14b`

## Adapters

- Default: `None`

| Adapter | Status |
|---------|--------|
| `local_ai/sft/artifacts/retry_geometry_v3_guarded` | safe_no_change |

## Models

- Baseline: `qwen25_coder_3b`
- Default: `None`

| Model | Decision |
|-------|----------|
| `qwen25_coder_14b` | manual_review |

## Datasets

| Dataset | Decision | Candidate-ready |
|---------|----------|:---------------:|
| `generated_sft_candidate_v1` | promote_to_candidate_training | True |

## Regression

- Latest detector verdict: **regression** (`strict_20260514_222958` → `strict_20260514_223526`)
- Trend `qwen2.5-coder:14b`: improving (latest-pair regression)
- Trend `qwen2.5-coder:3b`: improving (latest-pair regression)

## Evaluation Reliability

- Verdict: **flaky** (stamp rate 0.141, flaky tasks 35, runs 85)

## Prompt / Profile Governance

- Decision: **pass** (approved 1/1, warnings 1)

## Goldens

- Approved goldens: 41 (human-verified: 0)

## Routing Governance

- Verdict: **pass** (violations 0)

## Guardrails

- Read-only observability; promotes nothing, trains nothing, runs no models.
- Reflects the registries/reports produced by the governed promotion gates.
