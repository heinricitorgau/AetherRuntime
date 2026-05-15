# Benchmark Report

**Run ID**: `strict_20260514_222915`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-05-14T22:29:32+00:00  
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

Average score: **72.0/100**  
Score range: 72–72

## Score Distribution

| Bucket | Count |
|--------|------:|
| 90-100 | 0 |
| 70-89 | 1 |
| 60-69 | 0 |
| 0-59 | 0 |

## By Topic

| Topic | Count | Accepted | Avg Score |
|-------|------:|---------:|----------:|
| Game Simulation - Even/Odd Guessing | 1 | 1 | 72.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| medium | 1 | 1 | 72.0 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2025_midterm_004` | 72 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |

*Latency: avg 16446ms  min 16446ms  max 16446ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated