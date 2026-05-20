# Benchmark Report

**Run ID**: `prompt_probe_exam2_v2`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-05-17T21:02:31+00:00  
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
| Proxy response (no timeout/error) | 100% | 3/3 |
| Code not truncated | 100% | 3/3 |
| Compile pass | 33% | 1/3 |
| Runtime pass (output matches) | 33% | 1/3 |
| Semantic pass (no static errors) | 100% | 3/3 |
| Keyword pass (required constructs) | 67% | 2/3 |
| **Accepted** (score ≥ 60) | 33% | 1/3 |

Average score: **48.3/100**  
Score range: 15–100

## Score Distribution

| Bucket | Count |
|--------|------:|
| 90-100 | 1 |
| 70-89 | 0 |
| 60-69 | 0 |
| 0-59 | 2 |

## By Topic

| Topic | Count | Accepted | Avg Score |
|-------|------:|---------:|----------:|
| Geometry Toolkit | 1 | 0 | 15.0 |
| Harmonic Prefix Array | 1 | 1 | 100.0 |
| Nearest Pair of Points | 1 | 0 | 30.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| hard | 1 | 0 | 15.0 |
| medium | 2 | 1 | 65.0 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2024_exam2_001` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2021_exam2_003` | 30 | ✗ | ✗ | ✓ | ✓ | ✓ | no |
| `2022_exam2_002` | 15 | ✗ | ✗ | ✓ | ✗ | ✓ | no |

*Latency: avg 94234ms  min 55530ms  max 118704ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated