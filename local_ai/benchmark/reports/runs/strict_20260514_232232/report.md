# Benchmark Report

**Run ID**: `strict_20260514_232232`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-05-14T23:23:39+00:00  
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
| Proxy response (no timeout/error) | 100% | 4/4 |
| Code not truncated | 75% | 3/4 |
| Compile pass | 50% | 2/4 |
| Runtime pass (output matches) | 25% | 1/4 |
| Semantic pass (no static errors) | 75% | 3/4 |
| Keyword pass (required constructs) | 100% | 4/4 |
| **Accepted** (score ≥ 60) | 50% | 2/4 |

Average score: **48.5/100**  
Score range: 17–77

## Score Distribution

| Bucket | Count |
|--------|------:|
| 90-100 | 0 |
| 70-89 | 2 |
| 60-69 | 0 |
| 0-59 | 2 |

## By Topic

| Topic | Count | Accepted | Avg Score |
|-------|------:|---------:|----------:|
| Game Simulation - Even/Odd Guessing | 1 | 0 | 17.0 |
| Geometry - Triangle Enumeration | 1 | 0 | 30.0 |
| Pattern Generation | 1 | 1 | 77.0 |
| Series Calculation | 1 | 1 | 70.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| medium | 4 | 2 | 48.5 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2025_midterm_002` | 77 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_001` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `2025_midterm_003` | 30 | ✗ | ✗ | ✓ | ✓ | ✓ | no |
| `2025_midterm_004` | 17 | ✗ | ✗ | ✗ | ✓ | ✗ | no |

*Latency: avg 16207ms  min 10766ms  max 20109ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated
---

WARNING: regression against best known strict baseline strict_20260514_224452.
