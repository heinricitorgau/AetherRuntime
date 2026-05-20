#!/usr/bin/env python3
"""Training data preparation for local C programming AI.

Combines two data sources:
  1. eval_cases/c_exam/*.json  — structured question prompts (19 cases)
  2. ingest/output/*.chunks.json — PDF-derived text/question chunks (25 chunks)

Outputs (in local_ai/ingest/output/training/):
  code_generation.jsonl   — eval cases as instruction-tuning examples
  pdf_chunks.jsonl        — PDF chunks as RAG / reading context
  combined.jsonl          — merged, ready for fine-tuning
  summary.json            — statistics

Each record carries BOTH Alpaca format (instruction/input/output) AND
chat/messages format so it works with any fine-tuning framework.

The `output` field is empty by default.  Fill it with:
  --fill-answers DIR      reads DIR/<case_id>.c and inserts as output

Usage:
    python local_ai/ingest/prepare_training.py
    python local_ai/ingest/prepare_training.py --fill-answers path/to/answers/
    python local_ai/ingest/prepare_training.py --stats
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


# ── Paths ──────────────────────────────────────────────────────────────────

def _ingest_dir() -> Path:
    return Path(__file__).resolve().parent


def _eval_cases_dir() -> Path:
    return _ingest_dir().parent / "eval_cases" / "c_exam"


def _chunks_dir() -> Path:
    return _ingest_dir() / "output"


def _training_dir() -> Path:
    d = _ingest_dir() / "output" / "training"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── System prompt ──────────────────────────────────────────────────────────

_SYSTEM = (
    "You are a C programming assistant. "
    "When given a programming problem, output exactly one complete, compilable C99 program. "
    "Include all necessary #include directives and a main() function. "
    "Do not add explanations outside the code."
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _build_instruction(case: dict[str, Any]) -> str:
    """Build a clean natural-language instruction from an eval case."""
    parts = [case.get("prompt", "").strip()]

    features = case.get("required_features", [])
    if features:
        parts.append("\nRequired features:")
        for f in features:
            parts.append(f"  - {f}")

    sample = str(case.get("sample_input", "")).strip()
    if sample:
        parts.append(f"\nSample input:\n{sample}")

    behavior = case.get("expected_behavior", {})
    contains = behavior.get("output_contains", [])
    if contains:
        parts.append(f"\nExpected output contains: {', '.join(str(c) for c in contains)}")

    return "\n".join(parts)


def _alpaca_record(
    record_id: str,
    instruction: str,
    output: str,
    meta: dict[str, Any],
    source: str,
    record_type: str,
) -> dict[str, Any]:
    return {
        "id": record_id,
        "type": record_type,
        "source": source,
        "instruction": instruction,
        "input": "",
        "output": output,
        "messages": [
            {"role": "system",    "content": _SYSTEM},
            {"role": "user",      "content": instruction},
            {"role": "assistant", "content": output},
        ],
        "metadata": meta,
    }


# ── Source 1: eval cases ───────────────────────────────────────────────────

def load_eval_cases(
    answers_dir: Path | None = None,
    cases_dir: Path | None = None,
) -> list[dict[str, Any]]:
    cases_dir = cases_dir or _eval_cases_dir()
    if not cases_dir.exists():
        print(f"Warning: eval cases dir not found: {cases_dir}", file=sys.stderr)
        return []

    records: list[dict[str, Any]] = []
    for path in sorted(cases_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  skip {path.name}: {exc}", file=sys.stderr)
            continue
        cases = payload if isinstance(payload, list) else [payload]

        for case in cases:
            case_id = case.get("id", path.stem)
            instruction = _build_instruction(case)

            # Try to load reference answer (.c file) if answers_dir is given
            output = ""
            if answers_dir:
                answer_path = answers_dir / f"{case_id}.c"
                if answer_path.exists():
                    code = answer_path.read_text(encoding="utf-8", errors="replace").strip()
                    output = f"```c\n{code}\n```"

            meta = {
                "year":       case.get("year"),
                "exam":       case.get("exam"),
                "topic":      case.get("topic"),
                "difficulty": case.get("difficulty"),
                "points":     case.get("points"),
                "source_file": path.name,
            }

            records.append(_alpaca_record(
                record_id=case_id,
                instruction=instruction,
                output=output,
                meta=meta,
                source="eval_case",
                record_type="code_generation",
            ))

    return records


# ── Source 2: PDF chunks ───────────────────────────────────────────────────

def load_pdf_chunks(chunks_dir: Path | None = None) -> list[dict[str, Any]]:
    chunks_dir = chunks_dir or _chunks_dir()
    records: list[dict[str, Any]] = []

    for path in sorted(chunks_dir.glob("*.chunks.json")):
        try:
            chunks = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  skip {path.name}: {exc}", file=sys.stderr)
            continue

        year_m = re.search(r"(\d{4})", path.stem)
        year = int(year_m.group(1)) if year_m else None

        for chunk in chunks:
            ctype = chunk.get("content_type", "text")
            content = chunk.get("content", "").strip()
            section = chunk.get("section", "")
            if not content:
                continue

            if ctype == "code":
                instruction = (
                    f"Explain what the following C code does"
                    + (f" (from section: {section})" if section else "")
                    + ":\n\n```c\n" + content + "\n```"
                )
                record_type = "code_explanation"
            elif ctype == "question":
                instruction = _sanitize_question(content)
                record_type = "code_generation"
            else:
                instruction = (
                    "Summarize the following C programming concept"
                    + (f" from section '{section}'" if section else "")
                    + f":\n\n{content}"
                )
                record_type = "concept_summary"

            meta = {
                "year":         year,
                "section":      section,
                "content_type": ctype,
                "source_file":  chunk.get("source_file", path.name),
                "chunk_id":     chunk.get("id", ""),
                "estimated_tokens": chunk.get("estimated_tokens", 0),
            }

            records.append(_alpaca_record(
                record_id=chunk.get("id", f"chunk_{len(records):04d}"),
                instruction=instruction,
                output="",
                meta=meta,
                source="pdf_chunk",
                record_type=record_type,
            ))

    return records


def _sanitize_question(content: str) -> str:
    """Strip leading question number from PDF chunk content for use as instruction."""
    content = re.sub(r"^\d+\.\s*", "", content.strip())
    if not content.endswith("?") and not content.lower().startswith("write"):
        content = "Write a C program for the following:\n\n" + content
    return content


# ── Output ─────────────────────────────────────────────────────────────────

def _write_jsonl(records: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _print_stats(
    eval_records: list[dict[str, Any]],
    chunk_records: list[dict[str, Any]],
) -> None:
    all_records = eval_records + chunk_records

    answered = sum(1 for r in eval_records if r.get("output"))
    years = sorted({r["metadata"].get("year") for r in all_records if r["metadata"].get("year")})

    by_type: dict[str, int] = {}
    for r in all_records:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1

    print("\n── Training data summary ──────────────────────────────────")
    print(f"  Eval cases (code_generation):  {len(eval_records):>4}")
    print(f"    with reference answers:       {answered:>4}")
    print(f"    without answers (to fill):    {len(eval_records) - answered:>4}")
    print(f"  PDF chunks:                    {len(chunk_records):>4}")
    print(f"  Total records:                 {len(all_records):>4}")
    print(f"  Years covered: {years}")
    print(f"  By type:")
    for t, n in sorted(by_type.items()):
        print(f"    {t:<22} {n}")
    print()


# ── Main ───────────────────────────────────────────────────────────────────

def prepare_training(
    answers_dir: Path | None = None,
    eval_cases_dir: Path | None = None,
    chunks_dir: Path | None = None,
    output_dir: Path | None = None,
    stats_only: bool = False,
) -> dict[str, Any]:
    print("Loading eval cases...", file=sys.stderr)
    eval_records = load_eval_cases(answers_dir, eval_cases_dir)
    print(f"  {len(eval_records)} eval cases loaded", file=sys.stderr)

    print("Loading PDF chunks...", file=sys.stderr)
    chunk_records = load_pdf_chunks(chunks_dir)
    print(f"  {len(chunk_records)} chunks loaded", file=sys.stderr)

    _print_stats(eval_records, chunk_records)

    if stats_only:
        return {"eval": len(eval_records), "chunks": len(chunk_records)}

    out_dir = output_dir or _training_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    code_gen_path = out_dir / "code_generation.jsonl"
    _write_jsonl(eval_records, code_gen_path)
    print(f"  wrote {code_gen_path}")

    pdf_path = out_dir / "pdf_chunks.jsonl"
    _write_jsonl(chunk_records, pdf_path)
    print(f"  wrote {pdf_path}")

    combined = eval_records + chunk_records
    combined_path = out_dir / "combined.jsonl"
    _write_jsonl(combined, combined_path)
    print(f"  wrote {combined_path} ({len(combined)} records total)")

    summary = {
        "total_records": len(combined),
        "eval_cases": len(eval_records),
        "pdf_chunks": len(chunk_records),
        "answered": sum(1 for r in eval_records if r.get("output")),
        "output_dir": str(out_dir),
        "files": {
            "code_generation": str(code_gen_path),
            "pdf_chunks": str(pdf_path),
            "combined": str(combined_path),
        },
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  wrote {out_dir / 'summary.json'}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare training data from eval cases and PDF chunks"
    )
    parser.add_argument(
        "--fill-answers",
        metavar="DIR",
        help="Directory containing <case_id>.c reference answer files",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print statistics only, do not write files",
    )
    parser.add_argument(
        "--eval-cases-dir",
        help="Optional eval-case directory (default: eval_cases/c_exam)",
    )
    parser.add_argument(
        "--chunks-dir",
        help="Optional chunks directory (default: ingest/output)",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional training output directory (default: ingest/output/training)",
    )
    args = parser.parse_args()

    answers_dir = Path(args.fill_answers) if args.fill_answers else None
    result = prepare_training(
        answers_dir=answers_dir,
        eval_cases_dir=Path(args.eval_cases_dir) if args.eval_cases_dir else None,
        chunks_dir=Path(args.chunks_dir) if args.chunks_dir else None,
        output_dir=Path(args.output_dir) if args.output_dir else None,
        stats_only=args.stats,
    )
    if not args.stats:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
