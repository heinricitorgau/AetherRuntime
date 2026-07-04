# Prompt / Profile Governance Report

Generated: `2026-06-25T06:04:35+00:00`  
Decision: **pass**  
Approved: 1/1

## Profiles

| Profile | Prompt file | Exists | Deterministic | Status |
|---------|-------------|:------:|:-------------:|--------|
| `strict_code_only_v2_seeded` | `code_gen_strict_v2.txt` | True | False | approved |

## Issues

None.

## Warnings

- strict_code_only_v2_seeded: temperature=0.1 is non-deterministic

## Guardrails

- Read-only validation; runs no models, changes no scoring or prompts.
- Non-deterministic temperatures are flagged, not silently accepted.
