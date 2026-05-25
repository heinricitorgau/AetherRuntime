# Benchmark Report

**Run ID**: `strict_20260523_205251`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-05-23T21:32:57+00:00  
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
| Proxy response (no timeout/error) | 95% | 38/40 |
| Code not truncated | 95% | 38/40 |
| Compile pass | 85% | 34/40 |
| Runtime pass (output matches) | 70% | 28/40 |
| Semantic pass (no static errors) | 95% | 38/40 |
| Keyword pass (required constructs) | 100% | 40/40 |
| **Accepted** (score ≥ 60) | 85% | 34/40 |

Average score: **82.5/100**  
Score range: 15–100

## Score Distribution

| Bucket | Count |
|--------|------:|
| 90-100 | 26 |
| 70-89 | 8 |
| 60-69 | 0 |
| 0-59 | 6 |

## By Topic

| Topic | Count | Accepted | Avg Score |
|-------|------:|---------:|----------:|
| game_simulation | 10 | 8 | 72.0 |
| geometry | 10 | 8 | 80.0 |
| pattern_generation | 10 | 10 | 92.0 |
| series_calculation | 10 | 8 | 86.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| easy | 17 | 16 | 88.8 |
| hard | 13 | 11 | 83.8 |
| medium | 10 | 7 | 70.0 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `synthetic_v3_game_simulation_005` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_008` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_001` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_004` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_005` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_006` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_008` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_009` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_001` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_002` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_003` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_004` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_007` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_008` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_009` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_001` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_002` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_003` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_005` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_006` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_007` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_009` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_010` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_003` | 90 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_004` | 90 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_007` | 90 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_009` | 80 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_005` | 80 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_006` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_010` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_003` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_007` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_006` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_010` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_002` | 30 | ✗ | ✗ | ✓ | ✓ | ✓ | no |
| `synthetic_v3_geometry_010` | 30 | ✗ | ✗ | ✓ | ✓ | ✓ | no |
| `synthetic_v3_series_calculation_004` | 30 | ✗ | ✗ | ✓ | ✓ | ✓ | no |
| `synthetic_v3_series_calculation_008` | 30 | ✗ | ✗ | ✓ | ✓ | ✓ | no |
| `synthetic_v3_game_simulation_001` | 15 | ✗ | ✗ | ✗ | ✓ | ✗ | no |
| `synthetic_v3_game_simulation_002` | 15 | ✗ | ✗ | ✗ | ✓ | ✗ | no |

*Latency: avg 46015ms  min 26311ms  max 204406ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated