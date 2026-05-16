# Response Analysis Report

**Run ID**: `strict_20260516_084819`  
**Model**: `?`  
**Mode**: standard  
**max_tokens**: ?  
**temperature**: ?  
**Timestamp**: 2026-05-16T08:54:49+00:00

---

## Token Budget Efficiency

| Metric | Value |
|--------|------:|
| Avg response length (chars) | 725 |
| Avg code length (chars) | 717 |
| Avg explanation/prose (chars) | 0 |
| Avg code ratio | 99% |
| Avg explanation waste | 1% |
| Avg markdown waste (of prose) | 0% |

## Quality Flags

| Flag | Count | Rate |
|------|------:|-----:|
| Proxy timeout | 0 | 0% |
| Empty response | 0 | — |
| Truncated code | 0 | 0% |
| Used ```c fence | 4 | 100% |
| Contains CJK text | 0 | 0% |
| Explanation waste (>30% prose) | 0 | 0% |
| Markdown heading lines (total) | 0 | — |

## Per-Case Detail

| ID | Chars | Code% | Trunc | Fence | CJK | Timeout |
|----|------:|------:|-------|-------|-----|---------|
| `2025_midterm_001` | 496 | 98% | ok | yes | no | ok |
| `2025_midterm_002` | 578 | 99% | ok | yes | no | ok |
| `2025_midterm_003` | 1373 | 99% | ok | yes | no | ok |
| `2025_midterm_004` | 453 | 98% | ok | yes | no | ok |

---

**Interpretation guide**

- Code% < 60%: model is wasting tokens on explanation — use `--strict-code-only`
- Truncated > 20%: max_tokens too low — increase or use `--strict-code-only` to shrink prose
- CJK text present: model is responding in Chinese — add 'Respond in English only' to prompt
- Fence usage < 80%: model is not wrapping code — extraction falls back to heuristic