# Experiment Tracking

`local_ai/experiments/` records structured metadata for completed research
runs. The registry is intentionally lightweight: pipeline scripts keep their
existing reports and scoring logic, while the experiment layer stores a compact
index that is easy to list, inspect, and compare.

## Registry Structure

Each registered run is written as one JSON file:

```text
local_ai/experiments/registry/<run_id>.json
```

The registry stores common metadata across workflows:

- `run_id`
- `timestamp`
- `run_type`: `benchmark`, `train`, or `compare_lora`
- `model_profile`
- `benchmark_profile`
- `training_job`
- `adapter_path`
- `accepted`
- `avg_score`
- `compile_rate`
- `runtime_rate`
- `semantic_rate`
- `timeout_rate`
- `git_commit`
- `python_version`
- `cuda_available`
- `gpu_name`
- `linked_reports`
- `config_profiles`

## Automatic Registration

The following scripts register runs after their normal reports are written:

```powershell
python local_ai/benchmark/run_baseline.py --benchmark c_exam_2025_strict_seeded
python local_ai/sft/train_lora.py --job tiny_lora_test
python local_ai/sft/benchmark_lora.py --benchmark c_exam_2025_strict_seeded --adapter local_ai/sft/artifacts/test_lora
```

Registration failures are reported as warnings so they do not change benchmark,
training, or comparison behavior.

## List Runs

Show recent runs:

```powershell
python local_ai/experiments/list_runs.py
```

Filter by type:

```powershell
python local_ai/experiments/list_runs.py --type benchmark --limit 10
python local_ai/experiments/list_runs.py --type train
python local_ai/experiments/list_runs.py --type compare_lora
```

## Show One Run

Inspect full metadata:

```powershell
python local_ai/experiments/show_run.py --run-id strict_20260515_052032
```

The output includes linked report paths and the config profiles used by the
run.

## Compare Runs

Use `list_runs.py` to find candidate run IDs, then inspect the registry JSON
files or follow the linked benchmark reports:

```powershell
python local_ai/experiments/list_runs.py --type benchmark --limit 20
python local_ai/experiments/show_run.py --run-id <run_id>
```

Compare two registered runs without rerunning models:

```powershell
python local_ai/experiments/compare_runs.py --base <old_run_id> --new <new_run_id>
```

The comparison checks:

- `accepted`
- `avg_score`
- `compile_rate`
- `runtime_rate`
- `semantic_rate`
- `keyword_rate`
- `timeout_rate`

All metrics are higher-is-better except `timeout_rate`, where lower is better.
The verdict is:

- `improvement`: at least one metric improved and no metric regressed
- `regression`: at least one metric regressed
- `no_change`: no comparable metric changed

Reports are written to:

```text
local_ai/experiments/reports/compare_<base>_vs_<new>.json
local_ai/experiments/reports/compare_<base>_vs_<new>.md
```

## Leaderboard

Build a sorted view across benchmark and LoRA comparison runs:

```powershell
python local_ai/experiments/leaderboard.py
python local_ai/experiments/leaderboard.py --limit 10 --format markdown
python local_ai/experiments/leaderboard.py --format json
```

Filter by run type or benchmark profile:

```powershell
python local_ai/experiments/leaderboard.py --type benchmark
python local_ai/experiments/leaderboard.py --type compare_lora
python local_ai/experiments/leaderboard.py --benchmark c_exam_2025_strict_seeded
```

Leaderboard reports are written to:

```text
local_ai/experiments/reports/leaderboard.json
local_ai/experiments/reports/leaderboard.md
```

## Identifying The Best Model Or Adapter

Use the leaderboard as the first pass:

```powershell
python local_ai/experiments/leaderboard.py --benchmark c_exam_2025_strict_seeded --limit 10
```

Prefer runs with:

- higher `avg_score`
- higher `accepted`
- high `compile_rate`
- high `runtime_rate`
- low `timeout_rate`

For LoRA adapters, focus on `compare_lora` rows and inspect `adapter_path`.
Then use `show_run.py` to open the metadata and linked reports:

```powershell
python local_ai/experiments/show_run.py --run-id <best_run_id>
```

## Detecting Regression

Use `compare_runs.py` before replacing a golden baseline, model profile, prompt,
or adapter:

```powershell
python local_ai/experiments/compare_runs.py --base <known_good_run_id> --new <candidate_run_id>
```

A regression verdict means at least one tracked metric moved in the wrong
direction. The markdown report lists changed, improved, and regressed fields so
you can decide whether the candidate is safe to promote.

For detailed per-task benchmark comparison, continue to use the benchmark
comparison tools under `local_ai/benchmark/`. The experiment registry is the
index layer; scoring and detailed diff logic stay in the benchmark subsystem.

## Adapter Promotion Governance

LoRA adapters are not promoted directly from a successful training run. They are
classified after a base-vs-adapter benchmark comparison:

```powershell
python local_ai/sft/promote_adapter.py --adapter local_ai/sft/artifacts/<adapter> --comparison local_ai/sft/reports/comparison_report.json
```

The policy records one of four statuses:

- `promote`: positive average score delta, no accepted/compile/runtime/semantic regression, and no per-task drop worse than the guardrail.
- `safe_no_change`: accepted/compile/runtime/semantic guardrails hold and the average score is effectively unchanged. This is safe to keep available, but it is not made default.
- `ablation_only`: useful for analysis, but not eligible for default use because it regresses average score, runtime, or a task-level guardrail.
- `reject`: failed core guardrails such as accepted, compile, semantic, severe runtime collapse, or a very large task drop.

Rejected and ablation adapters are kept because they are research evidence:
they document failure modes, prevent repeated experiments, and make future
adapter routing or ablation analysis reproducible. The governance scripts never
delete adapter artifacts.

List the current adapter registry without opening JSON files:

```powershell
python local_ai/sft/list_adapters.py
python local_ai/sft/list_adapters.py --status safe_no_change
python local_ai/sft/list_adapters.py --format markdown
python local_ai/sft/list_adapters.py --format json
```

The summary reports are written to:

```text
local_ai/sft/reports/adapter_registry_summary.json
local_ai/sft/reports/adapter_registry_summary.md
```
