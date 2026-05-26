#!/usr/bin/env python3
"""Classify benchmark tasks into routing topics."""
from __future__ import annotations

import argparse
import re
import sys
from typing import Any

TOPICS = {
    "geometry",
    "game_simulation",
    "pattern_generation",
    "series_calculation",
    "unknown",
}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _field(task: dict[str, Any], key: str) -> str:
    if key in task:
        return str(task.get(key) or "")
    meta = task.get("metadata") or {}
    return str(meta.get(key) or "")


def classify_task(task: dict[str, Any]) -> str:
    """Return one of geometry/game_simulation/pattern_generation/series_calculation/unknown."""
    task_id = _norm(task.get("id"))
    topic = _norm(_field(task, "topic"))
    prompt = _norm(task.get("instruction") or task.get("prompt") or "")

    if "geometry" in topic:
        return "geometry"
    if "game_simulation" in topic or "game simulation" in topic or "guessing" in topic:
        return "game_simulation"
    if "pattern_generation" in topic or "pattern generation" in topic:
        return "pattern_generation"
    if "series_calculation" in topic or "series calculation" in topic:
        return "series_calculation"

    text = " ".join([task_id, topic, prompt])

    if "geometry" in text or re.search(r"\btriangle\b|\barea\b|heron|collinear|\bcoordinate\b|\bcoordinates\b", text):
        return "geometry"
    if (
        "game_simulation" in text
        or "game simulation" in text
        or "guess" in text
        or "points" in text
        or "win" in text
        or "srand" in text
        or "random" in text
    ):
        return "game_simulation"
    if (
        "pattern_generation" in text
        or "pattern generation" in text
        or "pattern" in text
        or "stars" in text
        or "pyramid" in text
        or "diamond" in text
        or "rows" in text
    ):
        return "pattern_generation"
    if (
        "series_calculation" in text
        or "series calculation" in text
        or "series" in text
        or "sum" in text
        or "factorial" in text
        or "term_i" in text
        or "rational" in text
    ):
        return "series_calculation"
    return "unknown"


def _self_test() -> None:
    cases = [
        ({"id": "2025_midterm_003", "topic": "Geometry", "instruction": "Compute triangle area"}, "geometry"),
        ({"id": "2025_midterm_004", "topic": "Game Simulation - Even/Odd Guessing", "instruction": "Pick and win points"}, "game_simulation"),
        ({"id": "synthetic_v3_pattern_generation_001", "topic": "pattern_generation", "instruction": "Print a pattern"}, "pattern_generation"),
        ({"id": "synthetic_v3_series_calculation_001", "topic": "series_calculation", "instruction": "Compute a sum"}, "series_calculation"),
        ({"id": "misc", "topic": "", "instruction": "Write a C program"}, "unknown"),
    ]
    failures: list[str] = []
    for task, expected in cases:
        actual = classify_task(task)
        if actual != expected:
            failures.append(f"{task.get('id')}: expected {expected}, got {actual}")
    if failures:
        print("[task-classifier] FAIL")
        for failure in failures:
            print(f"- {failure}")
        sys.exit(1)
    print("[task-classifier] self-test PASS")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify benchmark task topics")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.self_test:
        _self_test()
    else:
        print("Use --self-test or import classify_task().")


if __name__ == "__main__":
    main()
