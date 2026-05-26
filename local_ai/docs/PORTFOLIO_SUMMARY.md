# Portfolio Summary

`research-claw-code` is a local-first AI experimentation framework for coding
models. It focuses on offline evaluation, compile/runtime validated benchmarks,
LoRA adapter experiments, regression analysis, and governance around when an
adapter is safe to use.

## Technical Highlights

- Config-driven workflows for models, datasets, benchmarks, runtime profiles,
  and training jobs.
- Deterministic coding benchmark pipeline with compile, runtime, semantic, and
  keyword checks.
- LoRA training and comparison reports with experiment registry tracking.
- Retry repair loop with human-curated golden targets.
- Adapter promotion policy and registry summaries.
- Synthetic dataset scaling pipeline with generated task validation and
  candidate promotion gates.
- Task-specific routing layer that defaults to base and blocks rejected or
  ablation-only adapters.
- System index, report index, architecture map, smoke test, and unified CLI.

## Engineering Lessons

- A local-first system needs strong metadata and report indexing because
  experiments multiply quickly.
- Adapter promotion should be evidence-based and conservative; a successful
  training run is not enough.
- Regression analysis should inspect runtime behavior, not just compile rates.
- Routing by task type is safer than assuming one adapter improves every task.
- Guardrails are more valuable when they are executable as smoke tests.

## Negative Findings

- Synthetic data that passed compile/runtime/semantic validation still caused
  LoRA regression.
- The full `generated_candidate_v1` adapter regressed both strict and generated
  benchmarks.
- The topic-specific `pattern_only_candidate_v1` adapter did not improve the
  target pattern benchmark and still regressed general benchmarks.
- Synthetic generated datasets are useful as isolated stress-test assets, but
  not currently suitable as default LoRA training input.

## Final Positioning

This project is best positioned as local-first AI experimentation
infrastructure: a practical environment for evaluating coding models, mining
failures, testing repair data, governing adapters, and making conservative
routing decisions without depending on cloud execution.
