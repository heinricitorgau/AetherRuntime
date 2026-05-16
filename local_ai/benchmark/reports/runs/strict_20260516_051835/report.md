# Benchmark Report

**Run ID**: `strict_20260516_051835`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-05-16T05:23:48+00:00  
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
| Proxy response (no timeout/error) | 0% | 0/4 |
| Code not truncated | 0% | 0/4 |
| Compile pass | 0% | 0/4 |
| Runtime pass (output matches) | 0% | 0/4 |
| Semantic pass (no static errors) | 0% | 0/4 |
| Keyword pass (required constructs) | 0% | 0/4 |
| **Accepted** (score ≥ 60) | 0% | 0/4 |

Average score: **0.0/100**  
Score range: 0–0

## Score Distribution

| Bucket | Count |
|--------|------:|
| 90-100 | 0 |
| 70-89 | 0 |
| 60-69 | 0 |
| 0-59 | 4 |

## By Topic

| Topic | Count | Accepted | Avg Score |
|-------|------:|---------:|----------:|
| Game Simulation - Even/Odd Guessing | 1 | 0 | 0.0 |
| Geometry - Triangle Enumeration | 1 | 0 | 0.0 |
| Pattern Generation | 1 | 0 | 0.0 |
| Series Calculation | 1 | 0 | 0.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| medium | 4 | 0 | 0.0 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2025_midterm_001` | 0 | ✗ | ✗ | ✗ | ✗ | ✗ | no |
| `2025_midterm_002` | 0 | ✗ | ✗ | ✗ | ✗ | ✗ | no |
| `2025_midterm_003` | 0 | ✗ | ✗ | ✗ | ✗ | ✗ | no |
| `2025_midterm_004` | 0 | ✗ | ✗ | ✗ | ✗ | ✗ | no |

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated
---

WARNING: regression against best known strict baseline strict_20260514_224452.
