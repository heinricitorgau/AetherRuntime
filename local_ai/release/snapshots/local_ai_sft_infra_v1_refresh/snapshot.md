# local_ai_sft_infra_v1_refresh

Generated: 2026-05-20T19:15:53+00:00  
Git commit: 90283aa  
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

## Verified Capabilities

- Config validation: PASS
- Doctor status: WARN
- Experiment registry entries: 1

## Current Best Benchmark

- Golden baseline run: strict_20260515_052032
- Golden accepted: 4
- Golden average score: 84.2
- Leaderboard top run: geometry_toolkit_probe_v1
- Leaderboard top avg score: 0.0

## SFT / LoRA Status

- READY_FOR_SFT: False
- SFT summary: {"ready_for_sft": false, "timestamp": "2026-05-20T19:15:31+00:00", "dataset_passed": true, "semantic_passed": true, "benchmark_passed": true, "reproducibility_passed": false, "documentation_passed": true}

## How To Reproduce

```powershell
python local_ai/config/validate_profiles.py
python local_ai/doctor.py --benchmark c_exam_2025_strict_seeded
python local_ai/run_profile.py benchmark --benchmark c_exam_2025_strict_seeded --dry-run
python local_ai/experiments/leaderboard.py --limit 10 --format markdown
python local_ai/release/snapshot.py --name local_ai_sft_infra_v1
```

## Known Limitations

- Doctor status is WARN.
- SFT readiness is not currently PASS; check reproducibility gate.

## Next Recommended Work

- Resolve SFT reproducibility readiness warning
- Register more benchmark and compare-lora runs for meaningful leaderboard ranking
- Promote stable benchmark profiles into golden release candidates
- Add release snapshot diffing once multiple snapshots exist
