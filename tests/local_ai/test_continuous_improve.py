from __future__ import annotations

from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_DIR = ROOT / "local_ai" / "benchmark"
sys.path.insert(0, str(BENCHMARK_DIR))

from continuous_improve import build_repair_prompt, check_summary, evaluate_text


def test_check_summary_includes_failed_checks_only() -> None:
    summary = check_summary(
        {
            "proxy": {"passed": True, "note": "ok"},
            "compile": {"passed": False, "message": "compile error"},
            "keyword": {"passed": False, "missing": ["scanf", "for"]},
        }
    )

    assert "proxy" not in summary
    assert "- compile: compile error" in summary
    assert "- keyword: scanf; for" in summary


def test_build_repair_prompt_carries_task_feedback_and_previous_code() -> None:
    task = {"instruction": "Write a C program.", "id": "case1"}
    result = {"score": 15, "checks": {"compile": {"passed": False, "message": "missing ;"}}}

    prompt = build_repair_prompt(task, "int main(void) {", result)

    assert "Write a C program." in prompt
    assert "Previous score: 15/100" in prompt
    assert "missing ;" in prompt
    assert "int main(void) {" in prompt
    assert "complete C99 program" in prompt


def test_evaluate_text_scores_valid_c_without_compiler(tmp_path: Path) -> None:
    task = {
        "id": "hello_case",
        "sample_input": "",
        "expected_tokens": ["hello"],
        "expected_keywords": ["printf"],
        "topic": "Smoke",
        "difficulty": "easy",
        "points": 1,
        "year": 2026,
        "exam": "unit",
    }
    raw = '#include <stdio.h>\nint main(void) { printf("hello\\n"); return 0; }\n'

    result = evaluate_text(
        task=task,
        raw_response=raw,
        compiler=None,
        work_dir=tmp_path,
        run_timeout=1,
    )

    assert result["checks"]["structure"]["passed"]
    assert result["checks"]["keyword"]["passed"]
    assert not result["checks"]["compile"]["passed"]
    assert result["score"] == 30
