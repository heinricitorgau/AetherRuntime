# Benchmark Report

**Run ID**: `strict_20260514_222050`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-05-14T22:21:10+00:00  
**Prompt file**: `You are a competitive programming code generator.

Rules:
* `

---

## Pass Rates

| Dimension | Rate | Count |
|-----------|-----:|------:|
| Proxy response (no timeout/error) | 100% | 1/1 |
| Code not truncated | 100% | 1/1 |
| Compile pass | 0% | 0/1 |
| Runtime pass (output matches) | 0% | 0/1 |
| Semantic pass (no static errors) | 100% | 1/1 |
| Keyword pass (required constructs) | 0% | 0/1 |
| **Accepted** (score ≥ 60) | 0% | 0/1 |

Average score: **15.0/100**  
Score range: 15–15

## Score Distribution

| Bucket | Count |
|--------|------:|
| 90-100 | 0 |
| 70-89 | 0 |
| 60-69 | 0 |
| 0-59 | 1 |

## By Topic

| Topic | Count | Accepted | Avg Score |
|-------|------:|---------:|----------:|
| Geometry - Triangle Enumeration | 1 | 0 | 15.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| medium | 1 | 0 | 15.0 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2025_midterm_003` | 15 | ✗ | ✗ | ✓ | ✗ | ✓ | no |

*Latency: avg 19790ms  min 19790ms  max 19790ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated