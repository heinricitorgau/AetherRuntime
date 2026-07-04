# Benchmark Report

**Run ID**: `model_eval_qwen25_coder_14b_generated_c_tasks_v1_20260625_115605`  
**Model**: `qwen2.5-coder:14b`  
**Timestamp**: 2026-06-25T04:31:27+00:00  
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
| Compile pass | 92% | 37/40 |
| Runtime pass (output matches) | 92% | 37/40 |
| Semantic pass (no static errors) | 100% | 40/40 |
| Keyword pass (required constructs) | 100% | 40/40 |
| **Accepted** (score ≥ 60) | 92% | 37/40 |

Average score: **93.8/100**  
Score range: 30–100

## Score Distribution

| Bucket | Count |
|--------|------:|
| 90-100 | 36 |
| 70-89 | 1 |
| 60-69 | 0 |
| 0-59 | 3 |

## By Topic

| Topic | Count | Accepted | Avg Score |
|-------|------:|---------:|----------:|
| game_simulation | 10 | 8 | 82.0 |
| geometry | 10 | 9 | 93.0 |
| pattern_generation | 10 | 10 | 100.0 |
| series_calculation | 10 | 10 | 100.0 |

## By Difficulty

| Difficulty | Count | Accepted | Avg Score |
|------------|------:|---------:|----------:|
| easy | 17 | 14 | 86.5 |
| hard | 13 | 13 | 100.0 |
| medium | 10 | 10 | 98.0 |

## Per-Case Results

| ID | Score | C | R | S | K | T | Accept |
|----|------:|---|---|---|---|---|--------|
| `synthetic_v3_game_simulation_001` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_004` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_005` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_006` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_009` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_001` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_002` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_003` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_004` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_005` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_006` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_007` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_009` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_geometry_010` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_001` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_002` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_003` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_004` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_005` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_006` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_007` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_008` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_009` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_pattern_generation_010` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_001` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_002` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_003` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_004` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_005` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_006` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_007` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_008` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_009` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_series_calculation_010` | 100 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_002` | 90 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_010` | 90 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_008` | 80 | ✓ | ✓ | ✓ | ✓ | ✓ | YES |
| `synthetic_v3_game_simulation_003` | 30 | ✗ | ✗ | ✓ | ✓ | ✓ | no |
| `synthetic_v3_game_simulation_007` | 30 | ✗ | ✗ | ✓ | ✓ | ✓ | no |
| `synthetic_v3_geometry_008` | 30 | ✗ | ✗ | ✓ | ✓ | ✓ | no |

*Latency: avg 52707ms  min 28671ms  max 114655ms*

---

**Legend**: C=compile  R=runtime  S=semantic  K=keyword  T=not-truncated
## Model Override

- requested_model: `qwen2.5-coder:14b`
- effective_model: `qwen2.5-coder:14b`
- proxy_config_model: `qwen2.5-coder:14b`
- model_override_valid: `True`
- benchmark_status: `completed`
