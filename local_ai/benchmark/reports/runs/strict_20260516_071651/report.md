# Benchmark Report

**Run ID**: `strict_20260516_071651`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-05-16T07:28:51+00:00  
**Prompt file**: `You are a competitive programming code generator.

Rules:
* `  
**Mode**: strict_code_only (v2)  
**max_tokens**: 512  
**temperature**: 0.1
**proxy full timeout**: 300  
**proxy first-token timeout**: 90

---

## Pass Rates

| Dimension | Rate | Count |
|-----------|-----:|------:|
| Proxy response (no timeout/error) | 25% | 1/4 |
| Code not truncated | 25% | 1/4 |
| Compile pass | 25% | 1/4 |
| Runtime pass (output matches) | 25% | 1/4 |
| Semantic pass (no static errors) | 25% | 1/4 |
| Keyword pass (required constructs) | 25% | 1/4 |
| **Accepted** (score ≥ 60) | 25% | 1/4 |

Average score: **19.2/100**  
Score range: 0–77

## Score Distribution

| Bucket | Count |
|--------|------:|
| 90-100 | 0 |
| 70-89 | 1 |
| 60-69 | 0 |
| 0-59 | 3 |

## By Topic

| Topic | Count | Accepted | Avg Score |
|-------|------:|---------:|----------:|
| Game Simulation - Even/Odd Guessing | 1 | 0 | 0.0 |
| Geometry - Triangle Enumeration | 1 | 0 | 0.0 |
| Pattern Generation | 1 | 1 | 77.0 |
| Series Calculation | 1 | 0 | 0.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| medium | 4 | 1 | 19.2 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2025_midterm_002` | 77 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_001` | 0 | ✗ | ✗ | ✗ | ✗ | ✗ | no |
| `2025_midterm_003` | 0 | ✗ | ✗ | ✗ | ✗ | ✗ | no |
| `2025_midterm_004` | 0 | ✗ | ✗ | ✗ | ✗ | ✗ | no |

*Latency: avg 177968ms  min 177968ms  max 177968ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated
---

WARNING: regression against best known strict baseline strict_20260514_224452.
