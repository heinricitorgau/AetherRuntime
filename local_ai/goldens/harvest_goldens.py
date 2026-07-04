#!/usr/bin/env python3
"""Harvest golden candidates from already-verified reference solutions.

Builds golden *candidates* (not approved goldens) from a source JSONL whose
records already carry a compile/runtime-verified reference solution. The output
is written to `goldens/candidates/*.jsonl` for `promote_goldens.py` to
independently re-verify and promote. This never fabricates a solution — it only
re-packages solutions that were already validated — and tags them with their
true provenance tier (`agent_compile_runtime_verified`), awaiting human sign-off.

Default source: the validated generated reference solutions
(`dataset_scaling/reports/accepted_generated_solutions.jsonl`, 40/40 verified).

Usage:
  python local_ai/goldens/harvest_goldens.py
  python local_ai/goldens/harvest_goldens.py --source <path.jsonl> --out <name.jsonl>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_CANDIDATES_DIR = _HERE / "candidates"

_DEFAULT_SOURCE = _LOCAL_AI / "dataset_scaling" / "reports" / "accepted_generated_solutions.jsonl"
_DEFAULT_OUT = "harvested_generated_goldens.jsonl"

_PROVENANCE = "agent_compile_runtime_verified"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _to_candidate(rec: dict[str, Any], source: str) -> dict[str, Any] | None:
    solution = rec.get("reference_solution")
    prompt = rec.get("prompt")
    if not solution or not prompt:
        return None
    # Only harvest records that were actually validated/accepted.
    if not rec.get("validation", {}).get("accepted", False):
        return None
    return {
        "id": rec.get("id"),
        "topic": rec.get("topic", ""),
        "prompt": prompt,
        "verified_solution": solution,
        "sample_input": rec.get("sample_input", ""),
        "expected_output_contains": rec.get("expected_output_contains", []),
        "verified_by": _PROVENANCE,
        "source": source,
        "notes": "Harvested from a validated reference solution; agent compile/runtime "
                 "verified, awaiting human sign-off for the human_verified tier.",
    }


def harvest(source: Path, out_name: str) -> int:
    if not source.exists():
        print(f"[harvest-goldens] ERROR: source not found: {source}", file=sys.stderr)
        return 0
    records = _read_jsonl(source)
    rel_source = str(source).replace("\\", "/")
    candidates = [c for c in (_to_candidate(r, rel_source) for r in records) if c]

    _CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _CANDIDATES_DIR / out_name
    out_path.write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in candidates) + "\n",
        encoding="utf-8",
    )
    print(f"[harvest-goldens] harvested {len(candidates)} candidates from {source.name}")
    print(f"[harvest-goldens] >> {out_path}")
    print("[harvest-goldens] next: python local_ai/goldens/promote_goldens.py")
    return len(candidates)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Harvest golden candidates from verified solutions")
    parser.add_argument("--source", default=str(_DEFAULT_SOURCE), help="Source JSONL with reference_solution records")
    parser.add_argument("--out", default=_DEFAULT_OUT, help="Output candidates filename (under goldens/candidates/)")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    harvest(Path(args.source), args.out)


if __name__ == "__main__":
    main()
