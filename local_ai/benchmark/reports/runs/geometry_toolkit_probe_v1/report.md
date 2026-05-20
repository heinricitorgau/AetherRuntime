# Benchmark Report

**Run ID**: `geometry_toolkit_probe_v1`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-05-17T21:14:33+00:00  
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
| Proxy response (no timeout/error) | 0% | 0/2 |
| Code not truncated | 0% | 0/2 |
| Compile pass | 0% | 0/2 |
| Runtime pass (output matches) | 0% | 0/2 |
| Semantic pass (no static errors) | 0% | 0/2 |
| Keyword pass (required constructs) | 0% | 0/2 |
| **Accepted** (score ≥ 60) | 0% | 0/2 |

Average score: **0.0/100**  
Score range: 0–0

## Score Distribution

| Bucket | Count |
|--------|------:|
| 90-100 | 0 |
| 70-89 | 0 |
| 60-69 | 0 |
| 0-59 | 2 |

## By Topic

| Topic | Count | Accepted | Avg Score |
|-------|------:|---------:|----------:|
| Geometry Toolkit | 2 | 0 | 0.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| hard | 2 | 0 | 0.0 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2022_exam2_002` | 0 | ✗ | ✗ | ✗ | ✗ | ✗ | no |
| `2023_exam2_002` | 0 | ✗ | ✗ | ✗ | ✗ | ✗ | no |

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated