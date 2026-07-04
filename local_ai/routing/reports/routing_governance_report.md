# Routing Governance Report

Generated: `2026-06-25T06:13:14+00:00`  
Verdict: **pass**

- Usable adapters: ['retry_geometry_v3_guarded']
- Blocked adapters: —
- Plan adapter decisions checked: 1

## Violations

None — routing selects only governed-approved adapters.

## Warnings

None.

## Guardrails

- Read-only audit; runs no models, changes no routing policy.
- A violation means routing could use a non-approved adapter — block release until fixed.
