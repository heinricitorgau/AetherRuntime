# Benchmark Report

**Run ID**: `model_eval_qwen25_coder_3b_c_exam_2025_strict_seeded_20260625_094401`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-06-25T01:45:21+00:00  
**Prompt file**: `You are a competitive programming code generator.

Rules:
* `  
**Mode**: strict_code_only (v2)  
**max_tokens**: 512  
**temperature**: 0.1
**proxy full timeout**: 660  
**proxy first-token timeout**: 180

---

## Pass Rates

| Dimension | Rate | Count |
|-----------|-----:|------:|
| Proxy response (no timeout/error) | 100% | 4/4 |
| Code not truncated | 100% | 4/4 |
| Compile pass | 100% | 4/4 |
| Runtime pass (output matches) | 75% | 3/4 |
| Semantic pass (no static errors) | 100% | 4/4 |
| Keyword pass (required constructs) | 100% | 4/4 |
| **Accepted** (score ≥ 60) | 100% | 4/4 |

Average score: **83.2/100**  
Score range: 70–100

## Score Distribution

| Bucket | Count |
|--------|------:|
| 90-100 | 1 |
| 70-89 | 3 |
| 60-69 | 0 |
| 0-59 | 0 |

## By Topic

| Topic | Count | Accepted | Avg Score |
|-------|------:|---------:|----------:|
| Game Simulation - Even/Odd Guessing | 1 | 1 | 86.0 |
| Geometry - Triangle Enumeration | 1 | 1 | 100.0 |
| Pattern Generation | 1 | 1 | 77.0 |
| Series Calculation | 1 | 1 | 70.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| medium | 4 | 4 | 83.2 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2025_midterm_003` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_004` | 86 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_002` | 77 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_001` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |

*Latency: avg 19601ms  min 12500ms  max 34327ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated
## Model Override

- requested_model: `qwen2.5-coder:3b`
- effective_model: `qwen2.5-coder:3b`
- proxy_config_model: `qwen2.5-coder:14b`
- model_override_valid: `True`
- benchmark_status: `completed`
