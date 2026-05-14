"""Shared utilities for training_quality validators."""
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Paths ──────────────────────────────────────────────────────────────────

def tq_dir() -> Path:
    return Path(__file__).resolve().parent


def reports_dir() -> Path:
    d = tq_dir() / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def training_dir() -> Path:
    return tq_dir().parent / "ingest" / "output" / "training"


def eval_cases_dir() -> Path:
    return tq_dir().parent / "eval_cases" / "c_exam"


# ── I/O ────────────────────────────────────────────────────────────────────

def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def write_report(data: dict[str, Any], name: str) -> Path:
    path = reports_dir() / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_report(name: str) -> dict[str, Any]:
    path = reports_dir() / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── Record helpers ─────────────────────────────────────────────────────────

def record_code(rec: dict[str, Any]) -> str:
    """Extract the C code string from a training record's output field."""
    output = rec.get("output", "")
    # Strip markdown fence if present
    m = re.search(r"```(?:c|C)?\s*\n(.*?)```", output, re.DOTALL)
    if m:
        return m.group(1).strip()
    return output.strip()


def load_eval_case(case_id: str) -> dict[str, Any]:
    """Load the original eval case JSON for a given case_id."""
    cases_dir = eval_cases_dir()
    for path in cases_dir.glob("*.json"):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            if d.get("id") == case_id:
                return d
        except Exception:
            pass
    return {}


def load_code_gen_records() -> list[dict[str, Any]]:
    path = training_dir() / "code_generation.jsonl"
    if not path.exists():
        print(f"[error] {path} not found — run prepare_training.py first", file=sys.stderr)
        sys.exit(1)
    recs = load_jsonl(path)
    return [r for r in recs if r.get("output", "").strip()]


# ── C compiler discovery ───────────────────────────────────────────────────

_WINDOWS_GCC_PATHS = [
    r"C:\msys64\ucrt64\bin\gcc.exe",
    r"C:\msys64\mingw64\bin\gcc.exe",
    r"C:\MinGW\bin\gcc.exe",
    r"C:\TDM-GCC-64\bin\gcc.exe",
    r"C:\Program Files\mingw-w64\bin\gcc.exe",
]


def find_compiler() -> str | None:
    for name in ("cc", "gcc", "clang"):
        p = shutil.which(name)
        if p:
            return p
    for path in _WINDOWS_GCC_PATHS:
        if Path(path).exists():
            return path
    return None
