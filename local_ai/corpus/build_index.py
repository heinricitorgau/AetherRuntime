#!/usr/bin/env python3
"""Build the corpus index from all stage directories (V10).

Scans raw/ verified/ review/ archive/ and writes a single index of every corpus
item with its stage, status, verification level, and verification flags.

Outputs:
  metadata/corpus_index.json
  metadata/corpus_index.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import corpus_lib as cl  # noqa: E402


def build() -> dict:
    items = cl.all_items()
    rows = [
        {
            "task_id": i.get("task_id"),
            "stage": i.get("_stage"),
            "topic": i.get("topic"),
            "difficulty": i.get("difficulty"),
            "review_status": i.get("review_status"),
            "verification_level": i.get("verification_level"),
            "compile_verified": i.get("compile_verified"),
            "runtime_verified": i.get("runtime_verified"),
            "semantic_verified": i.get("semantic_verified"),
            "reviewer": i.get("reviewer"),
            "source": i.get("source"),
        }
        for i in items
    ]
    rows.sort(key=lambda r: (str(r["stage"]), str(r["task_id"])))
    by_stage: dict[str, int] = {}
    for r in rows:
        by_stage[r["stage"]] = by_stage.get(r["stage"], 0) + 1
    return {
        "timestamp": cl.now(),
        "total": len(rows),
        "by_stage": by_stage,
        "items": rows,
    }


def _markdown(index: dict) -> str:
    lines = ["# Corpus Index", "", f"Generated: `{index['timestamp']}`",
             f"Total items: {index['total']}", ""]
    lines.append("| Stage | Count |")
    lines.append("|-------|------:|")
    for stage, n in sorted(index["by_stage"].items()):
        lines.append(f"| {stage} | {n} |")
    lines.append("")
    lines.append("| Task | Stage | Topic | Diff | Status | Level | C | R | S |")
    lines.append("|------|-------|-------|------|--------|-------|:-:|:-:|:-:|")
    for r in index["items"][:200]:
        c = "✓" if r["compile_verified"] else "✗"
        rr = "✓" if r["runtime_verified"] else "✗"
        s = "✓" if r["semantic_verified"] else "✗"
        lines.append(f"| `{r['task_id']}` | {r['stage']} | {r['topic']} | {r['difficulty']} "
                     f"| {r['review_status']} | {r['verification_level']} | {c} | {rr} | {s} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    cl.ensure_dirs()
    index = build()
    (cl.METADATA_DIR / "corpus_index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (cl.METADATA_DIR / "corpus_index.md").write_text(_markdown(index), encoding="utf-8")
    print(f"[build-index] total={index['total']} by_stage={index['by_stage']}")
    print(f"[build-index] >> {cl.METADATA_DIR / 'corpus_index.md'}")


if __name__ == "__main__":
    main()
