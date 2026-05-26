#!/usr/bin/env python3
"""Build an isolated topic-specific generated candidate corpus."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPORTS_DIR = _HERE / "reports"
_TOPICS_DIR = _HERE / "topics"
_SOURCE_SFT = _REPORTS_DIR / "generated_sft_chatml.jsonl"
_SOURCE_BENCHMARK = _REPORTS_DIR / "generated_benchmark_cases.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                rows.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON in {path} line {line_no}: {exc}") from exc
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def _topic_from_sft(row: dict[str, Any]) -> str:
    return str((row.get("metadata") or {}).get("topic") or "")


def _topic_from_benchmark(row: dict[str, Any]) -> str:
    return str(row.get("topic") or (row.get("metadata") or {}).get("topic") or "")


def build_topic_candidate(topic: str, name: str) -> dict[str, Any]:
    if not topic.strip():
        raise ValueError("--topic must be non-empty")
    if not name.strip():
        raise ValueError("--name must be non-empty")
    if not _SOURCE_SFT.exists():
        raise FileNotFoundError(f"missing source SFT file: {_SOURCE_SFT}")
    if not _SOURCE_BENCHMARK.exists():
        raise FileNotFoundError(f"missing source benchmark file: {_SOURCE_BENCHMARK}")

    sft_rows = [row for row in _read_jsonl(_SOURCE_SFT) if _topic_from_sft(row) == topic]
    benchmark_rows = [row for row in _read_jsonl(_SOURCE_BENCHMARK) if _topic_from_benchmark(row) == topic]
    if not sft_rows:
        raise ValueError(f"no SFT records found for topic={topic}")
    if not benchmark_rows:
        raise ValueError(f"no benchmark records found for topic={topic}")

    out_dir = _TOPICS_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    sft_path = out_dir / "sft_chatml.jsonl"
    benchmark_path = out_dir / "benchmark_cases.jsonl"
    metadata_path = out_dir / "metadata.json"

    _write_jsonl(sft_path, sft_rows)
    _write_jsonl(benchmark_path, benchmark_rows)

    metadata = {
        "name": name,
        "topic": topic,
        "record_count": len(sft_rows),
        "benchmark_count": len(benchmark_rows),
        "source_dataset": str(_SOURCE_SFT),
        "source_benchmark": str(_SOURCE_BENCHMARK),
        "sft_path": str(sft_path),
        "benchmark_path": str(benchmark_path),
        "generated_at": _now(),
        "isolation": True,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return metadata


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build topic-specific generated candidate corpus")
    parser.add_argument("--topic", required=True, help="Topic to extract, e.g. pattern_generation")
    parser.add_argument("--name", required=True, help="Output candidate name")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        metadata = build_topic_candidate(args.topic, args.name)
    except Exception as exc:
        print(f"[build-topic-candidate] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print(
        "[build-topic-candidate] "
        f"name={metadata['name']} topic={metadata['topic']} "
        f"records={metadata['record_count']} benchmark={metadata['benchmark_count']}"
    )
    print(f"[build-topic-candidate] output >> {_TOPICS_DIR / args.name}")


if __name__ == "__main__":
    main()
