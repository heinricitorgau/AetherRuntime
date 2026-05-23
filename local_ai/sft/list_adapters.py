#!/usr/bin/env python3
"""List governed LoRA adapters by promotion status."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ADAPTER_DIR = _HERE / "adapters"
_REPORT_DIR = _HERE / "reports"

_REGISTRY_FILES = {
    "promote": "promoted_adapters.json",
    "safe_no_change": "safe_adapters.json",
    "ablation_only": "ablation_adapters.json",
    "reject": "rejected_adapters.json",
}
_DEFAULT_FILE = "default_adapter.json"
_STATUSES = tuple(_REGISTRY_FILES)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _adapter_name(path: str | None) -> str:
    if not path:
        return "-"
    return Path(str(path).replace("\\", "/")).name or str(path)


def _fmt_delta(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, int):
        return f"{value:+d}"
    try:
        return f"{float(value):+.3g}"
    except (TypeError, ValueError):
        return str(value)


def _entry_to_row(entry: dict[str, Any], fallback_status: str) -> dict[str, Any]:
    status = str(entry.get("status") or fallback_status)
    adapter_path = str(entry.get("adapter_path") or "")
    return {
        "status": status,
        "adapter": _adapter_name(adapter_path),
        "adapter_path": adapter_path,
        "avg_delta": entry.get("avg_delta"),
        "runtime_delta": entry.get("runtime_delta"),
        "accepted_delta": entry.get("accepted_delta"),
        "comparison_run": entry.get("comparison_run_id"),
        "notes": entry.get("notes"),
        "timestamp": entry.get("timestamp"),
    }


def load_adapter_rows(status_filter: str | None = None) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    default_data = _load_json(_ADAPTER_DIR / _DEFAULT_FILE, {})
    default_selected = bool(default_data.get("active"))

    if default_data.get("active"):
        rows.append(_entry_to_row(default_data["active"], "promote"))

    for status, filename in _REGISTRY_FILES.items():
        data = _load_json(_ADAPTER_DIR / filename, {"adapters": []})
        adapters = data.get("adapters")
        if not isinstance(adapters, list):
            adapters = []
        for entry in adapters:
            rows.append(_entry_to_row(entry, status))

    if status_filter:
        rows = [row for row in rows if row["status"] == status_filter]
    rows.sort(key=lambda row: (row.get("status") or "", row.get("adapter") or ""))
    return rows, default_selected


def _table(rows: list[dict[str, Any]], default_selected: bool) -> str:
    headers = [
        "Status",
        "Adapter",
        "Avg Δ",
        "Runtime Δ",
        "Accepted Δ",
        "Comparison Run",
        "Notes",
    ]
    data = [
        [
            row["status"],
            row["adapter"],
            _fmt_delta(row["avg_delta"]),
            _fmt_delta(row["runtime_delta"]),
            _fmt_delta(row["accepted_delta"]),
            str(row.get("comparison_run") or "-"),
            str(row.get("notes") or "-"),
        ]
        for row in rows
    ]
    widths = [len(h) for h in headers]
    for line in data:
        for idx, cell in enumerate(line):
            widths[idx] = max(widths[idx], len(cell))

    rendered: list[str] = []
    if not default_selected:
        rendered.append("No default adapter selected.")
        rendered.append("")
    rendered.append(" | ".join(h.ljust(widths[idx]) for idx, h in enumerate(headers)))
    rendered.append("-+-".join("-" * w for w in widths))
    if data:
        for line in data:
            rendered.append(" | ".join(cell.ljust(widths[idx]) for idx, cell in enumerate(line)))
    else:
        rendered.append(" | ".join("empty".ljust(widths[idx]) if idx == 0 else "-".ljust(widths[idx]) for idx in range(len(headers))))
    return "\n".join(rendered)


def _markdown(rows: list[dict[str, Any]], default_selected: bool) -> str:
    lines: list[str] = []
    a = lines.append
    a("# Adapter Registry Summary")
    a("")
    a(f"Generated: `{_now()}`")
    a("")
    if not default_selected:
        a("No default adapter selected.")
        a("")
    a("| Status | Adapter | Avg Δ | Runtime Δ | Accepted Δ | Comparison Run | Notes |")
    a("|--------|---------|------:|----------:|-----------:|----------------|-------|")
    if rows:
        for row in rows:
            a(
                "| "
                + " | ".join(
                    [
                        str(row["status"]),
                        f"`{row['adapter']}`",
                        _fmt_delta(row["avg_delta"]),
                        _fmt_delta(row["runtime_delta"]),
                        _fmt_delta(row["accepted_delta"]),
                        f"`{row.get('comparison_run') or '-'}`",
                        str(row.get("notes") or "-"),
                    ]
                )
                + " |"
            )
    else:
        a("| empty | - | - | - | - | - | - |")
    return "\n".join(lines)


def _summary_payload(rows: list[dict[str, Any]], default_selected: bool, status_filter: str | None) -> dict[str, Any]:
    return {
        "timestamp": _now(),
        "default_adapter_selected": default_selected,
        "status_filter": status_filter,
        "count": len(rows),
        "adapters": rows,
    }


def write_reports(rows: list[dict[str, Any]], default_selected: bool, status_filter: str | None) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _summary_payload(rows, default_selected, status_filter)
    (_REPORT_DIR / "adapter_registry_summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (_REPORT_DIR / "adapter_registry_summary.md").write_text(
        _markdown(rows, default_selected),
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List adapter promotion registries")
    parser.add_argument("--status", choices=_STATUSES, help="Filter by adapter status")
    parser.add_argument("--format", choices=["table", "markdown", "json"], default="table")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    rows, default_selected = load_adapter_rows(args.status)
    write_reports(rows, default_selected, args.status)

    if args.format == "json":
        print(json.dumps(_summary_payload(rows, default_selected, args.status), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(_markdown(rows, default_selected))
    else:
        print(_table(rows, default_selected))


if __name__ == "__main__":
    main()
