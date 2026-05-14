#!/usr/bin/env python3
"""Package semantic_accepted.jsonl into SFT-ready formats.

Outputs (in reports/ by default):
  sft_chatml.jsonl             -- messages[] format (ChatML-like)
  sft_alpaca.jsonl             -- instruction/input/output format
  sft_instruction_output.jsonl -- minimal prompt/completion format
  sft_package_summary.json     -- counts and validation results

Usage:
    python local_ai/training_quality/package_sft_dataset.py
    python local_ai/training_quality/package_sft_dataset.py --strip-code-fences
    python local_ai/training_quality/package_sft_dataset.py \\
        --input  local_ai/training_quality/reports/semantic_accepted.jsonl \\
        --out-dir local_ai/training_quality/reports
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from _common import now_iso


# ── System prompts ─────────────────────────────────────────────────────────

_SYSTEM_CODE = (
    "You are a C programming assistant. "
    "Output exactly one complete C99 program. "
    "Do not explain."
)

_SYSTEM_CONCEPT = (
    "You are a concise C programming tutor. "
    "Explain clearly and briefly."
)


def _system_prompt(rec_type: str) -> str:
    return _SYSTEM_CODE if rec_type == "code_generation" else _SYSTEM_CONCEPT


# ── Output field helpers ────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    """Remove leading/trailing markdown code fences."""
    m = re.search(r"```(?:c|C)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def _output_field(rec: dict, strip_fences: bool) -> str:
    raw = rec.get("output", "").strip()
    if strip_fences and rec.get("type") == "code_generation":
        return _strip_fences(raw)
    return raw


def _meta(rec: dict) -> dict:
    base = {
        "id":     rec.get("id", ""),
        "type":   rec.get("type", ""),
        "source": rec.get("source", ""),
    }
    m = rec.get("metadata") or {}
    for key in ("year", "topic", "difficulty", "points", "exam"):
        if key in m:
            base[key] = m[key]
    return base


# ── Format builders ────────────────────────────────────────────────────────

def _to_chatml(rec: dict, strip_fences: bool) -> dict:
    return {
        "messages": [
            {"role": "system",    "content": _system_prompt(rec["type"])},
            {"role": "user",      "content": rec.get("instruction", "").strip()},
            {"role": "assistant", "content": _output_field(rec, strip_fences)},
        ],
        "metadata": _meta(rec),
    }


def _to_alpaca(rec: dict, strip_fences: bool) -> dict:
    return {
        "instruction": rec.get("instruction", "").strip(),
        "input":       "",
        "output":      _output_field(rec, strip_fences),
        "metadata":    _meta(rec),
    }


def _to_instruction_output(rec: dict, strip_fences: bool) -> dict:
    system = _system_prompt(rec["type"])
    instruction = rec.get("instruction", "").strip()
    prompt = f"{system}\n\n{instruction}" if system else instruction
    return {
        "prompt":     prompt,
        "completion": _output_field(rec, strip_fences),
        "metadata":   _meta(rec),
    }


# ── Validation ─────────────────────────────────────────────────────────────

def _validate_record(rec: dict, strip_fences: bool) -> list[str]:
    issues: list[str] = []
    rec_id = rec.get("id", "?")

    instruction = rec.get("instruction", "").strip()
    output      = _output_field(rec, strip_fences)

    if not instruction:
        issues.append(f"{rec_id}: empty instruction/prompt")
    if not output:
        issues.append(f"{rec_id}: empty output/completion")

    if rec.get("type") == "code_generation" and output:
        has_main  = bool(re.search(r"\bint\s+main\s*\(", output))
        has_fence = "```" in output and not strip_fences
        has_code  = has_main or has_fence
        if not has_code:
            issues.append(f"{rec_id}: code_generation output missing 'int main' and code block")

    return issues


# ── I/O helpers ────────────────────────────────────────────────────────────

def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _write_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _write_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Main ───────────────────────────────────────────────────────────────────

def package(
    input_path: Path,
    out_dir: Path,
    strip_fences: bool,
) -> dict:
    if not input_path.exists():
        print(f"[package] input not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    records = _load_jsonl(input_path)

    by_type: dict[str, int] = {}
    all_issues: list[str]   = []

    chatml_out = []
    alpaca_out = []
    io_out     = []

    for rec in records:
        rec_type = rec.get("type", "unknown")
        by_type[rec_type] = by_type.get(rec_type, 0) + 1

        issues = _validate_record(rec, strip_fences)
        all_issues.extend(issues)

        if issues:
            continue  # skip malformed records

        chatml_out.append(_to_chatml(rec, strip_fences))
        alpaca_out.append(_to_alpaca(rec, strip_fences))
        io_out.append(_to_instruction_output(rec, strip_fences))

    chatml_path = out_dir / "sft_chatml.jsonl"
    alpaca_path = out_dir / "sft_alpaca.jsonl"
    io_path     = out_dir / "sft_instruction_output.jsonl"

    _write_jsonl(chatml_out, chatml_path)
    _write_jsonl(alpaca_out, alpaca_path)
    _write_jsonl(io_out,     io_path)

    summary = {
        "timestamp":    now_iso(),
        "input":        str(input_path),
        "strip_fences": strip_fences,
        "records": {
            "total":   len(records),
            "packaged": len(chatml_out),
            "skipped":  len(records) - len(chatml_out),
            "by_type":  by_type,
        },
        "validation_issues": all_issues,
        "outputs": {
            "chatml":             str(chatml_path),
            "alpaca":             str(alpaca_path),
            "instruction_output": str(io_path),
        },
    }
    _write_json(summary, out_dir / "sft_package_summary.json")
    return summary


def main() -> None:
    default_input = _HERE / "reports" / "semantic_accepted.jsonl"
    default_out   = _HERE / "reports"

    parser = argparse.ArgumentParser(description="Package SFT dataset from semantic_accepted.jsonl")
    parser.add_argument("--input",  default=str(default_input))
    parser.add_argument("--out-dir", default=str(default_out))
    parser.add_argument(
        "--strip-code-fences",
        action="store_true",
        help="Remove ```c ... ``` fences from code_generation outputs",
    )
    args = parser.parse_args()

    summary = package(
        input_path   = Path(args.input),
        out_dir      = Path(args.out_dir),
        strip_fences = args.strip_code_fences,
    )

    r = summary["records"]
    print(f"\nSFT packaging complete")
    print(f"records:          {r['total']}")
    for t, n in sorted(r["by_type"].items()):
        print(f"  {t}: {n}")
    print(f"packaged:         {r['packaged']}")
    if r["skipped"]:
        print(f"skipped:          {r['skipped']}  (validation issues)")
        for issue in summary["validation_issues"]:
            print(f"  - {issue}")
    print(f"outputs written:")
    for fmt, path in summary["outputs"].items():
        print(f"  {fmt}: {Path(path).name}")


if __name__ == "__main__":
    main()
