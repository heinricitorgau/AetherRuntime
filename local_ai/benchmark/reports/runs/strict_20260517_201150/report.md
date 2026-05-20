# Benchmark Report

**Run ID**: `strict_20260517_201150`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-05-17T20:41:55+00:00  
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
| Proxy response (no timeout/error) | 100% | 16/16 |
| Code not truncated | 94% | 15/16 |
| Compile pass | 50% | 8/16 |
| Runtime pass (output matches) | 31% | 5/16 |
| Semantic pass (no static errors) | 94% | 15/16 |
| Keyword pass (required constructs) | 69% | 11/16 |
| **Accepted** (score ≥ 60) | 50% | 8/16 |

Average score: **48.9/100**  
Score range: 11–90

## Score Distribution

| Bucket | Count |
|--------|------:|
| 90-100 | 3 |
| 70-89 | 5 |
| 60-69 | 0 |
| 0-59 | 8 |

## By Topic

| Topic | Count | Accepted | Avg Score |
|-------|------:|---------:|----------:|
| Alternating Series | 2 | 2 | 70.0 |
| Anagram Checker | 1 | 1 | 90.0 |
| Array Sorting and Weighted Sum | 2 | 2 | 90.0 |
| Board Game | 1 | 0 | 11.0 |
| Diamond Pattern | 1 | 1 | 85.0 |
| Geometry Toolkit | 2 | 0 | 15.0 |
| Guessing Board Game | 1 | 0 | 15.0 |
| Harmonic Prefix Array | 1 | 0 | 30.0 |
| Nearest Pair of Points | 1 | 0 | 30.0 |
| Phone Fee Aggregation | 1 | 1 | 80.0 |
| Random Walk Board | 2 | 0 | 11.0 |
| Series Array Generation | 1 | 1 | 70.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| hard | 7 | 1 | 22.6 |
| medium | 9 | 7 | 69.4 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2022_exam2_003` | 90 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2023_exam2_003` | 90 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2024_exam2_003` | 90 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2024_exam2_002` | 85 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2021_exam2_002` | 80 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2021_exam2_001` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `2022_exam2_001` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `2023_exam2_001` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `2021_exam2_003` | 30 | ✗ | ✗ | ✓ | ✓ | ✓ | no |
| `2024_exam2_001` | 30 | ✗ | ✗ | ✓ | ✓ | ✓ | no |
| `2021_exam2_004` | 15 | ✗ | ✗ | ✗ | ✓ | ✗ | no |
| `2022_exam2_002` | 15 | ✗ | ✗ | ✓ | ✗ | ✓ | no |
| `2023_exam2_002` | 15 | ✗ | ✗ | ✓ | ✗ | ✓ | no |
| `2022_exam2_004` | 11 | ✗ | ✗ | ✓ | ✗ | ✓ | no |
| `2023_exam2_004` | 11 | ✗ | ✗ | ✓ | ✗ | ✓ | no |
| `2024_exam2_004` | 11 | ✗ | ✗ | ✓ | ✗ | ✓ | no |

*Latency: avg 112040ms  min 37844ms  max 231421ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated
---

WARNING: regression against best known strict baseline strict_20260514_224452.
