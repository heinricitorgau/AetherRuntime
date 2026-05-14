# Benchmark Report

**Run ID**: `?`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-05-14T20:35:25+00:00  
**Prompt file**: `You are a C programming assistant. Output exactly one comple`

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

Average score: **77.0/100**  
Score range: 77–77

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
| Pattern Generation | 1 | 1 | 77.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| medium | 1 | 1 | 77.0 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2025_midterm_002` | 77 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |

*Latency: avg 218059ms  min 218059ms  max 218059ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated