# Deployment Readiness Report

Generated: `2026-06-25T06:18:28+00:00`  
Verdict: **blocked**

## Checks

| Check | Result | Detail |
|-------|:------:|--------|
| `smoke` | PASS | status=PASS |
| `config` | PASS | issues=0 |
| `profile_governance` | PASS | decision=pass |
| `routing_governance` | PASS | verdict=pass |
| `regression` | FAIL | latest verdict=regression |
| `reliability` | FAIL | verdict=flaky stamp_rate=0.141 |
| `awaiting_review` | FAIL | 1 awaiting manual review |
| `human_goldens` | FAIL | human_verified=0 |

## Blocked By

- regression: latest verdict=regression

## Warnings

- reliability: verdict=flaky stamp_rate=0.141
- awaiting_review: 1 awaiting manual review
- human_goldens: human_verified=0

## Guardrails

- Read-only aggregation of governance reports; runs no models, changes no state.
- A blocking check that has never run counts as a block (unknown == unsafe).
- `blocked` exits non-zero so deployment automation can refuse to ship.
