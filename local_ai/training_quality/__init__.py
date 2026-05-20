"""Data quality validation pipeline for C-programming training records.

This package will be renamed to local_ai.quality in Phase 2.
A backward-compatible shim will keep existing CLI paths working:
  python local_ai/training_quality/sft_readiness_check.py   # still works via shim
  python local_ai/quality/sft_readiness_check.py            # new canonical path

Validators:
  compile_validator   — compile every training record's C code
  runtime_validator   — run compiled binaries, check stdout
  keyword_validator   — assert required C constructs are present
  structure_validator — check #include / int main / brace balance
  semantic_validator  — static analysis (scanf mismatch, infinite loops)
  static_analysis     — pure-regex C static analyser (no external deps)
  score_records       — compute 0-100 quality scores
  sft_readiness_check — end-to-end pipeline readiness report
"""
