#!/usr/bin/env python3
"""Corpus quality dashboard (V10).

Statistics over the corpus: counts, topic/difficulty distribution, human-verified
and golden ratios, compile/runtime/semantic pass rates, and topic/difficulty
coverage. Read-only; reuses the existing benchmark dataset only to compute topic
coverage of the eval set. Does not run models or change scoring.

Outputs:
  reports/corpus_dashboard.json
  reports/corpus_dashboard.md
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import corpus_lib as cl  # noqa: E402


def _ratio(n: int, d: int) -> float:
    return round(n / d, 3) if d else 0.0


def build() -> dict:
    # The "corpus" for quality stats = verified/ stage (excludes raw + archive).
    items = list(cl.iter_items("verified"))
    total = len(items)

    by_topic = Counter(i.get("topic") or "unknown" for i in items)
    by_difficulty = Counter(i.get("difficulty") or "unknown" for i in items)
    by_level = Counter(i.get("verification_level") or "unverified" for i in items)

    human = by_level.get("human_verified", 0)
    golden = by_level.get("golden", 0)
    agent = by_level.get("agent_verified", 0)

    compile_pass = sum(1 for i in items if i.get("compile_verified"))
    runtime_pass = sum(1 for i in items if i.get("runtime_verified"))
    semantic_pass = sum(1 for i in items if i.get("semantic_verified"))

    raw_count = sum(1 for _ in cl.iter_items("raw"))
    review_count = sum(1 for _ in cl.iter_items("review"))
    archive_count = sum(1 for _ in cl.iter_items("archive"))

    return {
        "timestamp": cl.now(),
        "corpus_size": total,
        "stage_counts": {
            "raw": raw_count, "verified": total,
            "review": review_count, "archive": archive_count,
        },
        "by_topic": dict(sorted(by_topic.items())),
        "by_difficulty": dict(sorted(by_difficulty.items())),
        "by_verification_level": dict(by_level),
        "human_verified_ratio": _ratio(human, total),
        "golden_ratio": _ratio(golden, total),
        "agent_verified_ratio": _ratio(agent, total),
        "compile_pass_rate": _ratio(compile_pass, total),
        "runtime_pass_rate": _ratio(runtime_pass, total),
        "semantic_pass_rate": _ratio(semantic_pass, total),
        "topic_coverage": sorted(by_topic),
        "difficulty_coverage": sorted(by_difficulty),
    }


def _markdown(d: dict) -> str:
    lines = ["# Corpus Dashboard", "", f"Generated: `{d['timestamp']}`",
             f"Corpus size (verified stage): **{d['corpus_size']}**", ""]
    lines.append("## Verification Quality")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|------:|")
    lines.append(f"| human_verified_ratio | {d['human_verified_ratio']} |")
    lines.append(f"| golden_ratio | {d['golden_ratio']} |")
    lines.append(f"| agent_verified_ratio | {d['agent_verified_ratio']} |")
    lines.append(f"| compile_pass_rate | {d['compile_pass_rate']} |")
    lines.append(f"| runtime_pass_rate | {d['runtime_pass_rate']} |")
    lines.append(f"| semantic_pass_rate | {d['semantic_pass_rate']} |")
    lines.append("")
    lines.append("## Stage Counts")
    lines.append("")
    for k, v in d["stage_counts"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Topic Coverage")
    lines.append("")
    lines.append("| Topic | Count |")
    lines.append("|-------|------:|")
    for t, n in d["by_topic"].items():
        lines.append(f"| {t} | {n} |")
    lines.append("")
    lines.append("## Difficulty Coverage")
    lines.append("")
    lines.append("| Difficulty | Count |")
    lines.append("|------------|------:|")
    for t, n in d["by_difficulty"].items():
        lines.append(f"| {t} | {n} |")
    lines.append("")
    lines.append("## Verification Levels")
    lines.append("")
    for k, v in d["by_verification_level"].items():
        lines.append(f"- {k}: {v}")
    return "\n".join(lines) + "\n"


def main() -> None:
    cl.ensure_dirs()
    d = build()
    (cl.REPORTS_DIR / "corpus_dashboard.json").write_text(
        json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (cl.REPORTS_DIR / "corpus_dashboard.md").write_text(_markdown(d), encoding="utf-8")
    print(f"[corpus-dashboard] size={d['corpus_size']} "
          f"human_ratio={d['human_verified_ratio']} golden_ratio={d['golden_ratio']}")
    print(f"[corpus-dashboard] compile={d['compile_pass_rate']} runtime={d['runtime_pass_rate']} "
          f"semantic={d['semantic_pass_rate']}")
    print(f"[corpus-dashboard] >> {cl.REPORTS_DIR / 'corpus_dashboard.md'}")


if __name__ == "__main__":
    main()
