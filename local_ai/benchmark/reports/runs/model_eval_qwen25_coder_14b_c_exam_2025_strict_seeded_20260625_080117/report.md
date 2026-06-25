# Benchmark Report

**Run ID**: `model_eval_qwen25_coder_14b_c_exam_2025_strict_seeded_20260625_080117`  
**Model**: `qwen2.5-coder:14b`  
**Timestamp**: 2026-06-25T00:07:36+00:00  
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
| Compile pass | 75% | 3/4 |
| Runtime pass (output matches) | 50% | 2/4 |
| Semantic pass (no static errors) | 100% | 4/4 |
| Keyword pass (required constructs) | 100% | 4/4 |
| **Accepted** (score ≥ 60) | 75% | 3/4 |

Average score: **66.5/100**  
Score range: 22–97

## Score Distribution

| Bucket | Count |
|--------|------:|
| 90-100 | 1 |
| 70-89 | 2 |
| 60-69 | 0 |
| 0-59 | 1 |

## By Topic

| Topic | Count | Accepted | Avg Score |
|-------|------:|---------:|----------:|
| Game Simulation - Even/Odd Guessing | 1 | 1 | 97.0 |
| Geometry - Triangle Enumeration | 1 | 0 | 22.0 |
| Pattern Generation | 1 | 1 | 77.0 |
| Series Calculation | 1 | 1 | 70.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| medium | 4 | 3 | 66.5 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2025_midterm_004` | 97 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_002` | 77 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_001` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_003` | 22 | ✗ | ✗ | ✓ | ✓ | ✓ | no |

*Latency: avg 94444ms  min 38797ms  max 172171ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated