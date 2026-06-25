# Routing Plan

Generated: `2026-06-22T04:22:41+00:00`
Benchmark: `c_exam_2025_strict_seeded`
Total tasks: 4

## Summary

- Benchmark: `c_exam_2025_strict_seeded`
- Total tasks: 4
- Selected base count: 3
- Selected adapter count: 1
- Selected by topic: `{'game_simulation': {'base': 1}, 'geometry': {'adapter': 1}, 'pattern_generation': {'base': 1}, 'series_calculation': {'base': 1}}`
- Selected by adapter: `{'base': 3, 'retry_geometry_v3_guarded': 1}`
- Topic counts: `{'game_simulation': 1, 'geometry': 1, 'pattern_generation': 1, 'series_calculation': 1}`
- Rejected adapter count: 0
- Ablation adapter count: 0
- Safe adapter count: 1
- Promoted adapter count: 0

## Decisions

| Task ID | Topic | Selected | Model Path | Adapter Status | Fallback Reason |
|---------|-------|----------|------------|----------------|-----------------|
| 2025_midterm_001 | series_calculation | base | base |  | policy uses base |
| 2025_midterm_002 | pattern_generation | base | base |  | policy uses base |
| 2025_midterm_003 | geometry | adapter | local_ai/sft/artifacts/retry_geometry_v3_guarded | safe_no_change |  |
| 2025_midterm_004 | game_simulation | base | base |  | policy uses base |
