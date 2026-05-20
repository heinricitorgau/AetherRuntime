# shared

Common utilities that can be reused across `local_ai` subsystems without
changing existing CLI entrypoints.

Phase 1 adds stable helpers for paths, JSONL I/O, environment parsing, logging,
and report writing. Later phases may migrate duplicated call sites onto these
helpers incrementally while keeping old imports working during the transition.
