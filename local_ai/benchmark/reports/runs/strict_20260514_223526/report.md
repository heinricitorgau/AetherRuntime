# Benchmark Report

**Run ID**: `strict_20260514_223526`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-05-14T22:36:26+00:00  
**Prompt file**: `You are a competitive programming code generator.

Rules:
* `  
**Mode**: strict_code_only (v2)  
**max_tokens**: 512  
**temperature**: 0.1

---

## Pass Rates

| Dimension | Rate | Count |
|-----------|-----:|------:|
| Proxy response (no timeout/error) | 100% | 4/4 |
| Code not truncated | 75% | 3/4 |
| Compile pass | 50% | 2/4 |
| Runtime pass (output matches) | 25% | 1/4 |
| Semantic pass (no static errors) | 75% | 3/4 |
| Keyword pass (required constructs) | 75% | 3/4 |
| **Accepted** (score ≥ 60) | 50% | 2/4 |

Average score: **44.8/100**  
Score range: 15–77

## Score Distribution

| Bucket | Count |
|--------|------:|
| 90-100 | 0 |
| 70-89 | 2 |
| 60-69 | 0 |
| 0-59 | 2 |

## By Topic

| Topic | Count | Accepted | Avg Score |
|-------|------:|---------:|----------:|
| Game Simulation - Even/Odd Guessing | 1 | 0 | 17.0 |
| Geometry - Triangle Enumeration | 1 | 0 | 15.0 |
| Pattern Generation | 1 | 1 | 77.0 |
| Series Calculation | 1 | 1 | 70.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| medium | 4 | 2 | 44.8 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2025_midterm_002` | 77 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_001` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_004` | 17 | ✗ | ✗ | ✗ | ✓ | ✗ | no |
| `2025_midterm_003` | 15 | ✗ | ✗ | ✓ | ✗ | ✓ | no |

*Latency: avg 14486ms  min 10051ms  max 19038ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated