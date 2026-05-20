# Local AI Doctor Report

Generated: `2026-05-20T19:30:25+00:00`
Status: **PASS**

## Summary

| PASS | WARN | FAIL |
|-----:|-----:|-----:|
| 18 | 0 | 0 |

## Checks

| Status | Check | Detail | Fix |
|:------:|-------|--------|-----|
| PASS | `python_version` | 3.12.10 (C:\Users\User\OneDrive\Desktop\research-claw-code\.venv-sft\Scripts\python.exe) |  |
| PASS | `import_torch` | torch import available |  |
| PASS | `cuda_available` | CUDA available |  |
| PASS | `gpu` | NVIDIA GeForce RTX 4060 Laptop GPU (8.0 GB VRAM) |  |
| PASS | `import_transformers` | transformers import available |  |
| PASS | `import_peft` | peft import available |  |
| PASS | `unwanted_datasets` | datasets not installed |  |
| PASS | `unwanted_pyarrow` | pyarrow not installed |  |
| PASS | `c_compiler` | C:\msys64\ucrt64\bin\cc.EXE |  |
| PASS | `ollama_binary` | C:\Users\User\OneDrive\Desktop\research-claw-code\local_ai\runtime\bin\ollama.exe |  |
| PASS | `proxy_health` | http://127.0.0.1:8082/health ok |  |
| PASS | `proxy_config` | full_timeout=300s first_token_timeout=90s |  |
| PASS | `proxy_timeout` | benchmark timeout ok: full=300s first_token=90s |  |
| PASS | `config_registry` | profile registry valid (0 issues) |  |
| PASS | `golden_baseline` | C:\Users\User\OneDrive\Desktop\research-claw-code\local_ai\benchmark\golden\golden_baseline.json ref=strict_20260515_052032 tasks=4 |  |
| PASS | `benchmark_profile` | c_exam_2025_strict_seeded: model=qwen3b_local dataset=c_exam_test_2025 |  |
| PASS | `dataset_path:c_exam_test_2025` | C:\Users\User\OneDrive\Desktop\research-claw-code\local_ai\ingest\output\training\splits\test_code_generation.jsonl |  |
| PASS | `sft_readiness` | SFT readiness: PASS \| READY_FOR_SFT = true \|  \| Report: C:\Users\User\OneDrive\Desktop\research-claw-code\local_ai\training_quality\reports\sft_readiness_report.md |  |
