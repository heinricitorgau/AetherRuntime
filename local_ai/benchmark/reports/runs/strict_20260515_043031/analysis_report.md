# Response Analysis Report

**Run ID**: `strict_20260515_043031`  
**Model**: `?`  
**Mode**: standard  
**max_tokens**: ?  
**temperature**: ?  
**Timestamp**: 2026-05-15T04:42:05+00:00

---

## Token Budget Efficiency

| Metric | Value |
|--------|------:|
| Avg response length (chars) | 729 |
| Avg code length (chars) | 684 |
| Avg explanation/prose (chars) | 37 |
| Avg code ratio | 92% |
| Avg explanation waste | 8% |
| Avg markdown waste (of prose) | 50% |

## Quality Flags

| Flag | Count | Rate |
|------|------:|-----:|
| Proxy timeout | 0 | 0% |
| Empty response | 0 | — |
| Truncated code | 0 | 0% |
| Used ```c fence | 4 | 100% |
| Contains CJK text | 4 | 100% |
| Explanation waste (>30% prose) | 0 | 0% |
| Markdown heading lines (total) | 4 | — |

## Per-Case Detail

| ID | Chars | Code% | Trunc | Fence | CJK | Timeout |
|----|------:|------:|-------|-------|-----|---------|
| `2025_midterm_001` | 646 | 93% | ok | yes | YES | ok |
| `2025_midterm_002` | 272 | 84% | ok | yes | YES | ok |
| `2025_midterm_003` | 1253 | 96% | ok | yes | YES | ok |
| `2025_midterm_004` | 744 | 94% | ok | yes | YES | ok |

---

**Interpretation guide**

- Code% < 60%: model is wasting tokens on explanation — use `--strict-code-only`
- Truncated > 20%: max_tokens too low — increase or use `--strict-code-only` to shrink prose
- CJK text present: model is responding in Chinese — add 'Respond in English only' to prompt
- Fence usage < 80%: model is not wrapping code — extraction falls back to heuristic