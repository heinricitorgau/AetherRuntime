"""mine_failures.py — scan benchmark runs and experiment registry for failure patterns.

Outputs:
    local_ai/analysis/reports/failure_summary.json
    local_ai/analysis/reports/failure_summary.md
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Allow running as a script from any CWD
_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
if str(_LOCAL_AI.parent) not in sys.path:
    sys.path.insert(0, str(_LOCAL_AI.parent))

from local_ai.shared.jsonl import read_jsonl
from local_ai.analysis.failure_taxonomy import classify, primary, CATEGORY_NAMES

BENCHMARK_DIR  = _LOCAL_AI / "benchmark"
EXPERIMENTS_DIR = _LOCAL_AI / "experiments" / "registry"
REPORTS_DIR    = _HERE / "reports"

# ── helpers ──────────────────────────────────────────────────────────────────

def _iter_run_failed_cases() -> list[dict]:
    """Yield every failed case from every per-run failed_cases.jsonl."""
    records = []
    runs_dir = BENCHMARK_DIR / "reports" / "runs"
    if not runs_dir.exists():
        return records
    for run_dir in sorted(runs_dir.iterdir()):
        fc = run_dir / "failed_cases.jsonl"
        if fc.exists():
            try:
                records.extend(read_jsonl(fc))
            except Exception:
                pass
    return records


def _load_consolidated() -> list[dict]:
    """Load the top-level consolidated failed_cases.jsonl if present."""
    p = BENCHMARK_DIR / "reports" / "failed_cases.jsonl"
    if p.exists():
        try:
            return read_jsonl(p)
        except Exception:
            pass
    return []


def _deduplicate(records: list[dict]) -> list[dict]:
    """Deduplicate by (id, model, timestamp) keeping latest."""
    seen: dict[tuple, dict] = {}
    for r in records:
        key = (r.get("id", ""), r.get("model", ""), r.get("timestamp", ""))
        seen[key] = r
    return list(seen.values())


def _load_experiment_registry() -> list[dict]:
    exps = []
    if not EXPERIMENTS_DIR.exists():
        return exps
    for p in sorted(EXPERIMENTS_DIR.glob("*.json")):
        try:
            exps.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass
    return exps


# ── analysis ─────────────────────────────────────────────────────────────────

def _analyse_failures(records: list[dict]) -> dict:
    total = len(records)
    if total == 0:
        return {"total_failures": 0}

    primary_counter: Counter[str] = Counter()
    multi_counter:   Counter[str] = Counter()
    topic_failures:  Counter[str] = Counter()
    year_failures:   Counter[int] = Counter()
    model_failures:  Counter[str] = Counter()
    score_dist: list[int] = []
    by_topic: defaultdict[str, Counter] = defaultdict(Counter)

    for r in records:
        p  = primary(r)
        cs = classify(r)
        primary_counter[p] += 1
        for c in cs:
            multi_counter[c] += 1

        topic = (r.get("task_meta", {}) or {}).get("topic", "unknown")
        year  = (r.get("task_meta", {}) or {}).get("year", 0)
        model = r.get("model", "unknown")
        score = r.get("score", 0) or 0

        topic_failures[topic] += 1
        year_failures[year]   += 1
        model_failures[model] += 1
        score_dist.append(score)
        by_topic[topic][p] += 1

    avg_score = sum(score_dist) / len(score_dist) if score_dist else 0.0

    # Check-level aggregate
    check_pass_rates: dict[str, float] = {}
    check_keys = ["proxy", "truncation", "structure", "compile", "runtime", "semantic", "keyword"]
    for ck in check_keys:
        passed = sum(
            1 for r in records
            if (r.get("checks", {}) or {}).get(ck, {}).get("passed", False)
        )
        check_pass_rates[ck] = round(passed / total, 4)

    return {
        "total_failures": total,
        "avg_score_on_failures": round(avg_score, 2),
        "check_pass_rates": check_pass_rates,
        "primary_failure_counts": dict(primary_counter.most_common()),
        "multi_label_counts": dict(multi_counter.most_common()),
        "top_failing_topics": dict(topic_failures.most_common(10)),
        "failures_by_year": {str(k): v for k, v in sorted(year_failures.items())},
        "failures_by_model": dict(model_failures.most_common()),
        "top_topic_primary_breakdown": {
            t: dict(c.most_common())
            for t, c in sorted(by_topic.items(), key=lambda x: -sum(x[1].values()))[:10]
        },
    }


def _analyse_experiments(exps: list[dict]) -> dict:
    if not exps:
        return {}
    total = len(exps)
    avg_compile = sum(e.get("compile_rate", 0) or 0 for e in exps) / total
    avg_runtime = sum(e.get("runtime_rate", 0) or 0 for e in exps) / total
    avg_timeout = sum(e.get("timeout_rate", 0) or 0 for e in exps) / total
    avg_score   = sum(e.get("avg_score", 0)    or 0 for e in exps) / total
    return {
        "total_experiments": total,
        "avg_compile_rate":  round(avg_compile, 4),
        "avg_runtime_rate":  round(avg_runtime, 4),
        "avg_timeout_rate":  round(avg_timeout, 4),
        "avg_score":         round(avg_score, 4),
    }


# ── markdown renderer ─────────────────────────────────────────────────────────

def _render_md(summary: dict) -> str:
    fa = summary.get("failure_analysis", {})
    ea = summary.get("experiment_analysis", {})
    lines: list[str] = []

    lines += [
        "# Failure Mining Report",
        "",
        f"**Total failed cases analysed:** {fa.get('total_failures', 0)}",
        f"**Average score on failed cases:** {fa.get('avg_score_on_failures', 0)}",
        "",
        "## Check Pass Rates (on failed cases)",
        "",
        "| Check | Pass Rate |",
        "|-------|-----------|",
    ]
    for ck, rate in (fa.get("check_pass_rates") or {}).items():
        lines.append(f"| {ck} | {rate:.1%} |")

    lines += [
        "",
        "## Primary Failure Distribution",
        "",
        "| Category | Count |",
        "|----------|-------|",
    ]
    for cat, cnt in (fa.get("primary_failure_counts") or {}).items():
        pct = cnt / fa["total_failures"] * 100 if fa.get("total_failures") else 0
        lines.append(f"| {cat} | {cnt} ({pct:.1f}%) |")

    lines += [
        "",
        "## Multi-Label Failure Counts",
        "",
        "| Category | Occurrences |",
        "|----------|-------------|",
    ]
    for cat, cnt in (fa.get("multi_label_counts") or {}).items():
        lines.append(f"| {cat} | {cnt} |")

    lines += [
        "",
        "## Top Failing Topics",
        "",
        "| Topic | Failures |",
        "|-------|----------|",
    ]
    for topic, cnt in (fa.get("top_failing_topics") or {}).items():
        lines.append(f"| {topic} | {cnt} |")

    lines += [
        "",
        "## Failures by Year",
        "",
        "| Year | Failures |",
        "|------|----------|",
    ]
    for year, cnt in (fa.get("failures_by_year") or {}).items():
        lines.append(f"| {year} | {cnt} |")

    if ea:
        lines += [
            "",
            "## Experiment Registry Summary",
            "",
            f"- Total experiments: {ea.get('total_experiments')}",
            f"- Avg compile rate:  {ea.get('avg_compile_rate', 0):.1%}",
            f"- Avg runtime rate:  {ea.get('avg_runtime_rate', 0):.1%}",
            f"- Avg timeout rate:  {ea.get('avg_timeout_rate', 0):.1%}",
            f"- Avg score:         {ea.get('avg_score')}",
        ]

    lines += [
        "",
        "## Top Topic × Primary Failure Breakdown",
        "",
    ]
    for topic, breakdown in (fa.get("top_topic_primary_breakdown") or {}).items():
        lines.append(f"**{topic}**")
        for cat, cnt in breakdown.items():
            lines.append(f"  - {cat}: {cnt}")
        lines.append("")

    lines += ["", "---", f"*Generated by mine_failures.py*"]
    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("[mine_failures] Loading failed cases …")
    run_cases    = _iter_run_failed_cases()
    consolidated = _load_consolidated()
    all_cases    = _deduplicate(run_cases + consolidated)
    print(f"  {len(run_cases)} from runs + {len(consolidated)} consolidated → {len(all_cases)} unique")

    print("[mine_failures] Loading experiment registry …")
    exps = _load_experiment_registry()
    print(f"  {len(exps)} experiments")

    print("[mine_failures] Classifying failures …")
    fa = _analyse_failures(all_cases)
    ea = _analyse_experiments(exps)

    summary = {
        "failure_analysis": fa,
        "experiment_analysis": ea,
        "taxonomy_used": list(CATEGORY_NAMES),
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_out = REPORTS_DIR / "failure_summary.json"
    md_out   = REPORTS_DIR / "failure_summary.md"

    json_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    md_out.write_text(_render_md(summary), encoding="utf-8")

    print(f"\n[mine_failures] Reports written:")
    print(f"  {json_out}")
    print(f"  {md_out}")
    print()

    # Quick summary to stdout
    total = fa.get("total_failures", 0)
    print(f"  Total failures: {total}")
    if total:
        print("  Primary failure breakdown:")
        for cat, cnt in list((fa.get("primary_failure_counts") or {}).items())[:6]:
            pct = cnt / total * 100
            print(f"    {cat:<30} {cnt:>4}  ({pct:.1f}%)")


if __name__ == "__main__":
    main()
