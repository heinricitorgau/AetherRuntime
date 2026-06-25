# Benchmark Report

**Run ID**: `override_probe_3b_fixed`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-06-25T01:22:05+00:00  
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

Average score: **85.2/100**  
Score range: 70–100

## Score Distribution

| Bucket | Count |
|--------|------:|
| 90-100 | 2 |
| 70-89 | 2 |
| 60-69 | 0 |
| 0-59 | 0 |

## By Topic

| Topic | Count | Accepted | Avg Score |
|-------|------:|---------:|----------:|
| Game Simulation - Even/Odd Guessing | 1 | 1 | 94.0 |
| Geometry - Triangle Enumeration | 1 | 1 | 100.0 |
| Pattern Generation | 1 | 1 | 77.0 |
| Series Calculation | 1 | 1 | 70.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| medium | 4 | 4 | 85.2 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2025_midterm_003` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_004` | 94 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_002` | 77 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_001` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |

*Latency: avg 22996ms  min 14203ms  max 38703ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated
## Model Override

- requested_model: `qwen2.5-coder:3b`
- effective_model: `qwen2.5-coder:3b`
- proxy_config_model: `qwen2.5-coder:14b`
- model_override_valid: `True`
- benchmark_status: `completed`
