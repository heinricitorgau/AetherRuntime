# CLAUDE.md

This file provides repository context and working conventions for agents
operating on this codebase. `AGENTS.md` mirrors this file — keep both in sync
when workflows change.

## Repository context

- Languages: **Python (primary, active development)** and Rust.
- Active surface: `local_ai/` — offline coding-LLM evaluation, benchmark
  governance, corpus/ingest pipelines, proxy, and RAG. Most changes land here.
- `rust/` holds the `claw` CLI workspace; touch it only when the task is about
  the CLI binary itself.
- Environment: Windows 11, Traditional Chinese locale, offline-first design
  (no network calls at runtime; local Ollama models only).

## Repository shape

| Path | Role |
|------|------|
| `local_ai/` | Active development surface: benchmark, corpus, ingest, model/adapter governance, proxy, RAG, shared helpers |
| `local_ai/config/` | Policies, thresholds, and profiles as JSON — prefer changing data here over changing code |
| `local_ai/shared/` | Cross-subsystem helpers (config loader, report utils, translator, RAG export, regression policy) |
| `rust/` | `claw` CLI Rust workspace |
| `src/` | Early Python port; reference/frozen, not the active surface |
| `tests/` | Python test suite (`tests/local_ai/` covers the active surface) |
| `docs/` | User manual (`USER_MANUAL.md`) and research docs |
| `usb_export/` | Portable release output — never hand-edit; update only via `python local_ai/release/sync_portable_release.py` |

## Verification

Python (run these for changes under `local_ai/`, `src/`, or `tests/`):

- `python local_ai/cli.py smoke` — fast infrastructure smoke test; no models,
  no proxy, no network. Run before committing.
- `python -m pytest tests` — full Python suite (~1 minute, offline).
- Module self-tests: most `local_ai` modules expose `--self-test` that runs
  offline with mocked transports (e.g.
  `python local_ai/shared/translator.py --self-test`). New modules should
  follow this pattern.

Rust (only when changing `rust/`), run from `rust/`:

- `cargo fmt`
- `cargo clippy --workspace --all-targets -- -D warnings`
- `cargo test --workspace`

When behavior in `local_ai/` changes, update `tests/local_ai/` in the same
change. Stale tests that silently stop being collected have caused drift
before — if you add a test package directory, make sure it has `__init__.py`
so it does not shadow the real `local_ai` package.

## Working conventions

| Convention | Rationale |
|------------|-----------|
| Policies and thresholds are data (`local_ai/config/*.json`), not code | Behavior tuning stays auditable and reversible |
| Reports come in JSON + MD pairs; `*/reports/` content is generated | Edit the generating script, then regenerate — never hand-edit report files |
| Data-mutating steps preserve originals and append to audit logs | Governance-first: e.g. translation keeps `prompt_original`, corpus writes `metadata/audit_log.jsonl` |
| New modules ship an offline `--self-test` | Agents can verify changes without models or network |
| Prefer small, reviewable changes | Keeps diffs auditable; generated-report churn already adds noise |
| Keep shared defaults in `.claude.json`; machine-local state in `.claude/settings.local.json` | Separates project defaults from per-machine state |
| Do not overwrite existing `CLAUDE.md` / `AGENTS.md` content automatically | Updates are intentional when repo workflows change |

## Windows / locale notes

- Always pass `encoding="utf-8"` when reading/writing files from Python
  (already the codebase norm — keep it).
- Console output of Chinese text may appear as mojibake under cp950; this is
  display-only. Verify file contents by reading the file, not by trusting
  terminal rendering.
- Paths may contain spaces and Chinese characters (the repo lives under
  OneDrive); quote paths in shell commands.

## Guardrails

- Do not run unbounded synthetic LoRA training.
- Do not automatically promote adapters or models — promotion goes through the
  policy executors and their reports.
- Do not modify benchmark scoring as incidental work.
- Do not change routing policy without validation and report updates.
- Do not use benchmark failure outputs as training targets.
- Do not merge unvalidated generated datasets into formal SFT data.
