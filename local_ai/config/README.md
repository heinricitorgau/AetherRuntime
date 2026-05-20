# config

Configuration profiles for model, dataset, benchmark, training-job, and runtime
selection.

The goal is to switch research targets by editing JSON profiles instead of
changing Python code. CLI entry points stay backward compatible while gradually
adopting these profiles.

## How to add a new training dataset

Add a profile to `datasets.json` with a stable name, `path`, `format`, and
`type: "sft"`. Reference that dataset name from a job in `training_jobs.json`.

## How to add a new benchmark dataset

Add a profile to `datasets.json` with `type: "benchmark"`, then reference it
from `benchmarks.json`. Existing JSONL task files can stay where they are.

## How to add a new model

Add a profile to `models.json` with both HuggingFace and Ollama identifiers plus
generation defaults and LoRA target modules.

## How to add a new runtime profile

Add a profile to `runtime_profiles.json` with `ollama_timeout_seconds` and
`first_token_timeout_seconds`. Optional `proxy_port` and `ollama_port` values
can be included for launchers that adopt runtime profiles later.

## How to validate config profiles

```powershell
python local_ai/shared/config_loader.py --self-test
```

## How to run a configured training job

```powershell
python local_ai/sft/train_lora.py --job tiny_lora_test
```

## How to run a configured benchmark

```powershell
python local_ai/benchmark/run_baseline.py --benchmark c_exam2_all_strict_seeded
python local_ai/sft/benchmark_lora.py --benchmark c_exam2_all_strict_seeded --adapter local_ai/sft/artifacts/test_lora
```

`c_exam2_all_strict_seeded` uses all 16 exam-II benchmark cases from 2021-2024.
