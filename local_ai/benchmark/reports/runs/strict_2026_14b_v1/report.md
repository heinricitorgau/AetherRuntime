# Benchmark Report

**Run ID**: `strict_2026_14b_v1`  
**Model**: `qwen2.5-coder:14b`  
**Timestamp**: 2026-07-07T07:53:10+00:00  
**Prompt file**: `You are a competitive programming code generator.

Rules:
* `  
**Mode**: strict_code_only (v2)  
**max_tokens**: 512  
**temperature**: 0.1
**proxy full timeout**: 600  
**proxy first-token timeout**: 180

---

## Pass Rates

| Dimension | Rate | Count |
|-----------|-----:|------:|
| Proxy response (no timeout/error) | 100% | 9/9 |
| Code not truncated | 78% | 7/9 |
| Compile pass | 67% | 6/9 |
| Runtime pass (output matches) | 56% | 5/9 |
| Semantic pass (no static errors) | 78% | 7/9 |
| Keyword pass (required constructs) | 100% | 9/9 |
| **Accepted** (score ≥ 60) | 67% | 6/9 |

Average score: **63.8/100**  
Score range: 19–100

## Score Distribution

| Bucket | Count |
|--------|------:|
| 90-100 | 2 |
| 70-89 | 4 |
| 60-69 | 0 |
| 0-59 | 3 |

## By Topic

| Topic | Count | Accepted | Avg Score |
|-------|------:|---------:|----------:|
| Game Simulation - Letter Flip Match | 1 | 1 | 81.0 |
| Game Simulation - Poker Match | 1 | 1 | 81.0 |
| Geometry - Farthest and Closest Point Pairs | 1 | 0 | 19.0 |
| Geometry - Line and Parabola Intersection | 1 | 0 | 19.0 |
| Numerical Roots - Cubic plus d*sin(x) | 1 | 0 | 19.0 |
| Pattern Generation - Diamond | 1 | 1 | 85.0 |
| Pattern Generation - Diamond (odd rows) | 1 | 1 | 70.0 |
| Series Calculation - Alternating Reciprocal Squares | 1 | 1 | 100.0 |
| Series Calculation - Quasi-geometric Product | 1 | 1 | 100.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| hard | 5 | 2 | 43.8 |
| medium | 4 | 4 | 88.8 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `2026_exam1_series_product` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2026_exam2_series_alt_square` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2026_exam1_pattern_diamond` | 85 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2026_exam1_poker_match` | 81 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2026_exam2_letter_flip_game` | 81 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `2026_exam2_pattern_diamond` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `2026_exam1_geometry_line_parabola` | 19 | ✗ | ✗ | ✗ | ✓ | ✗ | no |
| `2026_exam2_geometry_point_distance` | 19 | ✗ | ✗ | ✗ | ✓ | ✗ | no |
| `2026_exam2_roots_cubic_dsin` | 19 | ✗ | ✗ | ✓ | ✓ | ✓ | no |

*Latency: avg 41303ms  min 26969ms  max 65359ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated
## Model Override

- requested_model: `qwen2.5-coder:14b`
- effective_model: `qwen2.5-coder:14b`
- proxy_config_model: `qwen2.5-coder:3b`
- model_override_valid: `True`
- benchmark_status: `completed`
