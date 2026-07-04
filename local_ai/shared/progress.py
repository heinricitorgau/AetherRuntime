"""Small terminal progress helpers for local_ai CLI surfaces.

Display-only utilities. They do not alter prompts, model payloads, scoring,
retry behavior, routing, or governance decisions.
"""
from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass
from typing import TextIO


UNICODE_SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴"]
ASCII_SPINNER = ["*", "\\", "|", "/"]


def supports_unicode(stream: TextIO | None = None) -> bool:
    stream = stream or sys.stdout
    encoding = (getattr(stream, "encoding", None) or "").lower()
    if not encoding:
        return False
    return "utf" in encoding


def symbols() -> dict[str, str]:
    if supports_unicode():
        return {
            "ok": "✓",
            "fail": "✗",
            "warn": "⚠",
            "filled": "■",
            "empty": "□",
            "bar_filled": "█",
            "bar_empty": "░",
        }
    return {
        "ok": "OK",
        "fail": "FAIL",
        "warn": "!",
        "filled": "#",
        "empty": ".",
        "bar_filled": "#",
        "bar_empty": ".",
    }


def spinner_frames() -> list[str]:
    return UNICODE_SPINNER if supports_unicode() else ASCII_SPINNER


def format_elapsed(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, rem = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{rem:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m{rem:02d}s"


def progress_bar(done: int, total: int, width: int = 14) -> str:
    sym = symbols()
    if total <= 0:
        return sym["bar_empty"] * width + " 0%"
    ratio = min(1.0, max(0.0, done / total))
    filled = int(round(width * ratio))
    bar = sym["bar_filled"] * filled + sym["bar_empty"] * (width - filled)
    return f"[{bar}] {ratio * 100:.0f}%"


def question_boxes(done: int, total: int) -> str:
    sym = symbols()
    total = max(0, total)
    done = min(max(0, done), total)
    return sym["filled"] * done + sym["empty"] * (total - done)


def separator() -> str:
    return "=" * 40


def print_model_info(
    *,
    configured_model: str | None,
    requested_model: str | None,
    effective_model: str | None,
    override_valid: bool | None,
) -> None:
    if override_valid is True:
        override = "VALID"
    elif override_valid is False:
        override = "INVALID"
    else:
        override = "not requested"
    print(separator())
    print("Model Information")
    print(separator())
    print("Configured Model:")
    print(configured_model or "(unknown)")
    print()
    print("Requested Model:")
    print(requested_model or "(none)")
    print()
    print("Effective Model:")
    print(effective_model or configured_model or "(unknown)")
    print()
    print("Override:")
    print(override)
    print(separator(), flush=True)


def print_question_start(index: int, total: int, task: str, status: str) -> None:
    completed = index - 1
    print()
    print(separator())
    print(f"Question {index} / {total}")
    print(separator())
    print("Question Progress")
    print(question_boxes(completed, total))
    print(progress_bar(completed, total))
    print()
    print("Task:")
    print(task)
    print()
    print("Status:")
    print(status)
    print(separator(), flush=True)


def print_stage(index: int, total: int, label: str) -> None:
    print(f"[{index}/{total}] {label}", flush=True)


def print_question_done(
    *,
    index: int,
    compile_ok: bool,
    runtime_ok: bool,
    semantic_ok: bool,
    elapsed: float,
) -> None:
    sym = symbols()
    print()
    print(f"{sym['ok']} Question {index} completed")
    print(f"Compile {'PASS' if compile_ok else 'FAIL'}")
    print(f"Runtime {'PASS' if runtime_ok else 'FAIL'}")
    print(f"Semantic {'PASS' if semantic_ok else 'FAIL'}")
    print(f"Elapsed: {elapsed:.1f} sec", flush=True)


def print_final_summary(
    *,
    questions_done: int,
    questions_total: int,
    compile_pass: int,
    runtime_pass: int,
    semantic_pass: int,
    average_score: float,
    elapsed: float,
    output_path: str,
) -> None:
    print()
    print(separator())
    print("Completed")
    print(separator())
    print("Questions:")
    print(f"{questions_done} / {questions_total}")
    print()
    print("Compile PASS:")
    print(compile_pass)
    print()
    print("Runtime PASS:")
    print(runtime_pass)
    print()
    print("Semantic PASS:")
    print(semantic_pass)
    print()
    print("Average Score:")
    print(f"{average_score:.1f}")
    print()
    print("Elapsed Time:")
    print(format_elapsed(elapsed))
    print()
    print("Output:")
    print(output_path)
    print(separator(), flush=True)


@dataclass
class ThinkingSpinner:
    model: str
    stage: str
    timeout: int
    update_interval: float = 3.0
    stream: TextIO = sys.stdout

    def __post_init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._start = 0.0

    def __enter__(self) -> "ThinkingSpinner":
        self._start = time.monotonic()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        self.stream.write("\n")
        self.stream.flush()

    def _run(self) -> None:
        frames = spinner_frames()
        idx = 0
        while not self._stop.is_set():
            elapsed = int(time.monotonic() - self._start)
            if self.timeout and elapsed >= max(1, int(self.timeout * 0.75)):
                label = f"{symbols()['warn']} Waiting model..."
                note = "Model still generating..."
            else:
                label = f"{frames[idx % len(frames)]} Thinking..."
                note = ""
            message = (
                f"\r{label} Current Model: {self.model} | "
                f"Stage: {self.stage} | Elapsed: {elapsed}s | Timeout: {self.timeout}s"
            )
            if note:
                message += f" | {note}"
            self.stream.write(message)
            self.stream.flush()
            idx += 1
            self._stop.wait(self.update_interval)
