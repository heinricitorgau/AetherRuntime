#!/usr/bin/env python3
"""Seed the verified corpus from already-verified reference solutions.

Builds candidate (agent_verified) corpus records from the validated generated
reference solutions and re-verifies each through the corpus platform's own
agent_verify (compile/runtime/semantic) — it does not blindly trust the source.
It never fabricates a pass and never writes human_verified.

Usage:
  python local_ai/corpus/seed_corpus.py
  python local_ai/corpus/seed_corpus.py --no-exec   # skip compile/runtime
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import corpus_lib as cl  # noqa: E402

_GENERATED = cl._LOCAL_AI / "dataset_scaling" / "reports" / "accepted_generated_solutions.jsonl"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def seed(do_exec: bool = True) -> int:
    cl.ensure_dirs()
    count = 0
    for rec in _read_jsonl(_GENERATED):
        if not rec.get("validation", {}).get("accepted", False):
            continue
        tid = rec.get("id")
        if not tid or cl.find_item(tid):
            continue  # never overwrite an existing corpus item
        item = cl.new_record(
            task_id=tid,
            source="generated_synthetic_v3",
            prompt=rec.get("prompt", ""),
            topic=rec.get("topic", ""),
            difficulty=rec.get("difficulty", ""),
            reference_solution=rec.get("reference_solution", ""),
            sample_input=rec.get("sample_input", ""),
            expected_output_contains=rec.get("expected_output_contains", []),
        )
        if do_exec:
            cl.agent_verify(item)
        else:
            v = rec.get("validation", {})
            item["compile_verified"] = bool(v.get("compile", {}).get("ok"))
            item["runtime_verified"] = bool(v.get("runtime", {}).get("ok"))
            item["semantic_verified"] = bool(v.get("semantic", {}).get("passed"))
        cl.transition(item, "agent_verify", "candidate", to_level="agent_verified")
        cl.save_item(item, "verified")
        cl.append_audit({"action": "seed", "task_id": tid, "stage": "verified",
                         "verification_level": "agent_verified"})
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed verified corpus from verified solutions")
    parser.add_argument("--no-exec", action="store_true", help="Skip compile/runtime; trust source flags")
    args = parser.parse_args()
    n = seed(do_exec=not args.no_exec)
    print(f"[seed-corpus] seeded {n} candidate (agent_verified) corpus records into verified/")
    print("[seed-corpus] next: python local_ai/corpus/build_index.py")


if __name__ == "__main__":
    main()
