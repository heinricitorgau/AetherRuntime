# Benchmark Report

**Run ID**: `strict_20260515_042607`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-05-15T04:26:32+00:00  
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
| Proxy response (no timeout/error) | 100% | 1/1 |
| Code not truncated | 100% | 1/1 |
| Compile pass | 100% | 1/1 |
| Runtime pass (output matches) | 100% | 1/1 |
| Semantic pass (no static errors) | 100% | 1/1 |
| Keyword pass (required constructs) | 100% | 1/1 |
| **Accepted** (score ≥ 60) | 100% | 1/1 |

Average score: **96.0/100**  
Score range: 96–96

## Score Distribution

| Bucket | Count |
|--------|------:|
| 90-100 | 1 |
| 70-89 | 0 |
| 60-69 | 0 |
| 0-59 | 0 |

## By Topic

| Topic | Count | Accepted | Avg Score |
|-------|------:|---------:|----------:|
| Geometry - Triangle Enumeration | 1 | 1 | 96.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| medium | 1 | 1 | 96.0 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2025_midterm_003` | 96 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |

*Latency: avg 21813ms  min 21813ms  max 21813ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated
---

WARNING: regression against best known strict baseline strict_20260514_224452.
