# Benchmark Report

**Run ID**: `?`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-05-14T20:56:26+00:00  
**Prompt file**: `You are a C programming assistant. Output exactly one comple`

---

## Pass Rates

| Dimension | Rate | Count |
|-----------|-----:|------:|
| Proxy response (no timeout/error) | 50% | 2/4 |
| Code not truncated | 50% | 2/4 |
| Compile pass | 50% | 2/4 |
| Runtime pass (output matches) | 25% | 1/4 |
| Semantic pass (no static errors) | 50% | 2/4 |
| Keyword pass (required constructs) | 50% | 2/4 |
| **Accepted** (score ≥ 60) | 50% | 2/4 |

Average score: **36.8/100**  
Score range: 0–77

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
| Game Simulation - Even/Odd Guessing | 1 | 0 | 0.0 |
| Geometry - Triangle Enumeration | 1 | 0 | 0.0 |
| Pattern Generation | 1 | 1 | 77.0 |
| Series Calculation | 1 | 1 | 70.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| medium | 4 | 2 | 36.8 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2025_midterm_002` | 77 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_001` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_003` | 0 | ✗ | ✗ | ✗ | ✗ | ✗ | no |
| `2025_midterm_004` | 0 | ✗ | ✗ | ✗ | ✗ | ✗ | no |

*Latency: avg 94096ms  min 60666ms  max 127526ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated