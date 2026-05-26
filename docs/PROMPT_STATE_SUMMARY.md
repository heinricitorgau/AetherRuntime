# Prompt State Summary

Use this as compact bootstrap context for future agents and automations.

## Current System State

- Project positioning: local-first AI experimentation infrastructure.
- Smoke test: PASS.
- Routing: enabled.
- Adapter governance: enabled.
- Experiment registry: active.
- Release snapshot system: active.
- Latest stable line: V1-V8, including unified CLI and demo platform.
- Default adapter: none selected.
- Stable adapter: `retry_geometry_v3_guarded = safe_no_change`.
- Synthetic training route: frozen.

## Active Guardrails

- Do not automatically promote adapters.
- Do not modify benchmark scoring as incidental work.
- Do not change routing policy without validation and report updates.
- Do not train new adapters unless explicitly requested.
- Do not use benchmark failure outputs as training targets.
- Do not merge unvalidated generated datasets into formal SFT.
- Do not claim production readiness.

## Frozen Routes

- `generated_candidate_v1`: rejected.
- `pattern_only_candidate_v1`: rejected.
- Full synthetic LoRA training: frozen.
- Topic-specific synthetic LoRA training: frozen until dataset audit or a new
  explicit governance decision.

## Stable Adapters

- `retry_geometry_v3_guarded`: `safe_no_change`.
- No default adapter selected.
- Rejected and ablation-only adapters must not be used for routing.

## Active Workflows

- Smoke validation: `python local_ai/cli.py smoke`
- System overview: `python local_ai/cli.py system`
- Adapter registry: `python local_ai/cli.py adapters`
- Routing dry evaluation:
  `python local_ai/cli.py routing --benchmark c_exam_2025_strict_seeded`
- Demo walkthrough: `python local_ai/demo/demo_walkthrough.py`
- Release snapshots: `python local_ai/cli.py snapshot --name <name>`

## Known Limitations

- No promoted/default adapter exists.
- Generated synthetic data passed validation but still caused LoRA regression.
- Routing currently produces plans; it is not a production serving layer.
- Benchmark execution still requires the explicit benchmark workflow and local
  model/proxy path.

## Recommended Next Directions

- Human-curated goldens.
- Benchmark robustness.
- Routing evaluation and reporting.
- Infrastructure stability and smoke coverage.
- Reproducibility and release documentation.
- Demo and presentation layer polish.
- Governance workflows before any renewed training.
