"""package_retry_dataset.py — package retry training records into SFT ChatML format.

Reads:
    local_ai/analysis/reports/retry_training_dataset.jsonl

Writes:
    local_ai/analysis/reports/retry_sft_chatml.jsonl   (records with corrected_output)
    local_ai/analysis/reports/retry_needs_correction.jsonl  (records missing corrected_output)

Only records that have a validated corrected_output are written to retry_sft_chatml.jsonl.
Records without corrected_output are written to retry_needs_correction.jsonl for human/model
correction via generate_retry_answers.py.

ChatML format is identical to local_ai/training_quality/reports/sft_chatml.jsonl:
    {"messages": [system, user, assistant], "metadata": {...}}
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
if str(_LOCAL_AI.parent) not in sys.path:
    sys.path.insert(0, str(_LOCAL_AI.parent))

from local_ai.shared.jsonl import read_jsonl, write_jsonl

RETRY_DATASET  = _HERE / "reports" / "retry_training_dataset.jsonl"
OUTPUT_CHATML  = _HERE / "reports" / "retry_sft_chatml.jsonl"
OUTPUT_NEEDS   = _HERE / "reports" / "retry_needs_correction.jsonl"

_SYSTEM = (
    "You are a C programming repair assistant. "
    "Output exactly one complete C program. "
    "Include all necessary #include directives. "
    "Always include int main(). "
    "No explanations outside the code. "
    "No markdown fences."
)


def _load_verified_goldens(goldens_dir: Path) -> dict[str, str]:
    """Load compile/runtime-verified golden repairs by task id."""
    goldens: dict[str, str] = {}
    if not goldens_dir.exists():
        return goldens

    verified_ids: set[str] = set()
    for manifest_path in sorted(goldens_dir.glob("*/*_manifest.json")):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for entry in data.get("goldens", []):
            if entry.get("compile_verified") and entry.get("runtime_verified"):
                verified_ids.add(str(entry.get("id", "")))

    candidates = list(goldens_dir.glob("*_golden.c"))
    candidates.extend(goldens_dir.glob("*/*_golden.c"))
    for c_file in sorted(candidates):
        file_id = c_file.stem.replace("_golden", "")
        if verified_ids and file_id not in verified_ids:
            continue
        try:
            goldens[file_id] = c_file.read_text(encoding="utf-8")
        except Exception:
            pass
    return goldens


# ── validator ─────────────────────────────────────────────────────────────────

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
    # Must not be just the bad_output (check it's not a tiny fragment)
    if len(code.strip()) < 50:
        violations.append("code too short (< 50 chars) -- likely a fragment")
    return violations


def _validate_c_strict(code: str) -> list[str]:
    """Stricter validator for geometry rounds: also requires scanf and printf."""
    violations = validate_c(code)
    if "scanf" not in code:
        violations.append("missing scanf (geometry tasks require reading float/int input)")
    if "printf" not in code:
        violations.append("missing printf (geometry tasks require formatted output)")
    return violations


# ── user message builder ──────────────────────────────────────────────────────

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


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Package retry training records into SFT ChatML format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  Global (legacy):          python local_ai/analysis/package_retry_dataset.py\n"
            "  Round-local (geometry):   python local_ai/analysis/package_retry_dataset.py "
            "--round round_geometry_v1\n"
        ),
    )
    p.add_argument("--round", default=None, metavar="NAME",
                   help="Retry curriculum round. Reads from "
                        "local_ai/retry/rounds/<round>/retry_dataset.jsonl and writes "
                        "retry_chatml.jsonl to the same directory.")
    return p.parse_args()


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()

    # ── Round-local mode ──────────────────────────────────────────────────────
    if args.round:
        _retry_dir  = Path(__file__).resolve().parent.parent / "retry"
        _goldens_dir = Path(__file__).resolve().parent.parent / "goldens"
        round_dir   = _retry_dir / "rounds" / args.round
        source_path = round_dir / "retry_dataset.jsonl"
        chatml_path = round_dir / "retry_chatml.jsonl"
        needs_path  = round_dir / "retry_needs_correction.jsonl"

        if not source_path.exists():
            print(f"[package] ERROR: {source_path} not found.")
            print(f"  Run: python local_ai/retry/build_retry_round.py --round {args.round}")
            sys.exit(1)

        # Detect geometry / strict validator from curriculum
        curriculum_path = _retry_dir / "retry_curriculum.json"
        use_strict      = False
        if curriculum_path.exists():
            curriculum = json.loads(curriculum_path.read_text(encoding="utf-8"))
            round_def  = curriculum.get(args.round, {})
            use_strict = bool(round_def.get("target_topics"))

        validator = _validate_c_strict if use_strict else validate_c

        # ── Load golden files ─────────────────────────────────────────────────
        goldens = _load_verified_goldens(_goldens_dir)
        if goldens:
            print(f"[package] Loaded {len(goldens)} verified golden file(s): "
                  f"{sorted(goldens.keys())}")

        records = read_jsonl(source_path)
        print(f"[package] --round {args.round}: loaded {len(records)} records")
        if use_strict:
            print(f"[package] Strict validator active (requires scanf + printf)")

        chatml_records: list[dict] = []
        needs_correction: list[dict] = []
        golden_used = 0

        for r in records:
            task_id = r.get("meta", {}).get("task_id", "")

            # Prefer golden over AI-generated corrected_output
            golden_code = goldens.get(task_id)
            if golden_code:
                corrected = golden_code
                print(f"  [golden] {task_id} -- using verified golden repair")
                golden_used += 1
            else:
                corrected = (r.get("corrected_output") or "").strip()

            if not corrected:
                needs_correction.append(r)
                continue
            violations = validator(corrected)
            if violations:
                source_label = "golden" if golden_code else "corrected_output"
                print(f"  [skip] {task_id} -- {source_label} invalid: {violations}")
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
                    "source":       f"retry_sft_{args.round}",
                    "failure_type": r.get("failure_type", ""),
                    "round":        args.round,
                    "year":         meta.get("year", 0),
                    "topic":        meta.get("topic", ""),
                    "score_before": meta.get("score", 0),
                    "golden":       bool(golden_code),
                },
            })

        round_dir.mkdir(parents=True, exist_ok=True)
        write_jsonl(chatml_path, chatml_records)
        write_jsonl(needs_path,  needs_correction)

        print(f"\n[package] Round '{args.round}' packaged:")
        print(f"  retry_chatml.jsonl:           {len(chatml_records)} training records")
        print(f"  retry_needs_correction.jsonl: {len(needs_correction)} records")
        if golden_used:
            print(f"  golden repairs used:          {golden_used}")
        print(f"  Output: {round_dir}")

        if needs_correction:
            print(f"\n  {len(needs_correction)} record(s) still need corrected_output.")
            print(f"  Run: python local_ai/analysis/generate_retry_answers.py "
                  f"--round {args.round} --ollama-direct")
        if chatml_records:
            print(f"\nNext step:")
            print(f"  python local_ai/sft/train_lora.py --round {args.round}")
        return

    # ── Global (legacy) mode ──────────────────────────────────────────────────
    if not RETRY_DATASET.exists():
        print(f"[package] ERROR: {RETRY_DATASET} not found. Run generate_retry_dataset.py first.")
        sys.exit(1)

    records = read_jsonl(RETRY_DATASET)
    print(f"[package] Loaded {len(records)} retry records")

    chatml_records_g: list[dict] = []
    needs_correction_g: list[dict] = []

    for r in records:
        corrected = (r.get("corrected_output") or "").strip()

        if not corrected:
            needs_correction_g.append(r)
            continue

        violations = validate_c(corrected)
        if violations:
            print(f"  [skip] {r.get('meta', {}).get('task_id', '?')} -- "
                  f"corrected_output invalid: {violations}")
            needs_correction_g.append(r)
            continue

        user_msg = _build_user_msg(r)
        meta = r.get("meta", {})

        chatml_records_g.append({
            "messages": [
                {"role": "system",    "content": _SYSTEM},
                {"role": "user",      "content": user_msg},
                {"role": "assistant", "content": corrected},
            ],
            "metadata": {
                "id":           meta.get("task_id", ""),
                "type":         "retry_code_generation",
                "source":       "retry_sft",
                "failure_type": r.get("failure_type", ""),
                "year":         meta.get("year", 0),
                "topic":        meta.get("topic", ""),
                "score_before": meta.get("score", 0),
            },
        })

    OUTPUT_CHATML.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUTPUT_CHATML, chatml_records_g)
    write_jsonl(OUTPUT_NEEDS,  needs_correction_g)

    print(f"\n[package] Results:")
    print(f"  retry_sft_chatml.jsonl      : {len(chatml_records_g)} records")
    print(f"  retry_needs_correction.jsonl: {len(needs_correction_g)} records")
    print(f"  Output : {OUTPUT_CHATML}")
    print(f"  Needs correction: {OUTPUT_NEEDS}")

    if needs_correction_g:
        print(f"\n[package] Run generate_retry_answers.py to produce corrected_output for "
              f"{len(needs_correction_g)} remaining records, then re-run this script.")


if __name__ == "__main__":
    main()
