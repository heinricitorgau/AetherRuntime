# Routing Plan

Generated: `2026-05-26T11:24:22+00:00`
Benchmark: `generated_c_tasks_v1`
Total tasks: 40

## Summary

- Benchmark: `generated_c_tasks_v1`
- Total tasks: 40
- Selected base count: 30
- Selected adapter count: 10
- Selected by topic: `{'game_simulation': {'base': 10}, 'geometry': {'adapter': 10}, 'pattern_generation': {'base': 10}, 'series_calculation': {'base': 10}}`
- Selected by adapter: `{'base': 30, 'retry_geometry_v3_guarded': 10}`
- Topic counts: `{'game_simulation': 10, 'geometry': 10, 'pattern_generation': 10, 'series_calculation': 10}`
- Rejected adapter count: 0
- Ablation adapter count: 0
- Safe adapter count: 1
- Promoted adapter count: 0

## Decisions

| Task ID | Topic | Selected | Model Path | Adapter Status | Fallback Reason |
|---------|-------|----------|------------|----------------|-----------------|
| synthetic_v3_game_simulation_001 | game_simulation | base | base |  | policy uses base |
| synthetic_v3_game_simulation_002 | game_simulation | base | base |  | policy uses base |
| synthetic_v3_game_simulation_003 | game_simulation | base | base |  | policy uses base |
| synthetic_v3_game_simulation_004 | game_simulation | base | base |  | policy uses base |
| synthetic_v3_game_simulation_005 | game_simulation | base | base |  | policy uses base |
| synthetic_v3_game_simulation_006 | game_simulation | base | base |  | policy uses base |
| synthetic_v3_game_simulation_007 | game_simulation | base | base |  | policy uses base |
| synthetic_v3_game_simulation_008 | game_simulation | base | base |  | policy uses base |
| synthetic_v3_game_simulation_009 | game_simulation | base | base |  | policy uses base |
| synthetic_v3_game_simulation_010 | game_simulation | base | base |  | policy uses base |
| synthetic_v3_geometry_001 | geometry | adapter | local_ai/sft/artifacts/retry_geometry_v3_guarded | safe_no_change |  |
| synthetic_v3_geometry_002 | geometry | adapter | local_ai/sft/artifacts/retry_geometry_v3_guarded | safe_no_change |  |
| synthetic_v3_geometry_003 | geometry | adapter | local_ai/sft/artifacts/retry_geometry_v3_guarded | safe_no_change |  |
| synthetic_v3_geometry_004 | geometry | adapter | local_ai/sft/artifacts/retry_geometry_v3_guarded | safe_no_change |  |
| synthetic_v3_geometry_005 | geometry | adapter | local_ai/sft/artifacts/retry_geometry_v3_guarded | safe_no_change |  |
| synthetic_v3_geometry_006 | geometry | adapter | local_ai/sft/artifacts/retry_geometry_v3_guarded | safe_no_change |  |
| synthetic_v3_geometry_007 | geometry | adapter | local_ai/sft/artifacts/retry_geometry_v3_guarded | safe_no_change |  |
| synthetic_v3_geometry_008 | geometry | adapter | local_ai/sft/artifacts/retry_geometry_v3_guarded | safe_no_change |  |
| synthetic_v3_geometry_009 | geometry | adapter | local_ai/sft/artifacts/retry_geometry_v3_guarded | safe_no_change |  |
| synthetic_v3_geometry_010 | geometry | adapter | local_ai/sft/artifacts/retry_geometry_v3_guarded | safe_no_change |  |
| synthetic_v3_pattern_generation_001 | pattern_generation | base | base |  | policy uses base |
| synthetic_v3_pattern_generation_002 | pattern_generation | base | base |  | policy uses base |
| synthetic_v3_pattern_generation_003 | pattern_generation | base | base |  | policy uses base |
| synthetic_v3_pattern_generation_004 | pattern_generation | base | base |  | policy uses base |
| synthetic_v3_pattern_generation_005 | pattern_generation | base | base |  | policy uses base |
| synthetic_v3_pattern_generation_006 | pattern_generation | base | base |  | policy uses base |
| synthetic_v3_pattern_generation_007 | pattern_generation | base | base |  | policy uses base |
| synthetic_v3_pattern_generation_008 | pattern_generation | base | base |  | policy uses base |
| synthetic_v3_pattern_generation_009 | pattern_generation | base | base |  | policy uses base |
| synthetic_v3_pattern_generation_010 | pattern_generation | base | base |  | policy uses base |
| synthetic_v3_series_calculation_001 | series_calculation | base | base |  | policy uses base |
| synthetic_v3_series_calculation_002 | series_calculation | base | base |  | policy uses base |
| synthetic_v3_series_calculation_003 | series_calculation | base | base |  | policy uses base |
| synthetic_v3_series_calculation_004 | series_calculation | base | base |  | policy uses base |
| synthetic_v3_series_calculation_005 | series_calculation | base | base |  | policy uses base |
| synthetic_v3_series_calculation_006 | series_calculation | base | base |  | policy uses base |
| synthetic_v3_series_calculation_007 | series_calculation | base | base |  | policy uses base |
| synthetic_v3_series_calculation_008 | series_calculation | base | base |  | policy uses base |
| synthetic_v3_series_calculation_009 | series_calculation | base | base |  | policy uses base |
| synthetic_v3_series_calculation_010 | series_calculation | base | base |  | policy uses base |
