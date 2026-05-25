#!/usr/bin/env python3
"""Generate deterministic synthetic C task specifications for dataset scaling."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPORT_DIR = _HERE / "reports"
_OUT_PATH = _REPORT_DIR / "generated_tasks.jsonl"

TOPICS = ("series_calculation", "pattern_generation", "geometry", "game_simulation")
DIFFICULTIES = ("easy", "medium", "hard")


def _series_task(index: int, difficulty: str, rng: random.Random) -> dict[str, Any]:
    variants = [
        ("alternating rational sum", "(-1)^(i+1) * (2*i+1) / (i*i+1)", "result"),
        ("factorial ratio sum", "i! / (i+1)", "sum"),
        ("square denominator series", "(3*i-1) / (i*i+i+1)", "result"),
        ("harmonic-style signed sum", "(-1)^i * i / (2*i+1)", "result"),
    ]
    name, formula, token = variants[index % len(variants)]
    n = 5 + index
    return {
        "id": f"synthetic_v3_series_calculation_{index + 1:03d}",
        "topic": "series_calculation",
        "difficulty": difficulty,
        "prompt": (
            f"Task S{index + 1}: Write a complete C99 program that reads integer n and computes a {name}. "
            f"Use the formula term_i = {formula} for i from 1 to n. "
            f"Assume 1 <= n <= {n + 5}. Print the final sum with a label and 3 decimal places."
        ),
        "required_features": [
            "read integer n",
            "use a loop over i",
            "use double precision",
            "print result with printf",
        ],
        "sample_input": f"{n}\n",
        "expected_output_contains": [token],
        "checker_rules": {
            "compile_required": True,
            "runtime_required": True,
            "keywords": ["scanf", "printf", "for", "double"],
            "timeout_seconds": 5,
        },
    }


def _pattern_task(index: int, difficulty: str, rng: random.Random) -> dict[str, Any]:
    variants = [
        ("left aligned increasing number triangle", ["1", "22", "333"]),
        ("centered descending digit pyramid", ["4444", "333", "22"]),
        ("diamond made from repeated row numbers", ["1", "22", "333", "22", "1"]),
        ("hollow square border using stars", ["***", "*    *"]),
    ]
    name, tokens = variants[index % len(variants)]
    n = 3 + (index % 4)
    return {
        "id": f"synthetic_v3_pattern_generation_{index + 1:03d}",
        "topic": "pattern_generation",
        "difficulty": difficulty,
        "prompt": (
            f"Task P{index + 1}: Write a complete C99 program that reads integer n and prints a {name}. "
            f"The sample uses n={n}. Use nested loops rather than hard-coded output."
        ),
        "required_features": [
            "read integer n",
            "use nested loops",
            "print each row with printf",
            "handle n from 1 to 9",
        ],
        "sample_input": f"{n}\n",
        "expected_output_contains": tokens[:3],
        "checker_rules": {
            "compile_required": True,
            "runtime_required": True,
            "keywords": ["scanf", "printf", "for"],
            "timeout_seconds": 5,
        },
    }


def _geometry_task(index: int, difficulty: str, rng: random.Random) -> dict[str, Any]:
    variants = [
        ("distance between two points and midpoint", "0 0 3 4\n", ["distance", "5.000"]),
        ("triangle perimeter and area using Heron's formula", "0 0 0 3 4 0\n", ["area", "6.000"]),
        ("line equation through two points", "0 0 4 3\n", ["line", "x", "y"]),
        ("collinearity check for three points", "0 0 1 1 2 2\n", ["collinear"]),
    ]
    name, sample_input, tokens = variants[index % len(variants)]
    keywords = ["scanf", "printf", "sqrt"]
    if "collinearity" in name:
        keywords = ["scanf", "printf"]
    return {
        "id": f"synthetic_v3_geometry_{index + 1:03d}",
        "topic": "geometry",
        "difficulty": difficulty,
        "prompt": (
            f"Task G{index + 1}: Write a complete C99 program for a geometry task: {name}. "
            f"The validator sample input is {sample_input.strip()!r}. "
            "Read coordinates from stdin and print labeled numeric results."
        ),
        "required_features": [
            "read coordinate values",
            "use functions for geometry calculations",
            "print labeled output",
            "handle degenerate cases when relevant",
        ],
        "sample_input": sample_input,
        "expected_output_contains": tokens,
        "checker_rules": {
            "compile_required": True,
            "runtime_required": True,
            "keywords": keywords,
            "timeout_seconds": 5,
        },
    }


def _game_task(index: int, difficulty: str, rng: random.Random) -> dict[str, Any]:
    variants = [
        ("even or odd hidden number game", "2\nO\n5\nE\n", ["Numbers", "Pick", "points"]),
        ("number guessing game from 1 to 10", "5\nN\n", ["Guess", "number", "points"]),
        ("rock paper scissors score game", "3\n1\n2\n3\n", ["choice", "score", "winner"]),
        ("tug war random choice game", "3\n1\n1\n1\n", ["Tug", "Enter", "winner"]),
    ]
    name, sample_input, tokens = variants[index % len(variants)]
    return {
        "id": f"synthetic_v3_game_simulation_{index + 1:03d}",
        "topic": "game_simulation",
        "difficulty": difficulty,
        "prompt": (
            f"Task GAME{index + 1}: Write a complete C99 program that simulates a {name}. "
            "Use arrays or state variables, read player input, update score or state, and print progress."
        ),
        "required_features": [
            "use srand or deterministic random setup",
            "read player input with scanf",
            "track score or game state",
            "print progress and final result",
        ],
        "sample_input": sample_input,
        "expected_output_contains": tokens,
        "checker_rules": {
            "compile_required": True,
            "runtime_required": True,
            "keywords": ["scanf", "printf", "rand", "srand"],
            "timeout_seconds": 5,
        },
    }


GENERATORS = {
    "series_calculation": _series_task,
    "pattern_generation": _pattern_task,
    "geometry": _geometry_task,
    "game_simulation": _game_task,
}


def generate_tasks(count_per_topic: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    tasks: list[dict[str, Any]] = []
    for topic in TOPICS:
        generator = GENERATORS[topic]
        for index in range(count_per_topic):
            difficulty = DIFFICULTIES[(index + rng.randrange(len(DIFFICULTIES))) % len(DIFFICULTIES)]
            tasks.append(generator(index, difficulty, rng))
    return tasks


def write_jsonl(path: Path, tasks: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for task in tasks:
            fh.write(json.dumps(task, ensure_ascii=False) + "\n")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic task specs")
    parser.add_argument("--count-per-topic", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=str(_OUT_PATH))
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.count_per_topic < 1:
        raise SystemExit("--count-per-topic must be >= 1")
    tasks = generate_tasks(args.count_per_topic, args.seed)
    write_jsonl(Path(args.out), tasks)
    print(f"[generate-tasks] wrote {len(tasks)} task specs")
    print(f"[generate-tasks] output >> {Path(args.out)}")


if __name__ == "__main__":
    main()
