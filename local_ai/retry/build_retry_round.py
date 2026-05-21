#!/usr/bin/env python3
"""Build a retry training round dataset from the failure mining results.

Reads:
    local_ai/retry/retry_curriculum.json               — round definitions
    local_ai/analysis/reports/retry_training_dataset.jsonl  — source failures

Outputs (per round):
    local_ai/retry/rounds/<round>/
        retry_dataset.jsonl          — raw filtered records (all: valid + needs correction)
        retry_chatml.jsonl           — ChatML training records (valid corrected_output only)
        retry_needs_correction.jsonl — records still missing a valid corrected_output
        retry_metadata.json          — round summary (counts, config, timestamp)

Updates:
    local_ai/retry/round_registry.json  — marks round as built

Usage:
    python local_ai/retry/build_retry_round.py --round round_1
    python local_ai/retry/build_retry_round.py --round round_2 --force
    python local_ai/retry/build_retry_round.py --list
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE      = Path(__file__).resolve().parent      # local_ai/retry/
_LOCAL_AI  = _HERE.parent                         # local_ai/
_REPO_ROOT = _LOCAL_AI.parent                     # repo root

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from local_ai.shared.jsonl import read_jsonl, write_jsonl

_CURRICULUM_PATH = _HERE / "retry_curriculum.json"
_REGISTRY_PATH   = _HERE / "round_registry.json"
_ROUNDS_DIR      = _HERE / "rounds"
_RETRY_DATASET   = _LOCAL_AI / "analysis" / "reports" / "retry_training_dataset.jsonl"

_SYSTEM = (
    "You are a C programming repair assistant. "
    "Output exactly one complete C program. "
    "Include all necessary #include directives. "
    "Always include int main(). "
    "No explanations outside the code. "
    "No markdown fences."
)


# ── C validator (mirrors package_retry_dataset.validate_c) ────────────────────

def _count_braces(text: str) -> tuple[int, int]:
    return text.count("{"), text.count("}")


def validate_c(code: str) -> list[str]:
    """Return a list of violation strings; empty list means the code is valid."""
    violations: list[str] = []
    if "#include" not in code:
        violations.append("missing #include")
    if not re.search(r"\bint\s+main\s*\(", code):
        violations.append("missing int main")
    if "return 0" not in code and "return(0)" not in code:
        violations.append("missing return 0")
    opens, closes = _count_braces(code)
    if opens != closes:
        violations.append(f"unbalanced braces ({opens} open, {closes} close)")
    if len(code.strip()) < 50:
        violations.append("code too short (< 50 chars) — likely a fragment")
    return violations


# ── User message builder (mirrors package_retry_dataset._build_user_msg) ─────

def _build_user_msg(record: dict) -> str:
    parts: list[str] = []
    prompt = (record.get("original_prompt") or "").strip()
    if prompt:
        parts.append(prompt)
    parts.append("")
    parts.append(f"[Failure type: {record.get('failure_type', 'unknown')}]")
    hint = (record.get("improvement_hint") or "").strip()
    if hint:
        parts.append(f"[Repair hint: {hint}]")
    expected = (record.get("expected_behavior") or "").strip()
    if expected:
        parts.append(f"[Expected: {expected}]")
    return "\n".join(parts)


# ── Config helpers ────────────────────────────────────────────────────────────

def _load_curriculum() -> dict:
    if not _CURRICULUM_PATH.exists():
        print(f"[build_round] ERROR: curriculum not found: {_CURRICULUM_PATH}", file=sys.stderr)
        sys.exit(1)
    return json.loads(_CURRICULUM_PATH.read_text(encoding="utf-8"))


def _load_registry() -> dict:
    if _REGISTRY_PATH.exists():
        return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    return {"rounds": {}}


def _save_registry(data: dict) -> None:
    _REGISTRY_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── List command ──────────────────────────────────────────────────────────────

def _cmd_list() -> None:
    curriculum = _load_curriculum()
    registry   = _load_registry()
    reg_rounds = registry.get("rounds", {})

    col_w = 12
    foc_w = 42
    print(f"\n{'Round':<{col_w}} {'Focus':<{foc_w}} {'Built':>6} {'Trained':>8} {'Bench':>6} {'Score':>6} Verdict")
    print("-" * 92)
    for name, defn in curriculum.items():
        entry = reg_rounds.get(name, {})
        focus_str   = ", ".join(defn.get("focus", []))
        built       = "yes" if entry.get("built")       else "no"
        trained     = "yes" if entry.get("trained")     else "no"
        benchmarked = "yes" if entry.get("benchmarked") else "no"
        score       = f"{entry['best_score']:.1f}" if entry.get("best_score") is not None else "-"
        verdict     = entry.get("regression") or "-"
        print(f"{name:<{col_w}} {focus_str:<{foc_w}} {built:>6} {trained:>8} {benchmarked:>6} {score:>6} {verdict}")

    print()
    total_valid = sum(
        reg_rounds.get(n, {}).get("records_valid") or 0
        for n in curriculum
    )
    print(f"  curriculum : {_CURRICULUM_PATH}")
    print(f"  registry   : {_REGISTRY_PATH}")
    print(f"  total valid training records across built rounds: {total_valid}")
    print()


# ── Build command ─────────────────────────────────────────────────────────────

def _cmd_build(round_name: str, force: bool) -> None:
    curriculum = _load_curriculum()

    if round_name not in curriculum:
        avail = ", ".join(sorted(curriculum))
        print(f"[build_round] ERROR: unknown round '{round_name}'. Available: {avail}",
              file=sys.stderr)
        sys.exit(1)

    round_def   = curriculum[round_name]
    focus: list[str] = round_def.get("focus", [])
    round_dir   = _ROUNDS_DIR / round_name
    chatml_path = round_dir / "retry_chatml.jsonl"

    if chatml_path.exists() and not force:
        print(f"[build_round] Round '{round_name}' already built at {round_dir}")
        print(f"  Use --force to rebuild.")
        return

    if not _RETRY_DATASET.exists():
        print(f"[build_round] ERROR: source dataset not found: {_RETRY_DATASET}",
              file=sys.stderr)
        print(f"  Run: python local_ai/analysis/generate_retry_dataset.py", file=sys.stderr)
        sys.exit(1)

    print(f"[build_round] Building '{round_name}'")
    print(f"  focus:       {focus}")
    print(f"  description: {round_def.get('description', '')}")

    all_records = read_jsonl(_RETRY_DATASET)
    print(f"[build_round] Loaded {len(all_records)} records from retry_training_dataset.jsonl")

    # Filter by primary failure_type — each record belongs to exactly one round
    matched = [r for r in all_records if r.get("failure_type") in focus]
    print(f"[build_round] {len(matched)} records match focus {focus}")

    if not matched:
        print(f"[build_round] WARNING: no records found for {focus}")
        print(f"  Mine more failures or wait for new benchmark runs to populate this round.")

    chatml_records: list[dict] = []
    needs_correction: list[dict] = []

    for r in matched:
        corrected = (r.get("corrected_output") or "").strip()

        if not corrected:
            needs_correction.append(r)
            continue

        violations = validate_c(corrected)
        if violations:
            task_id = r.get("meta", {}).get("task_id", "?")
            print(f"  [warn] {task_id} — corrected_output invalid: {violations}")
            needs_correction.append(r)
            continue

        meta = r.get("meta", {})
        chatml_records.append({
            "messages": [
                {"role": "system",    "content": _SYSTEM},
                {"role": "user",      "content": _build_user_msg(r)},
                {"role": "assistant", "content": corrected},
            ],
            "metadata": {
                "id":           meta.get("task_id", ""),
                "type":         "retry_code_generation",
                "source":       f"retry_sft_{round_name}",
                "failure_type": r.get("failure_type", ""),
                "round":        round_name,
                "year":         meta.get("year", 0),
                "topic":        meta.get("topic", ""),
                "score_before": meta.get("score", 0),
            },
        })

    # Write round files
    round_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(round_dir / "retry_dataset.jsonl",          matched)
    write_jsonl(round_dir / "retry_chatml.jsonl",           chatml_records)
    write_jsonl(round_dir / "retry_needs_correction.jsonl", needs_correction)

    metadata = {
        "round_name":       round_name,
        "focus_categories": focus,
        "description":      round_def.get("description", ""),
        "source_failures":  len(all_records),
        "selected_records": len(chatml_records),
        "needs_correction": len(needs_correction),
        "epochs":           round_def.get("epochs", 2),
        "lora":             round_def.get("lora", {}),
        "generated_at":     _now(),
    }
    (round_dir / "retry_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Update registry — preserve trained/benchmarked state from previous builds
    registry = _load_registry()
    existing = registry.get("rounds", {}).get(round_name, {})
    registry.setdefault("rounds", {})[round_name] = {
        **existing,
        "focus_categories": focus,
        "built":            True,
        "built_at":         _now(),
        "dataset_path":     str(chatml_path),
        "records_total":    len(matched),
        "records_valid":    len(chatml_records),
    }
    _save_registry(registry)

    # Summary
    print(f"\n[build_round] Round '{round_name}' built:")
    print(f"  retry_dataset.jsonl:          {len(matched)} records")
    print(f"  retry_chatml.jsonl:           {len(chatml_records)} training records")
    print(f"  retry_needs_correction.jsonl: {len(needs_correction)} records")
    print(f"  retry_metadata.json:          written")
    print(f"  round_registry.json:          updated  (built=True)")
    print(f"  Output: {round_dir}")

    if needs_correction:
        nc = len(needs_correction)
        print(f"\nNext step — generate corrected_output for {nc} record(s):")
        print(f"  python local_ai/analysis/generate_retry_answers.py "
              f"--round {round_name} --ollama-direct")
        print(f"  python local_ai/retry/build_retry_round.py --round {round_name} --force")

    if chatml_records:
        print(f"\nNext step — train on {len(chatml_records)} record(s):")
        print(f"  python local_ai/sft/train_lora.py --round {round_name}")
    elif not needs_correction:
        print(f"\n[build_round] WARNING: 0 valid chatml records and 0 failures — "
              f"nothing to train on for {round_name}.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build a retry curriculum training round",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  Build round_1:             python local_ai/retry/build_retry_round.py --round round_1\n"
            "  Rebuild with force:        python local_ai/retry/build_retry_round.py --round round_1 --force\n"
            "  Show all rounds' status:   python local_ai/retry/build_retry_round.py --list\n"
        ),
    )
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--round", metavar="NAME",
                     help="Round name to build (e.g. round_1, round_2)")
    grp.add_argument("--list", action="store_true",
                     help="List all rounds and their current build/train/benchmark status")
    p.add_argument("--force", action="store_true",
                   help="Rebuild the round even if it already exists")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    if args.list:
        _cmd_list()
    else:
        _cmd_build(args.round, args.force)


if __name__ == "__main__":
    main()
