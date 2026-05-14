#!/usr/bin/env python3
"""Compile each training record's C code and report results.

Writes reports/compile_report.json.

Usage:
    python local_ai/training_quality/compile_validator.py
    python local_ai/training_quality/compile_validator.py --work-dir /tmp/tq_build
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from _common import (
    find_compiler,
    load_code_gen_records,
    now_iso,
    record_code,
    write_report,
)


_MSYS2_PATH_PREFIXES = [
    r"C:\msys64\ucrt64\bin",
    r"C:\msys64\usr\bin",
    r"C:\msys64\mingw64\bin",
]


def _compiler_env(compiler: str) -> dict:
    """Build a subprocess env that includes msys2 DLL search paths if needed."""
    env = os.environ.copy()
    if "msys64" in compiler.lower():
        extra = os.pathsep.join(p for p in _MSYS2_PATH_PREFIXES if Path(p).exists())
        if extra:
            env["PATH"] = extra + os.pathsep + env.get("PATH", "")
    return env


# ── Core compile ───────────────────────────────────────────────────────────

def compile_one(
    code: str,
    case_id: str,
    work_dir: Path,
    compiler: str,
) -> dict:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", case_id)
    src = work_dir / f"{safe_id}.c"
    exe = work_dir / (safe_id + (".exe" if sys.platform == "win32" else ""))
    src.write_text(code, encoding="utf-8")

    try:
        result = subprocess.run(
            [compiler, "-std=c99", "-Wall", "-o", str(exe), str(src), "-lm"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=15,
            env=_compiler_env(compiler),
        )
        ok = result.returncode == 0
        stderr = (result.stderr or "").strip()
        warnings = [l for l in stderr.splitlines() if "warning:" in l]
        errors   = [l for l in stderr.splitlines() if "error:" in l]
        return {
            "id": case_id,
            "ok": ok,
            "message": "ok" if ok else f"compile error ({len(errors)} errors)",
            "errors":   errors[:10],
            "warnings": warnings[:10],
            "exe": str(exe) if ok else None,
        }
    except subprocess.TimeoutExpired:
        return {"id": case_id, "ok": False, "message": "compile timeout", "errors": [], "warnings": [], "exe": None}
    except Exception as exc:
        return {"id": case_id, "ok": False, "message": str(exc)[:200], "errors": [], "warnings": [], "exe": None}


# ── Batch ──────────────────────────────────────────────────────────────────

def run(work_dir: Path | None = None) -> dict:
    compiler = find_compiler()
    if not compiler:
        print("[compile] no C compiler found — skipping", file=sys.stderr)
        return {"compiler": None, "results": [], "passed": 0, "failed": 0, "skipped": 0}

    records = load_code_gen_records()
    if not records:
        print("[compile] no answered records found", file=sys.stderr)
        return {"compiler": compiler, "results": [], "passed": 0, "failed": 0, "skipped": 0}

    managed = work_dir is None
    tmp = tempfile.mkdtemp(prefix="tq_build_") if managed else None
    wd = Path(tmp) if tmp else work_dir
    wd.mkdir(parents=True, exist_ok=True)

    results = []
    for rec in records:
        code = record_code(rec)
        if not code:
            results.append({"id": rec["id"], "ok": False, "message": "empty output", "errors": [], "warnings": [], "exe": None})
            continue
        r = compile_one(code, rec["id"], wd, compiler)
        status = "ok" if r["ok"] else "FAIL"
        print(f"  [{status}] {rec['id']}  {r['message']}")
        results.append(r)

    passed = sum(1 for r in results if r["ok"])
    report = {
        "validator": "compile",
        "timestamp": now_iso(),
        "compiler": compiler,
        "work_dir": str(wd),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    path = write_report(report, "compile_report.json")
    print(f"\n[compile] {passed}/{len(results)} passed  -> {path}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile-validate training records")
    parser.add_argument("--work-dir", help="Directory for build artifacts (default: temp)")
    args = parser.parse_args()
    wd = Path(args.work_dir) if args.work_dir else None
    run(work_dir=wd)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
