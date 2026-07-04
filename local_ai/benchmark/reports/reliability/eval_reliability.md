# Evaluation Reliability Report

Generated: `2026-06-25T06:04:35+00:00`  
Verdict: **flaky**  
Total runs: 85  
Stamp rate: 0.141  
Determinism groups checked: 4

## Flaky Tasks (score spread within identical config)

| Task | Model | Profile | Range | Runs |
|------|-------|---------|------:|-----:|
| `2025_midterm_002` | qwen2.5-coder:3b | None | 77.0 | 3 |
| `2022_exam2_002` | qwen2.5-coder:3b | strict_code_only | 15.0 | 65 |
| `2023_exam2_002` | qwen2.5-coder:3b | strict_code_only | 15.0 | 65 |
| `2025_midterm_001` | qwen2.5-coder:3b | strict_code_only | 70.0 | 65 |
| `2025_midterm_002` | qwen2.5-coder:3b | strict_code_only | 77.0 | 65 |
| `2025_midterm_003` | qwen2.5-coder:3b | strict_code_only | 100.0 | 65 |
| `2025_midterm_004` | qwen2.5-coder:3b | strict_code_only | 97.0 | 65 |
| `synthetic_v3_game_simulation_001` | qwen2.5-coder:3b | strict_code_only | 85.0 | 65 |
| `synthetic_v3_game_simulation_002` | qwen2.5-coder:3b | strict_code_only | 75.0 | 65 |
| `synthetic_v3_game_simulation_003` | qwen2.5-coder:3b | strict_code_only | 70.0 | 65 |
| `synthetic_v3_game_simulation_004` | qwen2.5-coder:3b | strict_code_only | 30.0 | 65 |
| `synthetic_v3_game_simulation_005` | qwen2.5-coder:3b | strict_code_only | 70.0 | 65 |
| `synthetic_v3_game_simulation_006` | qwen2.5-coder:3b | strict_code_only | 20.0 | 65 |
| `synthetic_v3_game_simulation_007` | qwen2.5-coder:3b | strict_code_only | 60.0 | 65 |
| `synthetic_v3_game_simulation_008` | qwen2.5-coder:3b | strict_code_only | 30.0 | 65 |
| `synthetic_v3_game_simulation_009` | qwen2.5-coder:3b | strict_code_only | 70.0 | 65 |
| `synthetic_v3_game_simulation_010` | qwen2.5-coder:3b | strict_code_only | 30.0 | 65 |
| `synthetic_v3_geometry_002` | qwen2.5-coder:3b | strict_code_only | 70.0 | 65 |
| `synthetic_v3_geometry_003` | qwen2.5-coder:3b | strict_code_only | 30.0 | 65 |
| `synthetic_v3_geometry_006` | qwen2.5-coder:3b | strict_code_only | 15.0 | 65 |
| `synthetic_v3_geometry_007` | qwen2.5-coder:3b | strict_code_only | 30.0 | 65 |
| `synthetic_v3_geometry_010` | qwen2.5-coder:3b | strict_code_only | 70.0 | 65 |
| `synthetic_v3_pattern_generation_001` | qwen2.5-coder:3b | strict_code_only | 20.0 | 65 |
| `synthetic_v3_pattern_generation_002` | qwen2.5-coder:3b | strict_code_only | 30.0 | 65 |
| `synthetic_v3_pattern_generation_003` | qwen2.5-coder:3b | strict_code_only | 20.0 | 65 |
| `synthetic_v3_pattern_generation_005` | qwen2.5-coder:3b | strict_code_only | 20.0 | 65 |
| `synthetic_v3_pattern_generation_006` | qwen2.5-coder:3b | strict_code_only | 30.0 | 65 |
| `synthetic_v3_pattern_generation_009` | qwen2.5-coder:3b | strict_code_only | 20.0 | 65 |
| `synthetic_v3_pattern_generation_010` | qwen2.5-coder:3b | strict_code_only | 30.0 | 65 |
| `synthetic_v3_series_calculation_004` | qwen2.5-coder:3b | strict_code_only | 70.0 | 65 |
| `synthetic_v3_series_calculation_008` | qwen2.5-coder:3b | strict_code_only | 70.0 | 65 |
| `2024_exam2_001` | qwen2.5-coder:3b | strict_code_only | 70.0 | 65 |
| `synthetic_v3_game_simulation_006` | qwen2.5-coder:14b | strict_code_only | 10.0 | 11 |
| `synthetic_v3_game_simulation_008` | qwen2.5-coder:14b | strict_code_only | 20.0 | 11 |
| `synthetic_v3_geometry_008` | qwen2.5-coder:14b | strict_code_only | 70.0 | 11 |

## Reproducibility Stamp Audit

- Unstamped runs: 73
- Non-deterministic runs (temperature != 0): 80
- Invalid model override: 0

## Guardrails

- Read-only over existing run reports; runs no models, changes no scoring.
- Verdict derived from the reliability policy; nothing hard-coded.
