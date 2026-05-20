# Local AI SFT Infrastructure v1

## Completed Capabilities

- Local offline coding LLM runtime with Ollama and proxy
- Config-driven profiles for models, datasets, benchmarks, runtime, and training jobs
- Config registry validation with structured reports
- Startup doctor for Python, CUDA, compiler, proxy, config, golden baseline, and SFT readiness
- Unified workflow runner via `local_ai/run_profile.py`
- Strict-code-only benchmark with compile, runtime, semantic, keyword, truncation, and timeout signals
- Golden baseline regression detection
- SFT readiness gate and dataset quality reports
- LoRA training, LoRA inference, and LoRA-vs-base benchmark comparison
- Experiment registry with searchable run metadata
- Run comparison and leaderboard reports
- Release snapshot generation

## Benchmark Status

The current golden baseline is `strict_20260515_052032` using
`qwen2.5-coder:3b` in strict-code-only mode.

Current golden metrics:

- Accepted: 4/4
- Average score: 84.2
- Compile pass rate: 100%
- Runtime pass rate: 75%
- Semantic pass rate: 100%
- Keyword pass rate: 100%
- Timeout rate: 0%

## LoRA Status

The project includes config-driven LoRA training jobs and adapter evaluation
scripts. The SFT readiness report currently marks the full readiness gate as
not ready because reproducibility needs attention, while dataset, semantic,
benchmark, and documentation checks are present.

## Config-Driven Workflow

Primary profile files:

- `local_ai/config/models.json`
- `local_ai/config/datasets.json`
- `local_ai/config/benchmarks.json`
- `local_ai/config/training_jobs.json`
- `local_ai/config/runtime_profiles.json`

Common commands:

```powershell
python local_ai/config/validate_profiles.py
python local_ai/doctor.py --benchmark c_exam_2025_strict_seeded
python local_ai/run_profile.py benchmark --benchmark c_exam_2025_strict_seeded --dry-run
python local_ai/run_profile.py train --job tiny_lora_test --dry-run
```

## Experiment Tracking

Experiment metadata is stored in:

```text
local_ai/experiments/registry/
```

Analysis reports are stored in:

```text
local_ai/experiments/reports/
```

Useful commands:

```powershell
python local_ai/experiments/list_runs.py
python local_ai/experiments/leaderboard.py --limit 10 --format markdown
python local_ai/experiments/show_run.py --run-id <run_id>
python local_ai/experiments/compare_runs.py --base <old_run_id> --new <new_run_id>
```

## Limitations

- SFT readiness is not fully PASS due to the reproducibility gate.
- The experiment registry currently needs more benchmark and compare-lora runs
  before the leaderboard becomes a meaningful ranking surface.
- Release snapshots summarize existing reports; they do not rerun benchmark,
  doctor, or training jobs.
- Model quality is still bounded by the local model and prompt profiles
  currently configured.

## Next Milestone

- Resolve SFT reproducibility readiness.
- Register multiple benchmark and compare-lora runs for adapter ranking.
- Add snapshot-to-snapshot diffing.
- Promote stable config profiles into release candidates.
- Expand evaluation coverage without changing core scoring semantics.
