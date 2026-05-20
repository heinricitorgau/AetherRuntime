"""Benchmark orchestration for the local_ai pipeline.

Runs C-code generation tasks against the local proxy, compiles and executes
results, and scores them deterministically (0-100).

Key entry points:
  run_baseline.py            — standard and --strict-code-only benchmark runs
  compare_against_golden.py  — diff a run against the locked golden baseline
  lock_golden_baseline.py    — promote a run to the golden baseline
  report_analysis.py         — aggregate analysis across multiple runs
"""
