# local_ai_cli_v7

Generated: 2026-05-26T11:49:47+00:00  
Git commit: d1ca455  
Python: 3.12.10  
CUDA: True  
GPU: NVIDIA GeForce RTX 4060 Laptop GPU

## What This Release Contains

- Config-driven model, dataset, benchmark, runtime, and training profiles
- Profile validation and startup doctor
- Offline benchmark and golden baseline workflow
- SFT readiness gate
- LoRA training, inference, and base-vs-LoRA comparison
- Experiment registry, run comparison, and leaderboard
- Failure mining, retry dataset generation, and golden repair targets
- Guarded LoRA retry experiments and adapter promotion governance
- Adapter registry summary for safe, ablation, rejected, and default adapters

## Verified Capabilities

- Config validation: PASS
- Doctor status: PASS
- Experiment registry entries: 95

## Current Best Benchmark

- Golden baseline run: strict_20260515_052032
- Golden run registered: True
- Golden accepted: 4
- Golden average score: 84.2
- Leaderboard top run: strict_20260514_232044
- Leaderboard top avg score: 100.0

## SFT / LoRA Status

- READY_FOR_SFT: True
- Reproducibility: PASS
- SFT summary: {"ready_for_sft": true, "timestamp": "2026-05-20T19:30:25+00:00", "dataset_passed": true, "semantic_passed": true, "benchmark_passed": true, "reproducibility_passed": true, "documentation_passed": true}

## How To Reproduce

```powershell
python local_ai/config/validate_profiles.py
python local_ai/doctor.py --benchmark c_exam_2025_strict_seeded
python local_ai/run_profile.py benchmark --benchmark c_exam_2025_strict_seeded --dry-run
python local_ai/experiments/leaderboard.py --limit 10 --format markdown
python local_ai/release/snapshot.py --name local_ai_cli_v7
```

## Known Limitations

- No missing reports detected in this snapshot.

## Next Recommended Work

- Resolve SFT reproducibility readiness warning
- Register more benchmark and compare-lora runs for meaningful leaderboard ranking
- Promote stable benchmark profiles into golden release candidates
- Scale trusted retry datasets
- Add task-specific adapter routing for guarded adapters
- Add release snapshot diffing once multiple snapshots exist
