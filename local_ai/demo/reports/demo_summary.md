# Demo Summary

Generated: `2026-05-26T12:39:33+00:00`

## Project Overview

`research-claw-code` is a local-first AI experimentation platform for coding
models. It emphasizes offline benchmark validation, LoRA adapter experiments,
adapter governance, task-specific routing, report indexing, and release
snapshots.

## Key Engineering Milestones

- V1: Local AI SFT infrastructure and compile/runtime benchmark workflow.
- V2: Retry loop, golden repairs, and adapter promotion governance.
- V3: Dataset scaling pipeline, generated corpus validation, and synthetic
  training freeze.
- V4: Task-specific routing based on topic and adapter status.
- V5: System index, report index, and architecture map.
- V6: Fast smoke validation for pre-commit checks.
- V7: Unified CLI for common developer workflows.
- V8: Demo platform index, walkthrough, and portfolio summary.

## Lessons Learned

- Evaluation infrastructure matters as much as training code.
- Adapter promotion should be conservative and evidence-based.
- Runtime correctness can regress even when compile and semantic checks pass.
- Routing by task topic is safer than applying one adapter globally.
- A validated dataset is not automatically useful SFT signal.

## Negative Findings

- Synthetic reference solutions passed compile/runtime/semantic validation but
  still caused LoRA regression.
- `generated_candidate_v1` and `pattern_only_candidate_v1` were rejected.
- Generated datasets are retained as isolated stress tests, not default training
  data.

## Current Stable Status

- Smoke test: PASS.
- No default adapter selected.
- `retry_geometry_v3_guarded` is safe_no_change and geometry-only routable.
- Synthetic LoRA training route is frozen.
- The project is positioned as local-first AI experimentation infrastructure.
