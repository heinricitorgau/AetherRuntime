# Architecture Map

Generated: `2026-07-07T04:43:30+00:00`

## Module Tree

```text
local_ai/
  config/            profile-driven datasets, models, benchmarks, jobs
  benchmark/         task loading, prompting, compile/runtime scoring
  sft/               LoRA training, benchmark comparison, adapter governance
  retry/             failure mining and retry repair datasets
  routing/           task classification and adapter routing plans
  release/           milestone snapshots
  experiments/       run registry and leaderboard
  dataset_scaling/   generated tasks, validation, synthetic evaluation assets
  system/            infrastructure indexes and architecture reports
```

## Responsibilities

- **config**: Defines model, dataset, benchmark, runtime, and training job profiles.
- **benchmark**: Loads tasks and validates outputs through structure, compile, runtime, semantic, and keyword checks.
- **sft**: Trains LoRA adapters, compares adapters to base, analyzes regressions, and governs adapter promotion.
- **retry**: Builds curated retry datasets and guarded repair rounds.
- **routing**: Selects base or approved adapters by task topic and adapter status.
- **release**: Captures snapshot artifacts for project milestones.
- **experiments**: Registers runs and exposes leaderboard/report surfaces.
- **dataset scaling**: Generates and validates synthetic tasks, kept as isolated evaluation assets after V3.

## Data Flow

```text
config profiles
  -> benchmark task loading
  -> base / adapter evaluation
  -> experiment registry and reports
  -> adapter governance
  -> routing policy uses approved adapter statuses

dataset_scaling
  -> generated benchmark assets
  -> synthetic training experiments
  -> frozen synthetic LoRA route
  -> retained stress-test benchmarks

retry goldens
  -> guarded retry datasets
  -> LoRA experiments
  -> adapter promotion policy
  -> safe_no_change adapter available to routing
```

## Guardrails

- Rejected adapters must not be routed.
- Ablation adapters are retained for analysis only.
- No default adapter is selected unless promotion policy explicitly allows it.
- Synthetic generated datasets remain isolated and are not merged into the formal SFT corpus.
- Routing evaluation produces plans only; it does not run models or change scoring.
- Benchmark scoring is not modified by training, routing, or governance scripts.

## Frozen Routes

- `generated_candidate_v1`: rejected.
- `pattern_only_candidate_v1`: rejected.
- Synthetic LoRA training route: frozen for now.

## Approved Paths

- Use the base model by default.
- Use `retry_geometry_v3_guarded` only for geometry tasks when its status remains `safe_no_change` or better.
- Use generated benchmarks for stress testing and evaluation, not as default training input.
- Expand real exam-style verified data and human-curated goldens before further LoRA training.
