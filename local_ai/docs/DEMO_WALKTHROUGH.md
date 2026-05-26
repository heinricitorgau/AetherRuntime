# Demo Walkthrough

This walkthrough shows the stable V1-V7 portfolio path without running models
or training adapters.

## 1. Run The Smoke Test

```bash
python local_ai/cli.py smoke
```

This validates config profiles, system reports, adapter registry summaries, and
routing dry-run behavior. It does not call the proxy, run a model, train LoRA,
or require CUDA/torch.

## 2. View The System Index

```bash
python local_ai/cli.py system
```

Open:

- `local_ai/system/reports/system_index.md`
- `local_ai/system/reports/report_index.md`
- `local_ai/system/reports/architecture_map.md`

These reports summarize config status, experiment count, adapter state,
snapshots, routing reports, and module responsibilities.

## 3. View The Adapter Registry

```bash
python local_ai/cli.py adapters
```

Open:

- `local_ai/sft/reports/adapter_registry_summary.md`

Current expected state:

- No default adapter selected.
- `retry_geometry_v3_guarded` is retained as `safe_no_change`.
- Rejected synthetic adapters are not eligible for routing.

## 4. View A Routing Plan

```bash
python local_ai/cli.py routing --benchmark c_exam_2025_strict_seeded
python local_ai/cli.py routing --benchmark generated_c_tasks_v1
```

Open:

- `local_ai/routing/reports/c_exam_2025_strict_seeded_routing_plan.md`
- `local_ai/routing/reports/generated_c_tasks_v1_routing_plan.md`

The routing layer defaults to the base model and only considers approved
adapter statuses. `retry_geometry_v3_guarded` is considered only for geometry
tasks.

## 5. View The Release Snapshot

Latest snapshot:

- `local_ai/release/snapshots/local_ai_cli_v7/snapshot.md`

To create a new snapshot:

```bash
python local_ai/cli.py snapshot --name local_ai_cli_v7
```

## What V1-V7 Achieved

- **V1**: Local AI SFT infrastructure, benchmark profiles, LoRA train/eval flow.
- **V2**: Retry loop, golden repairs, adapter governance, safe adapter registry.
- **V3**: Dataset scaling, generated corpus validation, synthetic training freeze.
- **V4**: Task-specific adapter routing and routing reports.
- **V5**: System index, report index, and architecture map.
- **V6**: Fast smoke validation for pre-commit checks.
- **V7**: Unified CLI for common developer workflows.
