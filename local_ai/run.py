#!/usr/bin/env python3
"""Interactive local_ai entry point.

This is a display-focused wrapper around local_ai/cli.py. It does not change
model prompts, inference behavior, benchmark scoring, routing, governance, or
corpus data.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from local_ai.shared.progress import (
    format_elapsed,
    print_model_info,
    print_stage,
    progress_bar,
    separator,
    symbols,
)


def _default_model() -> str:
    return os.environ.get("CLAW_MODEL", "qwen2.5-coder:3b")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    started = time.monotonic()
    command_args = argv if argv else ["smoke"]
    model = _default_model()

    print_model_info(
        configured_model=model,
        requested_model=None,
        effective_model=model,
        override_valid=None,
    )
    print()
    print(separator())
    print("Interactive Run")
    print(separator())
    print(f"Command: {' '.join(command_args)}")
    print(progress_bar(0, 3))
    print_stage(1, 3, "Resolve Command")

    cmd = [sys.executable, str(_HERE / "cli.py"), *command_args]
    print_stage(2, 3, "Launch CLI")
    completed = subprocess.run(cmd, cwd=str(_REPO_ROOT), check=False)

    print_stage(3, 3, "Complete")
    mark = symbols()["ok"] if completed.returncode == 0 else symbols()["fail"]
    status = "PASS" if completed.returncode == 0 else "FAIL"
    print(progress_bar(3, 3))
    print()
    print(separator())
    print("Run Summary")
    print(separator())
    print(f"{mark} Status: {status}")
    print(f"Exit Code: {completed.returncode}")
    print(f"Elapsed Time: {format_elapsed(time.monotonic() - started)}")
    print(separator(), flush=True)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
