# Golden Baseline Comparison

**Golden run**: `strict_20260515_052032`  
**Current run**: `strict_20260516_031927`  
**Generated**: 2026-05-16T03:26:58+00:00

## Verdict: REGRESSION DETECTED

| Metric | Golden | Current | Delta |
|--------|-------:|--------:|------:|
| Accepted count | 4 | 0 | -4 |
| Avg score | 84.2 | 0.0 | -84.2 |
| Compile pass rate | 100% | 0% | -100.0% |
| Runtime pass rate | 75% | 0% | -75.0% |
| Semantic pass rate | 100% | 0% | -100.0% |
| Keyword pass rate | 100% | 0% | -100.0% |
| Timeout rate | 0% | 100% | +100.0% |

---

> **Regression**: accepted count dropped, avg score dropped > 1.0pt, or timeout rate increased vs golden.

---

*Regression if: accepted drops, avg_score drops > 1.0pt, or timeout_rate rises.*  
*Improvement if: accepted rises or avg_score rises > 1.0pt.*