# AGENTS.md

This file provides repository context and working conventions for agents operating on this codebase.

## Repository context

- Languages: Rust.
- Frameworks: none detected from supported starter markers.

## Verification

- Run Rust verification from `rust/`: `cargo fmt`, `cargo clippy --workspace --all-targets -- -D warnings`, `cargo test --workspace`
- `src/` and `tests/` are both present; update both surfaces together when behavior changes.

**Rationale**: requiring `clippy` with `-D warnings` and coordinated `src/`+`tests/` updates enforces that behavioral changes are reflected at the verification surface before commit.

## Repository shape

| Path | Role |
|------|------|
| `rust/` | Rust workspace and active CLI/runtime implementation |
| `src/` | Source files that should stay consistent with generated guidance and tests |
| `tests/` | Validation surfaces reviewed alongside code changes |

## Working conventions

| Convention | Rationale |
|------------|-----------|
| Prefer small, reviewable changes | Keeps generated bootstrap files aligned with actual repo workflows and makes diffs auditable |
| Keep shared defaults in `.Codex.json` | Separates machine-local state (`.Codex/settings.local.json`) from shared project defaults |
| Do not overwrite existing `AGENTS.md` content automatically | Updates are intentional when repo workflows change, not incidental side effects of agent runs |
