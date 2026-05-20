# Response Analysis Report

**Run ID**: `strict_20260517_201150`  
**Model**: `?`  
**Mode**: standard  
**max_tokens**: ?  
**temperature**: ?  
**Timestamp**: 2026-05-17T20:45:02+00:00

---

## Token Budget Efficiency

| Metric | Value |
|--------|------:|
| Avg response length (chars) | 1227 |
| Avg code length (chars) | 1107 |
| Avg explanation/prose (chars) | 115 |
| Avg code ratio | 93% |
| Avg explanation waste | 7% |
| Avg markdown waste (of prose) | 0% |

## Quality Flags

| Flag | Count | Rate |
|------|------:|-----:|
| Proxy timeout | 0 | 0% |
| Empty response | 0 | — |
| Truncated code | 1 | 6% |
| Used ```c fence | 16 | 100% |
| Contains CJK text | 0 | 0% |
| Explanation waste (>30% prose) | 1 | 6% |
| Markdown heading lines (total) | 0 | — |

## Per-Case Detail

| ID | Chars | Code% | Trunc | Fence | CJK | Timeout |
|----|------:|------:|-------|-------|-----|---------|
| `2021_exam2_001` | 729 | 99% | ok | yes | no | ok |
| `2021_exam2_002` | 1372 | 99% | ok | yes | no | ok |
| `2021_exam2_003` | 1190 | 99% | ok | yes | no | ok |
| `2021_exam2_004` | 1815 | 0% | YES | yes | no | ok |
| `2022_exam2_001` | 623 | 99% | ok | yes | no | ok |
| `2022_exam2_002` | 1471 | 100% | ok | yes | no | ok |
| `2022_exam2_003` | 1441 | 99% | ok | yes | no | ok |
| `2022_exam2_004` | 1520 | 100% | ok | yes | no | ok |
| `2023_exam2_001` | 570 | 99% | ok | yes | no | ok |
| `2023_exam2_002` | 1489 | 100% | ok | yes | no | ok |
| `2023_exam2_003` | 1441 | 99% | ok | yes | no | ok |
| `2023_exam2_004` | 1474 | 100% | ok | yes | no | ok |
| `2024_exam2_001` | 945 | 99% | ok | yes | no | ok |
| `2024_exam2_002` | 678 | 99% | ok | yes | no | ok |
| `2024_exam2_003` | 1056 | 99% | ok | yes | no | ok |
| `2024_exam2_004` | 1824 | 100% | ok | yes | no | ok |

---

**Interpretation guide**

- Code% < 60%: model is wasting tokens on explanation — use `--strict-code-only`
- Truncated > 20%: max_tokens too low — increase or use `--strict-code-only` to shrink prose
- CJK text present: model is responding in Chinese — add 'Respond in English only' to prompt
- Fence usage < 80%: model is not wrapping code — extraction falls back to heuristic