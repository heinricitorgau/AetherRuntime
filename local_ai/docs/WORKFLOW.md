# Workflow Runner

`local_ai/run_profile.py` is the single entry point for common profile-driven
workflows. It does not contain benchmark, training, doctor, or scoring logic.
It prints the command it is about to run, delegates to the existing script, and
returns the same exit code.

## Common Startup Flow

Start each development session with the doctor for the benchmark or training
profile you plan to use:

```powershell
python local_ai/run_profile.py doctor --benchmark c_exam_2025_strict_seeded
```

If the doctor reports `FAIL`, fix those items before running long benchmark or
training jobs. `WARN` items are visible risk notes and do not block the wrapper.

## Doctor

Run environment checks through the unified entry point:

```powershell
python local_ai/run_profile.py doctor --benchmark c_exam_2025_strict_seeded
python local_ai/run_profile.py doctor --profile qwen3b_local
python local_ai/run_profile.py doctor --training-job tiny_lora_test
```

These are delegated to `local_ai/doctor.py`.

## Benchmark

Run a configured benchmark profile:

```powershell
python local_ai/run_profile.py benchmark --benchmark c_exam_2025_strict_seeded
```

Preview the delegated command without running it:

```powershell
python local_ai/run_profile.py benchmark --benchmark c_exam_2025_strict_seeded --dry-run
```

This delegates to `local_ai/benchmark/run_baseline.py`.

## Train

Run a configured LoRA training job:

```powershell
python local_ai/run_profile.py train --job tiny_lora_test
```

Preview the training command without executing it:

```powershell
python local_ai/run_profile.py train --job tiny_lora_test --dry-run
```

The wrapper dry-run is intentionally handled in `run_profile.py`: every
subcommand prints the delegated command and exits without calling the underlying
script.

## Compare LoRA

Compare a LoRA adapter against the configured benchmark:

```powershell
python local_ai/run_profile.py compare-lora --benchmark c_exam_2025_strict_seeded --adapter local_ai/sft/artifacts/test_lora
```

This delegates to `local_ai/sft/benchmark_lora.py`.

## Golden Baseline Workflow

Use wrapper dry-run first to confirm which command will run:

```powershell
python local_ai/run_profile.py benchmark --benchmark c_exam_2025_strict_seeded --dry-run
```

To list benchmark tasks without model calls, use the benchmark script dry-run:

```powershell
python local_ai/benchmark/run_baseline.py --benchmark c_exam_2025_strict_seeded --dry-run
```

Then run the benchmark:

```powershell
python local_ai/run_profile.py benchmark --benchmark c_exam_2025_strict_seeded
```

The benchmark script keeps ownership of scoring, report generation, accepted
counts, and golden baseline regression detection.

## Config-Driven Workflow

Use config files to change models, datasets, benchmarks, and training jobs:

- `local_ai/config/models.json`
- `local_ai/config/datasets.json`
- `local_ai/config/benchmarks.json`
- `local_ai/config/training_jobs.json`
- `local_ai/config/runtime_profiles.json`

After editing profiles, validate the registry:

```powershell
python local_ai/config/validate_profiles.py
python local_ai/shared/config_loader.py --self-test
```

Then run the workflow through `run_profile.py`. The wrapper should stay thin:
new business behavior belongs in the underlying script or config layer, not in
the orchestration entry point.
