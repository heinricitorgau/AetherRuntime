# V3 Dataset Scaling

V3 tested whether a validated synthetic C corpus could safely expand the local
SFT training surface.

## What Was Built

- `generated_tasks.jsonl`: 40 generated C task specs.
- `generated_solutions.jsonl`: 40 reference solutions.
- `accepted_generated_solutions.jsonl`: 40 accepted reference solutions.
- `generated_sft_chatml.jsonl`: 40 isolated SFT records.
- `generated_benchmark_cases.jsonl`: 40 isolated benchmark cases.

The corpus covers four topics:

- `series_calculation`
- `pattern_generation`
- `geometry`
- `game_simulation`

All reference solutions passed compile, runtime, and semantic validation before
packaging.

## Generated Benchmark

The generated benchmark run `strict_20260523_205251` produced:

- tasks: 40
- accepted: 34/40
- average score: 82.5

The benchmark was useful as a stress test. It exposed low-score cases in
`game_simulation`, `geometry`, and `series_calculation`, while
`pattern_generation` was the strongest topic.

## Promotion Gate

The generated dataset promotion gate classified `generated_sft_candidate_v1` as
`promote_to_candidate_training`.

That decision meant the dataset was allowed into isolated, guarded experiments.
It did not mean the dataset should become a default corpus, and it did not imply
that synthetic SFT would improve LoRA behavior.

## LoRA Experiments

Two synthetic LoRA experiments were run:

| Adapter | Corpus | Result |
|---------|--------|--------|
| `generated_candidate_v1` | full 40-record generated corpus | reject |
| `pattern_only_candidate_v1` | topic-specific pattern records | reject |

`generated_candidate_v1` regressed both the strict exam benchmark and the
generated benchmark.

`pattern_only_candidate_v1` did not improve the pattern-only benchmark and still
regressed the strict and generated benchmarks.

## Final Lesson

Validated synthetic solutions do not guarantee useful SFT signal.

The generated datasets should be retained as isolated benchmark and evaluation
assets, but synthetic LoRA training should be frozen for now.

## Next Direction

- Audit generated task specs and checkers before further training use.
- Prioritize human-curated goldens for repair targets.
- Explore task-specific adapter routing rather than broad synthetic adapters.
- Improve prompts and benchmark profiles before more LoRA training.
- Expand a real exam-style verified corpus instead of relying on synthetic-only
  records.
