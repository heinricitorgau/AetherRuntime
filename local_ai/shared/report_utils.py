"""JSON report read/write helpers used across subsystems."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_report(data: dict[str, Any], path: Path) -> Path:
    """Write *data* as pretty-printed JSON to *path*, creating parents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_report(path: Path) -> dict[str, Any]:
    """Return parsed JSON from *path*, or empty dict if missing."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_report(path: Path, data: dict[str, Any]) -> Path:
    """Write a JSON report to *path*."""
    return write_report(data, path)


def write_text_report(path: Path, text: str) -> Path:
    """Write a plain-text report to *path*, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
