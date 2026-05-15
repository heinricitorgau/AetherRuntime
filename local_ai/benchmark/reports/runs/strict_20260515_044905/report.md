# Benchmark Report

**Run ID**: `strict_20260515_044905`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-05-15T04:49:56+00:00  
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
| Code not truncated | 100% | 4/4 |
| Compile pass | 100% | 4/4 |
| Runtime pass (output matches) | 75% | 3/4 |
| Semantic pass (no static errors) | 100% | 4/4 |
| Keyword pass (required constructs) | 100% | 4/4 |
| **Accepted** (score ≥ 60) | 100% | 4/4 |

Average score: **82.2/100**  
Score range: 70–96

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
| Geometry - Triangle Enumeration | 1 | 1 | 96.0 |
| Pattern Generation | 1 | 1 | 77.0 |
| Series Calculation | 1 | 1 | 70.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| medium | 4 | 4 | 82.2 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2025_midterm_003` | 96 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_004` | 86 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_002` | 77 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_001` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |

*Latency: avg 11846ms  min 7708ms  max 17947ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated