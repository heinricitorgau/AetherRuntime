# Model Replacement Benchmark

Generated: `2026-06-25T04:31:37+00:00`
Baseline: `qwen25_coder_3b`

## Execution Strategy

Models are not pre-filtered by `compare_models.py`. The script directly calls `run_baseline.py --model-override ...` and records benchmark subprocess failures as `benchmark_failed` without stopping the full comparison.

Before each benchmark subprocess, the script checks proxy `/health` and `/config` with retry. If the proxy preflight fails, that benchmark is recorded as `proxy_unavailable` and the subprocess is not started.

| Model | Ollama Model | Strategy |
|-------|--------------|----------|
| Qwen2.5-Coder-3B-Instruct | qwen2.5-coder:3b | direct benchmark run |
| Qwen2.5-Coder-14B-Instruct | qwen2.5-coder:14b | direct benchmark run |

## Aggregate Comparison

| Model | Status | Tasks | Accepted | Avg Score | Compile | Runtime | Semantic | vs Baseline Avg |
|-------|--------|------:|---------:|----------:|--------:|--------:|---------:|----------------:|
| Qwen2.5-Coder-3B-Instruct | completed | 44 | 37 | 79.75 | 84.1% | 63.6% | 100.0% | 0.00 |
| Qwen2.5-Coder-14B-Instruct | completed | 44 | 40 | 91.32 | 90.9% | 88.6% | 100.0% | 11.57 |

## Per-Benchmark Results

| Model | Benchmark | Status | Tasks | Accepted | Avg Score | Compile | Runtime | Semantic | Requested Model | Effective Model | Override Valid | Proxy OK | Proxy Model | Proxy Full Timeout | Proxy First Token Timeout | Error | Proxy Error |
|-------|-----------|--------|------:|---------:|----------:|--------:|--------:|---------:|-----------------|-----------------|---------------:|---------:|-------------|-------------------:|--------------------------:|-------|-------------|
| Qwen2.5-Coder-3B-Instruct | c_exam_2025_strict_seeded | completed | 4 | 4 | 83.20 | 100.0% | 75.0% | 100.0% | qwen2.5-coder:3b | qwen2.5-coder:3b | True | True | qwen2.5-coder:14b | 660 | 180 |  |  |
| Qwen2.5-Coder-3B-Instruct | generated_c_tasks_v1 | completed | 40 | 33 | 79.40 | 82.5% | 62.5% | 100.0% | qwen2.5-coder:3b | qwen2.5-coder:3b | True | True | qwen2.5-coder:14b | 660 | 180 |  |  |
| Qwen2.5-Coder-14B-Instruct | c_exam_2025_strict_seeded | completed | 4 | 3 | 66.50 | 75.0% | 50.0% | 100.0% | qwen2.5-coder:14b | qwen2.5-coder:14b | True | True | qwen2.5-coder:14b | 660 | 180 |  |  |
| Qwen2.5-Coder-14B-Instruct | generated_c_tasks_v1 | completed | 40 | 37 | 93.80 | 92.5% | 92.5% | 100.0% | qwen2.5-coder:14b | qwen2.5-coder:14b | True | True | qwen2.5-coder:14b | 660 | 180 |  |  |

## Questions

- Q1: 14B vs 3B: avg score delta +11.57, accepted delta +3, runtime delta +0.250.
- Q2: 30B vs 14B: insufficient completed benchmark data.
- Q3: Model capability is the primary bottleneck: a larger model improves aggregate score without reducing runtime correctness.
- Q4: Not yet.

## Recommendation

**stay on 3B**

No larger model completed all guarded benchmarks with a material, regression-free gain.

## Guardrails

- Benchmark evaluation only; no LoRA training.
- Benchmark scoring unchanged.
- Routing policy unchanged.
- No adapter or synthetic dataset promotion.
