"""Subprocess helpers: find compiler, compile C code, run executables."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

_MSYS2_GCC_PATHS = [
    r"C:\msys64\ucrt64\bin\gcc.exe",
    r"C:\msys64\mingw64\bin\gcc.exe",
    r"C:\msys64\mingw32\bin\gcc.exe",
]


def find_compiler() -> str | None:
    """Return path to gcc or clang, checking PATH then known Windows locations."""
    for name in ("gcc", "clang", "cc"):
        found = shutil.which(name)
        if found:
            return found
    for p in _MSYS2_GCC_PATHS:
        if Path(p).exists():
            return p
    return None


def compile_code(source: str, compiler: str | None = None, extra_flags: list[str] | None = None) -> tuple[bool, str, Path | None]:
    """Compile *source* C code.

    Returns (success, stderr_output, exe_path_or_None).
    The caller is responsible for cleaning up the tempdir containing exe_path.
    """
    cc = compiler or find_compiler()
    if cc is None:
        return False, "No C compiler found on PATH", None

    tmpdir = Path(tempfile.mkdtemp())
    src_path = tmpdir / "prog.c"
    exe_path = tmpdir / ("prog.exe" if os.name == "nt" else "prog")
    src_path.write_text(source, encoding="utf-8")

    flags = ["-std=c99", "-Wall", "-o", str(exe_path), str(src_path)]
    if extra_flags:
        flags.extend(extra_flags)

    try:
        result = subprocess.run(
            [cc] + flags,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, result.stderr, exe_path
        return False, result.stderr, None
    except subprocess.TimeoutExpired:
        return False, "Compile timed out", None
    except Exception as exc:
        return False, str(exc), None


def run_exe(exe_path: Path, stdin_data: str = "", timeout: int = 10) -> tuple[bool, str]:
    """Run a compiled executable.  Returns (success, stdout_output)."""
    try:
        result = subprocess.run(
            [str(exe_path)],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout
    except subprocess.TimeoutExpired:
        return False, ""
    except Exception as exc:
        return False, str(exc)
