# Benchmark Report

**Run ID**: `baseline_20260515_041608`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-05-15T04:17:18+00:00  
**Prompt file**: `You are a C programming assistant. Output exactly one comple`  
**Mode**: default  
**max_tokens**: 768  
**temperature**: 0.0

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

Average score: **68.5/100**  
Score range: 27–100

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
| Game Simulation - Even/Odd Guessing | 1 | 0 | 27.0 |
| Geometry - Triangle Enumeration | 1 | 1 | 100.0 |
| Pattern Generation | 1 | 1 | 77.0 |
| Series Calculation | 1 | 1 | 70.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| medium | 4 | 3 | 68.5 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2025_midterm_003` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_002` | 77 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_001` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_004` | 27 | ✗ | ✗ | ✓ | ✓ | ✓ | no |

*Latency: avg 16367ms  min 6759ms  max 21476ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated