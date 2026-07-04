# Benchmark Report

**Run ID**: `model_eval_qwen25_coder_3b_generated_c_tasks_v1_20260625_113845`  
**Model**: `qwen2.5-coder:3b`  
**Timestamp**: 2026-06-25T03:49:57+00:00  
**Prompt file**: `You are a competitive programming code generator.

Rules:
* `  
**Mode**: strict_code_only (v2)  
**max_tokens**: 512  
**temperature**: 0.1
**proxy full timeout**: 660  
**proxy first-token timeout**: 180

---

## Pass Rates

| Dimension | Rate | Count |
|-----------|-----:|------:|
| Proxy response (no timeout/error) | 100% | 40/40 |
| Code not truncated | 100% | 40/40 |
| Compile pass | 82% | 33/40 |
| Runtime pass (output matches) | 62% | 25/40 |
| Semantic pass (no static errors) | 100% | 40/40 |
| Keyword pass (required constructs) | 100% | 40/40 |
| **Accepted** (score ≥ 60) | 82% | 33/40 |

Average score: **79.4/100**  
Score range: 30–100

## Score Distribution

| Bucket | Count |
|--------|------:|
| 90-100 | 21 |
| 70-89 | 12 |
| 60-69 | 0 |
| 0-59 | 7 |

## By Topic

| Topic | Count | Accepted | Avg Score |
|-------|------:|---------:|----------:|
| game_simulation | 10 | 6 | 58.0 |
| geometry | 10 | 9 | 85.5 |
| pattern_generation | 10 | 10 | 88.0 |
| series_calculation | 10 | 8 | 86.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| easy | 17 | 14 | 81.8 |
| hard | 13 | 11 | 79.6 |
| medium | 10 | 8 | 75.0 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `synthetic_v3_geometry_001` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_004` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_005` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_008` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_009` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_010` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_001` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_002` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_004` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_007` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_008` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_001` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_002` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_003` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_005` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_006` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_007` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_009` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_010` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_003` | 90 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_008` | 90 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_006` | 85 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_003` | 80 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_005` | 80 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_009` | 80 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_002` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_004` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_006` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_010` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_003` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_007` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_006` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_010` | 70 | ✓ | ✗ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_001` | 30 | ✗ | ✗ | ✓ | ✓ | ✓ | no |
| `synthetic_v3_game_simulation_005` | 30 | ✗ | ✗ | ✓ | ✓ | ✓ | no |
| `synthetic_v3_game_simulation_007` | 30 | ✗ | ✗ | ✓ | ✓ | ✓ | no |
| `synthetic_v3_game_simulation_009` | 30 | ✗ | ✗ | ✓ | ✓ | ✓ | no |
| `synthetic_v3_geometry_002` | 30 | ✗ | ✗ | ✓ | ✓ | ✓ | no |
| `synthetic_v3_series_calculation_004` | 30 | ✗ | ✗ | ✓ | ✓ | ✓ | no |
| `synthetic_v3_series_calculation_008` | 30 | ✗ | ✗ | ✓ | ✓ | ✓ | no |

*Latency: avg 15656ms  min 8812ms  max 28156ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated
## Model Override

- requested_model: `qwen2.5-coder:3b`
- effective_model: `qwen2.5-coder:3b`
- proxy_config_model: `qwen2.5-coder:14b`
- model_override_valid: `True`
- benchmark_status: `completed`
