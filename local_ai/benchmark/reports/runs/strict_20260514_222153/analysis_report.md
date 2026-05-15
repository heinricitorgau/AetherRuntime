# Response Analysis Report

**Run ID**: `strict_20260514_222153`  
**Model**: `?`  
**Mode**: standard  
**max_tokens**: ?  
**temperature**: ?  
**Timestamp**: 2026-05-14T22:24:12+00:00

---

## Token Budget Efficiency

| Metric | Value |
|--------|------:|
| Avg response length (chars) | 938 |
| Avg code length (chars) | 913 |
| Avg explanation/prose (chars) | 21 |
| Avg code ratio | 95% |
| Avg explanation waste | 5% |
| Avg markdown waste (of prose) | 25% |

## Quality Flags

| Flag | Count | Rate |
|------|------:|-----:|
| Proxy timeout | 0 | 0% |
| Empty response | 0 | — |
| Truncated code | 0 | 0% |
| Used ```c fence | 4 | 100% |
| Contains CJK text | 4 | 100% |
| Explanation waste (>30% prose) | 0 | 0% |
| Markdown heading lines (total) | 2 | — |

## Per-Case Detail

| ID | Chars | Code% | Trunc | Fence | CJK | Timeout |
|----|------:|------:|-------|-------|-----|---------|
| `2025_midterm_001` | 437 | 90% | ok | yes | YES | ok |
| `2025_midterm_002` | 594 | 92% | ok | yes | YES | ok |
| `2025_midterm_003` | 1210 | 100% | ok | yes | YES | ok |
| `2025_midterm_004` | 1510 | 100% | ok | yes | YES | ok |

---

**Interpretation guide**

- Code% < 60%: model is wasting tokens on explanation — use `--strict-code-only`
- Truncated > 20%: max_tokens too low — increase or use `--strict-code-only` to shrink prose
- CJK text present: model is responding in Chinese — add 'Respond in English only' to prompt
- Fence usage < 80%: model is not wrapping code — extraction falls back to heuristic