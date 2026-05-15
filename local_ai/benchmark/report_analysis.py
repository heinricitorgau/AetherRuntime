#!/usr/bin/env python3
"""Analyse raw model outputs for token waste, code ratio, and timeout patterns.

Reads:  reports/runs/<run_id>/raw_outputs.jsonl
Writes: reports/runs/<run_id>/analysis_report.json
        reports/runs/<run_id>/analysis_report.md

Metrics:
  explanation_waste_ratio  fraction of response chars that are NOT C code
  markdown_waste_ratio     fraction of non-code lines that look like markdown
  code_ratio               fraction of response chars that ARE C code
  fence_usage_rate         fraction of responses that used a ```c fence
  timeout_count            number of proxy timeouts
  timeout_rate             fraction of responses that timed out
  avg_response_chars       average total response length in characters
  avg_code_chars           average extracted C code length
  avg_explanation_chars    average non-code length
  truncation_count         responses where code appears truncated
  truncation_rate          fraction of extracted codes that are truncated
  chinese_text_count       responses containing CJK characters
  chinese_text_rate        fraction with Chinese/Japanese/Korean text
  empty_response_count     zero-length raw responses

These metrics are useful for comparing standard vs --strict-code-only runs.

Usage:
  python local_ai/benchmark/report_analysis.py
  python local_ai/benchmark/report_analysis.py --run-id strict_20260514_120000
  python local_ai/benchmark/report_analysis.py --compare baseline_3b strict_3b
  python local_ai/benchmark/report_analysis.py --results-file path/to/raw_outputs.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from _bench_common import REPORTS_DIR, extract_c, is_truncated, load_jsonl, now_iso, write_json

# ── CJK range ────────────────────────────────────────────────────────────────
_CJK_RE = re.compile(r"[一-鿿぀-ゟ゠-ヿ가-힣]")

# Markdown patterns outside code fences
_MD_HEADING_RE    = re.compile(r"^#{1,6}\s")
_MD_BULLET_RE     = re.compile(r"^[\*\-\+]\s")
_MD_BLOCKQUOTE_RE = re.compile(r"^>\s")
_MD_HR_RE         = re.compile(r"^---+$")
_FENCE_START_RE   = re.compile(r"^```")


def _split_code_and_prose(raw: str) -> tuple[str, str]:
    """Split raw response into (code_text, prose_text).

    code_text:  everything inside the first ```c ... ``` block
    prose_text: everything outside that block (before + after)
    """
    m = re.search(r"```(?:c|C)?\s*\n(.*?)```", raw, re.DOTALL)
    if m:
        code   = m.group(1)
        before = raw[: m.start()]
        after  = raw[m.end() :]
        return code, before + after

    # No fence: try heuristic split
    if "#include" in raw and "int main" in raw:
        start = raw.find("#include")
        return raw[start:], raw[:start]

    return "", raw


def _count_markdown_lines(prose: str) -> int:
    """Count lines in prose that look like markdown formatting."""
    count = 0
    in_fence = False
    for line in prose.splitlines():
        stripped = line.strip()
        if _FENCE_START_RE.match(stripped):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if (
            _MD_HEADING_RE.match(stripped)
            or _MD_BULLET_RE.match(stripped)
            or _MD_BLOCKQUOTE_RE.match(stripped)
            or _MD_HR_RE.match(stripped)
        ):
            count += 1
    return count


# ── Per-record analysis ───────────────────────────────────────────────────────

def analyse_record(raw_rec: dict) -> dict:
    raw     = raw_rec.get("raw_response", "") or ""
    error   = raw_rec.get("proxy_error")
    case_id = raw_rec.get("id", "?")

    timed_out = bool(
        error and ("timeout" in error.lower() or "timed out" in error.lower())
    )
    empty = len(raw.strip()) == 0

    code_text, prose_text = _split_code_and_prose(raw)
    extracted, method     = extract_c(raw)

    total_chars       = len(raw)
    code_chars        = len(code_text)
    prose_chars       = len(prose_text)
    explanation_chars = prose_chars  # same thing, named for clarity

    code_ratio         = code_chars / total_chars if total_chars > 0 else 0.0
    explanation_ratio  = prose_chars / total_chars if total_chars > 0 else 1.0

    md_lines           = _count_markdown_lines(prose_text)
    prose_lines        = len([l for l in prose_text.splitlines() if l.strip()])
    markdown_ratio     = md_lines / prose_lines if prose_lines > 0 else 0.0

    has_fence          = bool(re.search(r"```(?:c|C)?", raw))
    has_cjk            = bool(_CJK_RE.search(raw))
    truncated          = is_truncated(extracted) if extracted else True

    return {
        "id":                case_id,
        "timed_out":         timed_out,
        "empty":             empty,
        "has_fence":         has_fence,
        "extract_method":    method,
        "truncated":         truncated,
        "has_cjk":           has_cjk,
        "total_chars":       total_chars,
        "code_chars":        code_chars,
        "explanation_chars": explanation_chars,
        "code_ratio":        round(code_ratio, 3),
        "explanation_ratio": round(explanation_ratio, 3),
        "md_lines":          md_lines,
        "prose_lines":       prose_lines,
        "markdown_ratio":    round(markdown_ratio, 3),
    }


# ── Aggregate metrics ─────────────────────────────────────────────────────────

def compute_analysis(records: list[dict]) -> dict:
    n = len(records)
    if n == 0:
        return {}

    per_case = [analyse_record(r) for r in records]

    def _sum(key: str) -> int | float:
        return sum(r[key] for r in per_case)

    def _count(key: str) -> int:
        return sum(1 for r in per_case if r[key])

    def _avg(key: str) -> float:
        return round(_sum(key) / n, 1)

    def _rate(key: str) -> float:
        return round(_count(key) / n, 3)

    total_chars_list = [r["total_chars"] for r in per_case]
    code_chars_list  = [r["code_chars"]  for r in per_case]
    expl_chars_list  = [r["explanation_chars"] for r in per_case]
    code_ratio_list  = [r["code_ratio"] for r in per_case]

    explanation_waste_signal_count = sum(
        1 for r in per_case if r["explanation_ratio"] > 0.3
    )
    markdown_heading_count = sum(r["md_lines"] for r in per_case)

    return {
        "cases_analysed":                 n,
        "timeout_count":                  _count("timed_out"),
        "timeout_rate":                   _rate("timed_out"),
        "empty_response_count":           _count("empty"),
        "fence_usage_count":              _count("has_fence"),
        "fence_usage_rate":               _rate("has_fence"),
        "truncation_count":               _count("truncated"),
        "truncation_rate":                _rate("truncated"),
        "chinese_text_count":             _count("has_cjk"),
        "chinese_text_rate":              _rate("has_cjk"),
        "explanation_waste_signal_count": explanation_waste_signal_count,
        "explanation_waste_signal_rate":  round(explanation_waste_signal_count / n, 3),
        "markdown_heading_count":         markdown_heading_count,
        "avg_response_chars":             _avg("total_chars"),
        "avg_code_chars":                 _avg("code_chars"),
        "avg_explanation_chars":          _avg("explanation_chars"),
        "avg_code_ratio":                 round(sum(code_ratio_list) / n, 3),
        "avg_explanation_ratio":          round(1.0 - sum(code_ratio_list) / n, 3),
        "avg_markdown_ratio":             round(sum(r["markdown_ratio"] for r in per_case) / n, 3),
        "min_response_chars":             min(total_chars_list),
        "max_response_chars":             max(total_chars_list),
        "per_case":                       per_case,
    }


# ── Markdown report ───────────────────────────────────────────────────────────

def write_analysis_markdown(analysis: dict, meta: dict, path: Path) -> None:
    n = analysis.get("cases_analysed", 0)
    lines: list[str] = []
    a = lines.append

    a("# Response Analysis Report")
    a("")
    a(f"**Run ID**: `{meta.get('run_id', '?')}`  ")
    a(f"**Model**: `{meta.get('model', '?')}`  ")
    a(f"**Mode**: {'STRICT code-only' if meta.get('strict_code_only') else 'standard'}  ")
    a(f"**max_tokens**: {meta.get('max_tokens', '?')}  ")
    a(f"**temperature**: {meta.get('temperature', '?')}  ")
    a(f"**Timestamp**: {analysis.get('timestamp', '?')}")
    a("")
    a("---")
    a("")
    a("## Token Budget Efficiency")
    a("")
    a("| Metric | Value |")
    a("|--------|------:|")
    a(f"| Avg response length (chars) | {analysis.get('avg_response_chars', 0):.0f} |")
    a(f"| Avg code length (chars) | {analysis.get('avg_code_chars', 0):.0f} |")
    a(f"| Avg explanation/prose (chars) | {analysis.get('avg_explanation_chars', 0):.0f} |")
    a(f"| Avg code ratio | {analysis.get('avg_code_ratio', 0):.0%} |")
    a(f"| Avg explanation waste | {analysis.get('avg_explanation_ratio', 0):.0%} |")
    a(f"| Avg markdown waste (of prose) | {analysis.get('avg_markdown_ratio', 0):.0%} |")
    a("")
    a("## Quality Flags")
    a("")
    a("| Flag | Count | Rate |")
    a("|------|------:|-----:|")
    a(f"| Proxy timeout | {analysis.get('timeout_count', 0)} | {analysis.get('timeout_rate', 0):.0%} |")
    a(f"| Empty response | {analysis.get('empty_response_count', 0)} | — |")
    a(f"| Truncated code | {analysis.get('truncation_count', 0)} | {analysis.get('truncation_rate', 0):.0%} |")
    a(f"| Used ```c fence | {analysis.get('fence_usage_count', 0)} | {analysis.get('fence_usage_rate', 0):.0%} |")
    a(f"| Contains CJK text | {analysis.get('chinese_text_count', 0)} | {analysis.get('chinese_text_rate', 0):.0%} |")
    a(f"| Explanation waste (>30% prose) | {analysis.get('explanation_waste_signal_count', 0)} | {analysis.get('explanation_waste_signal_rate', 0):.0%} |")
    a(f"| Markdown heading lines (total) | {analysis.get('markdown_heading_count', 0)} | — |")
    a("")
    a("## Per-Case Detail")
    a("")
    a("| ID | Chars | Code% | Trunc | Fence | CJK | Timeout |")
    a("|----|------:|------:|-------|-------|-----|---------|")
    for pc in analysis.get("per_case", []):
        trunc   = "YES" if pc["truncated"] else "ok"
        fence   = "yes" if pc["has_fence"] else "no"
        cjk     = "YES" if pc["has_cjk"]   else "no"
        timeout = "TIMEOUT" if pc["timed_out"] else "ok"
        a(f"| `{pc['id']}` | {pc['total_chars']} | {pc['code_ratio']:.0%} | {trunc} | {fence} | {cjk} | {timeout} |")
    a("")
    a("---")
    a("")
    a("**Interpretation guide**")
    a("")
    a("- Code% < 60%: model is wasting tokens on explanation — use `--strict-code-only`")
    a("- Truncated > 20%: max_tokens too low — increase or use `--strict-code-only` to shrink prose")
    a("- CJK text present: model is responding in Chinese — add 'Respond in English only' to prompt")
    a("- Fence usage < 80%: model is not wrapping code — extraction falls back to heuristic")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# ── CLI helpers ───────────────────────────────────────────────────────────────

def _latest_run_id() -> str | None:
    runs_dir = REPORTS_DIR / "runs"
    if not runs_dir.exists():
        return None
    dirs = sorted(
        (d for d in runs_dir.iterdir() if d.is_dir() and (d / "raw_outputs.jsonl").exists()),
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    return dirs[0].name if dirs else None


def analyse_run(run_id: str) -> dict:
    run_dir      = REPORTS_DIR / "runs" / run_id
    raw_path     = run_dir / "raw_outputs.jsonl"
    meta_path    = run_dir / "meta.json"

    if not raw_path.exists():
        print(f"[analysis] raw_outputs.jsonl not found in {run_dir}", file=sys.stderr)
        sys.exit(1)

    raw_records = load_jsonl(raw_path)
    meta        = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    analysis = compute_analysis(raw_records)
    analysis["timestamp"] = now_iso()
    analysis["run_id"]    = run_id

    out_json = run_dir / "analysis_report.json"
    out_md   = run_dir / "analysis_report.md"

    write_json(analysis, out_json)
    write_analysis_markdown(analysis, {**meta, "run_id": run_id}, out_md)

    return analysis


def compare_runs(run_ids: list[str]) -> None:
    analyses: list[dict] = []
    for rid in run_ids:
        a = analyse_run(rid)
        a["_run_id"] = rid
        analyses.append(a)

    metrics = [
        ("avg_response_chars",    "Avg chars"),
        ("avg_code_chars",        "Avg code chars"),
        ("avg_explanation_chars", "Avg prose chars"),
        ("avg_code_ratio",        "Code ratio"),
        ("avg_explanation_ratio", "Explanation waste"),
        ("timeout_rate",          "Timeout rate"),
        ("truncation_rate",       "Truncation rate"),
        ("chinese_text_rate",     "CJK text rate"),
        ("fence_usage_rate",      "Fence usage"),
    ]

    col_w = 22
    header = f"{'Metric':<{col_w}}" + "".join(f"  {a['_run_id']:<20}" for a in analyses)
    print(header)
    print("-" * len(header))

    for key, label in metrics:
        row = f"{label:<{col_w}}"
        for a in analyses:
            val = a.get(key, 0)
            if isinstance(val, float) and val <= 1.0:
                row += f"  {val:>8.0%}            "
            else:
                row += f"  {val:>8.1f}            "
        print(row)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyse raw model outputs for token waste and quality flags"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--run-id",       default=None)
    group.add_argument("--results-file", default=None,
        help="Path to raw_outputs.jsonl file")
    group.add_argument("--compare",      nargs="+",
        help="Compare token waste across two or more run IDs")
    args = parser.parse_args()

    if args.compare:
        compare_runs(args.compare)
        return

    if args.results_file:
        path   = Path(args.results_file)
        run_id = path.parent.name
    else:
        run_id = args.run_id or _latest_run_id()
        if not run_id:
            print("[analysis] no run found in reports/runs/", file=sys.stderr)
            sys.exit(1)

    analysis = analyse_run(run_id)

    print(f"\nAnalysis: {run_id}")
    print(f"  cases:              {analysis.get('cases_analysed', 0)}")
    print(f"  avg response chars: {analysis.get('avg_response_chars', 0):.0f}")
    print(f"  avg code chars:     {analysis.get('avg_code_chars', 0):.0f}")
    print(f"  avg code ratio:     {analysis.get('avg_code_ratio', 0):.0%}")
    print(f"  explanation waste:  {analysis.get('avg_explanation_ratio', 0):.0%}")
    print(f"  timeout rate:       {analysis.get('timeout_rate', 0):.0%}  ({analysis.get('timeout_count', 0)} cases)")
    print(f"  truncation rate:    {analysis.get('truncation_rate', 0):.0%}  ({analysis.get('truncation_count', 0)} cases)")
    print(f"  CJK text rate:      {analysis.get('chinese_text_rate', 0):.0%}  ({analysis.get('chinese_text_count', 0)} cases)")
    print(f"  fence usage:        {analysis.get('fence_usage_rate', 0):.0%}")
    print(f"  expl. waste signals:{analysis.get('explanation_waste_signal_count', 0)} cases  (>30% prose)")
    print(f"  markdown headings:  {analysis.get('markdown_heading_count', 0)} lines total")
    run_dir = REPORTS_DIR / "runs" / run_id
    print(f"\nReport: {run_dir / 'analysis_report.md'}")


if __name__ == "__main__":
    main()
