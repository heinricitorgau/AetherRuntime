# Benchmark Report

**Run ID**: `strict_20260514_222153`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-05-14T22:22:47+00:00  
**Prompt file**: `You are a competitive programming code generator.

Rules:
* `

---

## Pass Rates

| Dimension | Rate | Count |
|-----------|-----:|------:|
| Proxy response (no timeout/error) | 100% | 4/4 |
| Code not truncated | 100% | 4/4 |
| Compile pass | 50% | 2/4 |
| Runtime pass (output matches) | 25% | 1/4 |
| Semantic pass (no static errors) | 100% | 4/4 |
| Keyword pass (required constructs) | 50% | 2/4 |
| **Accepted** (score ≥ 60) | 50% | 2/4 |

Average score: **44.0/100**  
Score range: 14–77

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
| Game Simulation - Even/Odd Guessing | 1 | 0 | 14.0 |
| Geometry - Triangle Enumeration | 1 | 0 | 15.0 |
| Pattern Generation | 1 | 1 | 77.0 |
| Series Calculation | 1 | 1 | 70.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| medium | 4 | 2 | 44.0 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2025_midterm_002` | 77 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_001` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_003` | 15 | ✗ | ✗ | ✓ | ✗ | ✓ | no |
| `2025_midterm_004` | 14 | ✗ | ✗ | ✓ | ✗ | ✓ | no |

*Latency: avg 12915ms  min 9088ms  max 16345ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated