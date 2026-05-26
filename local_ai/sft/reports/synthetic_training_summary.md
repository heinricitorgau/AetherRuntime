# Synthetic Training Summary

Generated: `2026-05-26T11:03:18+00:00`
Status: **synthetic_training_route_frozen**

## Corpus And Benchmark

- Generated corpus records: 40
- Generated benchmark run: `strict_20260523_205251`
- Generated benchmark accepted: 34/40
- Generated benchmark avg score: 82.5
- Promotion gate decision: `promote_to_candidate_training`
- Gate note: Candidate-training-ready was a permission to run guarded experiments, not evidence that synthetic SFT would improve LoRA behavior.

## Adapter Status

| Adapter | Status | Decision | Strict Avg Delta | Generated Avg Delta | Pattern Benchmark |
|---|---|---|---|---|---|
| generated_candidate_v1 | reject | regression | -3.7 | -1.7 | n/a |
| pattern_only_candidate_v1 | reject | regression | -13.7 | -1.7 | no_change |

## Regression Patterns

- generated_candidate_v1: strict regression and generated regression
- pattern_only_candidate_v1: pattern_only benchmark no_change, but strict and generated benchmarks regress
- Synthetic training signal did not transfer safely even when reference solutions were compile/runtime/semantic validated

## Conclusion

- Do not continue synthetic LoRA training for now.
- Keep generated datasets as isolated evaluation assets.
- Use the generated benchmark for stress testing, not training.
- Final lesson: validated synthetic solutions do not guarantee useful SFT signal.

## Recommended Next Path

- Run a dataset audit before any further synthetic training.
- Prioritize human-curated goldens for repair targets.
- Explore task-specific adapter routing instead of one synthetic LoRA.
- Improve prompt/profile behavior before more LoRA experiments.
- Expand real exam-style verified corpus rather than synthetic-only corpus.
