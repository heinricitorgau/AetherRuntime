# Response Analysis Report

**Run ID**: `strict_20260516_031927`  
**Model**: `?`  
**Mode**: standard  
**max_tokens**: ?  
**temperature**: ?  
**Timestamp**: 2026-05-16T03:26:27+00:00

---

## Token Budget Efficiency

| Metric | Value |
|--------|------:|
| Avg response length (chars) | 0 |
| Avg code length (chars) | 0 |
| Avg explanation/prose (chars) | 0 |
| Avg code ratio | 0% |
| Avg explanation waste | 100% |
| Avg markdown waste (of prose) | 0% |

## Quality Flags

| Flag | Count | Rate |
|------|------:|-----:|
| Proxy timeout | 4 | 100% |
| Empty response | 4 | — |
| Truncated code | 4 | 100% |
| Used ```c fence | 0 | 0% |
| Contains CJK text | 0 | 0% |
| Explanation waste (>30% prose) | 4 | 100% |
| Markdown heading lines (total) | 0 | — |

## Per-Case Detail

| ID | Chars | Code% | Trunc | Fence | CJK | Timeout |
|----|------:|------:|-------|-------|-----|---------|
| `2025_midterm_001` | 0 | 0% | YES | no | no | TIMEOUT |
| `2025_midterm_002` | 0 | 0% | YES | no | no | TIMEOUT |
| `2025_midterm_003` | 0 | 0% | YES | no | no | TIMEOUT |
| `2025_midterm_004` | 0 | 0% | YES | no | no | TIMEOUT |

---

**Interpretation guide**

- Code% < 60%: model is wasting tokens on explanation — use `--strict-code-only`
- Truncated > 20%: max_tokens too low — increase or use `--strict-code-only` to shrink prose
- CJK text present: model is responding in Chinese — add 'Respond in English only' to prompt
- Fence usage < 80%: model is not wrapping code — extraction falls back to heuristic