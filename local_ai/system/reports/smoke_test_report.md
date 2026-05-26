# Smoke Test Report

Generated: `2026-05-26T12:42:02+00:00`
Status: **PASS**
Passed: 10
Failed: 0

## Steps

| Step | Status | Detail |
|------|--------|--------|
| config validation | PASS | `C:\Users\User\OneDrive\Desktop\research-claw-code\.venv-sft\Scripts\python.exe local_ai/config/validate_profiles.py` |
| config loader self-test | PASS | `C:\Users\User\OneDrive\Desktop\research-claw-code\.venv-sft\Scripts\python.exe local_ai/shared/config_loader.py --self-test` |
| system index | PASS | `C:\Users\User\OneDrive\Desktop\research-claw-code\.venv-sft\Scripts\python.exe local_ai/system/system_index.py` |
| report index | PASS | `C:\Users\User\OneDrive\Desktop\research-claw-code\.venv-sft\Scripts\python.exe local_ai/system/build_report_index.py` |
| architecture map | PASS | `C:\Users\User\OneDrive\Desktop\research-claw-code\.venv-sft\Scripts\python.exe local_ai/system/build_architecture_map.py` |
| adapter registry summary | PASS | `C:\Users\User\OneDrive\Desktop\research-claw-code\.venv-sft\Scripts\python.exe local_ai/sft/list_adapters.py` |
| routing classifier self-test | PASS | `C:\Users\User\OneDrive\Desktop\research-claw-code\.venv-sft\Scripts\python.exe local_ai/routing/task_classifier.py --self-test` |
| routing plan dry evaluation | PASS | `C:\Users\User\OneDrive\Desktop\research-claw-code\.venv-sft\Scripts\python.exe local_ai/routing/evaluate_routing.py --benchmark c_exam_2025_strict_seeded` |
| generated dataset promotion report exists | PASS | `C:\Users\User\OneDrive\Desktop\research-claw-code\local_ai\dataset_scaling\reports\generated_dataset_promotion_report.json` |
| synthetic training summary exists | PASS | `C:\Users\User\OneDrive\Desktop\research-claw-code\local_ai\sft\reports\synthetic_training_summary.json` |

## Guardrails

- runs_models: False
- trains_adapters: False
- calls_proxy: False
- requires_cuda_or_torch: False
- modifies_benchmark_scoring: False
- promotes_adapters: False
