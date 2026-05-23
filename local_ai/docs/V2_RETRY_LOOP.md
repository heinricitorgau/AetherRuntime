# V2 Retry Loop

V2 exists to make local coding-model repair experiments repeatable and
guarded. The goal is not to declare a self-improving or production-ready model.
The goal is infrastructure: mine failures, build targeted retry datasets,
train small LoRA adapters, benchmark them against the base model, and govern
adapter promotion decisions with explicit guardrails.

## Why V2 Exists

The strict 2025 C benchmark already tracks compile, runtime, semantic, keyword,
and accepted signals. V2 adds a loop around those signals:

1. Find benchmark failures and regressions.
2. Convert trusted fixes into retry training examples.
3. Train limited-scope LoRA adapters.
4. Benchmark base versus adapter.
5. Classify the adapter instead of automatically promoting it.

This supports iterative model repair while keeping regression evidence visible.

## Failure Taxonomy

The retry loop tracks failure categories such as:

- `missing_entrypoint`: output lacks a complete `int main(void)`.
- `hallucinated_function`: generated code calls undeclared helpers or invalid C.
- `geometry_reasoning`: incorrect geometry enumeration or area logic.
- `runtime_logic`: code compiles but fails sample runtime tokens.
- `io_format_error`: output misses required tokens or prompt-visible labels.
- `array_bounds`: game or array code risks invalid indexing.

The taxonomy is used to select repair targets and to explain why an adapter is
retained only for ablation when it regresses guardrails.

## Retry Dataset Flow

The V2 retry dataset flow is:

```text
benchmark comparison
  -> failure mining / regression analysis
  -> curated golden repair target
  -> mixed retry round
  -> LoRA training job
  -> base-vs-LoRA benchmark
  -> promotion policy
  -> adapter registry
```

The mixed retry rounds are intentionally small and conservative. The project
does not add more low-quality recursive self-repair examples when a round
regresses runtime correctness.

## Golden Repair Targets

Golden repair targets are human-curated C99 solutions that are compile and
runtime verified before they are used as trusted retry targets.

Current goldens:

- `2025_midterm_003_golden.c`: geometry triangle enumeration, Heron's formula,
  collinear detection, and output containing `area` and `6.000`.
- `2025_midterm_004_golden.c`: game simulation guard using arrays, `srand`,
  input/output tokens `Numbers`, `Pick`, `win`, and `points`.

Goldens are validated with:

```powershell
python local_ai/goldens/validate_goldens.py
```

## Why V1 And V2 Regressed

`retry_geometry_v1` and `retry_geometry_v2` preserved compile and semantic
signals but reduced runtime pass rate from 75% to 50%. The primary regression
moved from the geometry task in v1 to the game simulation task in v2.

This showed that geometry-focused retry training could interfere with runtime
behavior outside the targeted task. The lesson was not to increase epochs or
add more narrow geometry examples. Instead, V3 added a game simulation golden
guard and reduced training strength.

## Why V3 Is Safe No Change

`retry_geometry_v3_guarded` combines:

- geometry golden repair for `2025_midterm_003`
- game golden guard for `2025_midterm_004`
- anti-regression examples for `2025_midterm_001` and `2025_midterm_002`
- lower training strength: 1 epoch and learning rate `0.000025`

The latest comparison classifies it as `safe_no_change`:

- accepted remains 4/4
- compile remains 100%
- runtime remains 75%
- semantic remains 100%
- average score remains unchanged

This means the adapter is safe to keep available, but it is not promoted as the
default adapter.

## Adapter Promotion Policy

Adapters are classified by `promotion_policy.py` and written to registry files
by `promote_adapter.py`.

Statuses:

- `promote`: positive average score delta with no accepted, compile, runtime,
  semantic, or per-task guardrail regression.
- `safe_no_change`: no material aggregate change and all guardrails held.
- `ablation_only`: useful research evidence, but not eligible for default use
  because a guardrail or task-level delta regressed.
- `reject`: failed a core guardrail or had severe runtime/task collapse.

Rejected and ablation adapters are kept because they document failure modes and
support future adapter selection or routing work. The governance scripts do not
delete adapter artifacts.

## Adapter Registry

List governed adapters:

```powershell
python local_ai/sft/list_adapters.py
python local_ai/sft/list_adapters.py --status safe_no_change
python local_ai/sft/list_adapters.py --format json
```

Current state:

- default adapter: none selected
- `retry_geometry_v3_guarded`: `safe_no_change`

## How To Reproduce

Build and validate the V3 guarded retry loop:

```powershell
python local_ai/goldens/validate_goldens.py
python local_ai/retry/build_mixed_retry_round.py --round round_geometry_v3_guarded
python local_ai/config/validate_profiles.py
python local_ai/sft/train_lora.py --job retry_geometry_v3_guarded
python local_ai/sft/benchmark_lora.py --benchmark c_exam_2025_strict_seeded --adapter local_ai/sft/artifacts/retry_geometry_v3_guarded
python local_ai/sft/analyze_lora_regression.py
python local_ai/sft/promote_adapter.py --adapter local_ai/sft/artifacts/retry_geometry_v3_guarded --comparison local_ai/sft/reports/comparison_report.json
python local_ai/sft/list_adapters.py
```

Create the V2 milestone snapshot:

```powershell
python local_ai/release/snapshot.py --name local_ai_retry_loop_v2
```

The snapshot summarizes existing reports. It does not rerun training or
benchmark jobs.
