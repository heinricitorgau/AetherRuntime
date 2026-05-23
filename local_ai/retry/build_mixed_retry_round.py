#!/usr/bin/env python3
"""Build mixed retry rounds with trusted goldens and anti-regression samples."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_REPO_ROOT = _LOCAL_AI.parent

_BASE_SFT = _LOCAL_AI / "training_quality" / "reports" / "sft_chatml.jsonl"
_GEOMETRY_GOLDEN_DIR = _LOCAL_AI / "goldens" / "geometry"
_GEOMETRY_MANIFEST = _GEOMETRY_GOLDEN_DIR / "geometry_manifest.json"
_GAME_GOLDEN_DIR = _LOCAL_AI / "goldens" / "game"
_GAME_MANIFEST = _GAME_GOLDEN_DIR / "game_manifest.json"
_RETRY_V1 = _HERE / "rounds" / "round_geometry_v1" / "retry_chatml.jsonl"

_SUPPORTED_ROUNDS = {"round_geometry_v2", "round_geometry_v3_guarded"}
_V2_ANTI_REGRESSION_IDS = [
    "2025_midterm_001",
    "2025_midterm_002",
    "2025_midterm_004",
]
_V3_ANTI_REGRESSION_IDS = [
    "2025_midterm_001",
    "2025_midterm_002",
]
_GEOMETRY_GOLDEN_ID = "2025_midterm_003"
_GAME_GOLDEN_ID = "2025_midterm_004"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                rows.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL: {exc}") from exc
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _record_id(record: dict[str, Any]) -> str:
    meta = record.get("metadata") or {}
    return str(meta.get("id") or record.get("id") or "")


def _assistant_content(record: dict[str, Any]) -> str:
    for message in record.get("messages", []):
        if message.get("role") == "assistant":
            return str(message.get("content", ""))
    return ""


def _with_role(
    record: dict[str, Any],
    *,
    role: str,
    round_name: str,
    source: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = copy.deepcopy(record)
    meta = out.setdefault("metadata", {})
    meta["sample_role"] = role
    meta["mixed_round"] = round_name
    meta["source"] = source
    if extra:
        meta.update(extra)
    return out


def _find_record(rows: list[dict[str, Any]], task_id: str) -> dict[str, Any] | None:
    for row in rows:
        if _record_id(row) == task_id:
            return row
    return None


def _load_golden_manifest(manifest_path: Path, task_id: str) -> dict[str, Any]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in data.get("goldens", []):
        if item.get("id") == task_id:
            return item
    raise RuntimeError(f"golden manifest missing id {task_id}")


def _build_golden_record(
    base_rows: list[dict[str, Any]],
    round_name: str,
    *,
    task_id: str,
    category: str,
    sample_role: str,
    source: str,
) -> dict[str, Any]:
    if category == "geometry":
        manifest_path = _GEOMETRY_MANIFEST
        golden_dir = _GEOMETRY_GOLDEN_DIR
    elif category == "game":
        manifest_path = _GAME_MANIFEST
        golden_dir = _GAME_GOLDEN_DIR
    else:
        raise RuntimeError(f"unsupported golden category: {category}")

    manifest = _load_golden_manifest(manifest_path, task_id)
    golden_path = golden_dir / str(manifest["golden_file"])
    golden_code = golden_path.read_text(encoding="utf-8").strip() + "\n"

    template = _find_record(_read_jsonl(_RETRY_V1), task_id) if _RETRY_V1.exists() else None
    if template is None:
        template = _find_record(base_rows, task_id)
    if template is None:
        raise RuntimeError(f"could not find prompt template for {task_id}")

    record = copy.deepcopy(template)
    for message in record.get("messages", []):
        if message.get("role") == "assistant":
            message["content"] = golden_code
            break
    else:
        record.setdefault("messages", []).append({"role": "assistant", "content": golden_code})

    meta = record.setdefault("metadata", {})
    meta.update(
        {
            "id": task_id,
            "type": "retry_code_generation",
            "sample_role": sample_role,
            "mixed_round": round_name,
            "source": source,
            "golden": True,
            "golden_file": str(golden_path.relative_to(_REPO_ROOT)).replace("\\", "/"),
            "compile_verified": bool(manifest.get("compile_verified")),
            "runtime_verified": bool(manifest.get("runtime_verified")),
            "verified_at": manifest.get("verified_at"),
            "failure_categories": manifest.get("failure_categories", []),
        }
    )
    return record


def _is_code_generation(record: dict[str, Any]) -> bool:
    meta = record.get("metadata") or {}
    return str(meta.get("type")) == "code_generation" and bool(_assistant_content(record).strip())


def _topic(record: dict[str, Any]) -> str:
    return str((record.get("metadata") or {}).get("topic", "")).lower()


def _year(record: dict[str, Any]) -> int:
    try:
        return int((record.get("metadata") or {}).get("year", 0))
    except (TypeError, ValueError):
        return 0


def _select_anti_regression(
    base_rows: list[dict[str, Any]],
    round_name: str,
    task_ids: list[str],
    *,
    require_game: bool,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    by_id = {_record_id(row): row for row in base_rows}
    missing = [task_id for task_id in task_ids if task_id not in by_id]
    if missing:
        raise RuntimeError(f"missing anti-regression samples: {', '.join(missing)}")

    for task_id in task_ids:
        selected.append(
            _with_role(
                by_id[task_id],
                role="anti_regression",
                round_name=round_name,
                source="base_sft_accepted",
                extra={"anti_regression_reason": "2025 benchmark guard"},
            )
        )

    non_geometry = [row for row in selected if "geometry" not in _topic(row)]
    has_game = any("game" in _topic(row) for row in selected)
    if len(non_geometry) < 2 or (require_game and not has_game):
        for row in base_rows:
            rid = _record_id(row)
            if rid in {_record_id(item) for item in selected} or not _is_code_generation(row):
                continue
            topic = _topic(row)
            if "geometry" in topic:
                continue
            if len(non_geometry) < 2 or (require_game and "game" in topic and not has_game):
                mixed = _with_role(
                    row,
                    role="anti_regression",
                    round_name=round_name,
                    source="base_sft_accepted",
                    extra={"anti_regression_reason": "non-geometry/game balance"},
                )
                selected.append(mixed)
                non_geometry.append(mixed)
                has_game = has_game or "game" in topic
            if len(non_geometry) >= 2 and (has_game or not require_game):
                break

    if len(non_geometry) < 2:
        raise RuntimeError("could not select at least 2 non-geometry anti-regression samples")
    if require_game and not has_game:
        raise RuntimeError("could not select at least 1 game simulation anti-regression sample")
    return selected


def _select_balanced_geometry(base_rows: list[dict[str, Any]], round_name: str) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in base_rows:
        if not _is_code_generation(row):
            continue
        rid = _record_id(row)
        if rid == _GEOMETRY_GOLDEN_ID:
            continue
        topic = _topic(row)
        if _year(row) not in {2023, 2024}:
            continue
        if "geometry" not in topic and "triangle" not in topic:
            continue
        selected.append(
            _with_role(
                row,
                role="balanced_geometry",
                round_name=round_name,
                source="base_sft_accepted",
                extra={"balanced_reason": "near-year geometry guard"},
            )
        )
        if len(selected) == 2:
            break
    return selected


def build_round(round_name: str) -> tuple[Path, Path, dict[str, Any]]:
    if round_name not in _SUPPORTED_ROUNDS:
        raise RuntimeError(f"unsupported mixed retry round: {round_name}")

    base_rows = _read_jsonl(_BASE_SFT)
    rows: list[dict[str, Any]] = []
    balanced_geometry: list[dict[str, Any]] = []

    if round_name == "round_geometry_v2":
        rows.append(
            _build_golden_record(
                base_rows,
                round_name,
                task_id=_GEOMETRY_GOLDEN_ID,
                category="geometry",
                sample_role="golden_repair",
                source="golden_geometry_v1",
            )
        )
        rows.extend(
            _select_anti_regression(
                base_rows,
                round_name,
                _V2_ANTI_REGRESSION_IDS,
                require_game=True,
            )
        )
        balanced_geometry = _select_balanced_geometry(base_rows, round_name)
        rows.extend(balanced_geometry)
    elif round_name == "round_geometry_v3_guarded":
        rows.append(
            _build_golden_record(
                base_rows,
                round_name,
                task_id=_GEOMETRY_GOLDEN_ID,
                category="geometry",
                sample_role="geometry_golden_repair",
                source="golden_geometry_v1",
            )
        )
        rows.append(
            _build_golden_record(
                base_rows,
                round_name,
                task_id=_GAME_GOLDEN_ID,
                category="game",
                sample_role="game_golden_guard",
                source="golden_game_v1",
            )
        )
        rows.extend(
            _select_anti_regression(
                base_rows,
                round_name,
                _V3_ANTI_REGRESSION_IDS,
                require_game=False,
            )
        )

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        rid = _record_id(row)
        if not rid or rid in seen:
            continue
        seen.add(rid)
        deduped.append(row)

    role_counts = Counter((row.get("metadata") or {}).get("sample_role") for row in deduped)
    round_dir = _HERE / "rounds" / round_name
    chatml_path = round_dir / "retry_chatml.jsonl"
    metadata_path = round_dir / "retry_metadata.json"
    _write_jsonl(chatml_path, deduped)

    metadata = {
        "round": round_name,
        "created_at": _now(),
        "created_by": "build_mixed_retry_round.py",
        "dataset": str(chatml_path.relative_to(_REPO_ROOT)).replace("\\", "/"),
        "records": len(deduped),
        "anti_regression_samples": True,
        "sample_roles": dict(sorted(role_counts.items())),
        "balanced_geometry_candidates_found": len(balanced_geometry),
        "samples": [
            {
                "id": _record_id(row),
                "sample_role": (row.get("metadata") or {}).get("sample_role"),
                "topic": (row.get("metadata") or {}).get("topic"),
                "year": (row.get("metadata") or {}).get("year"),
            }
            for row in deduped
        ],
        "training_job": "retry_geometry_v3_guarded"
        if round_name == "round_geometry_v3_guarded"
        else "retry_geometry_v2",
        "training_intent": "stabilize geometry retry with game runtime guard"
        if round_name == "round_geometry_v3_guarded"
        else "stabilize geometry retry with anti-regression guards",
        "lora": {"r": 4, "alpha": 8, "dropout": 0.05},
        "epochs": 1 if round_name == "round_geometry_v3_guarded" else 2,
        "learning_rate": 0.000025 if round_name == "round_geometry_v3_guarded" else 0.00005,
        "sources": {
            "geometry_manifest": str(_GEOMETRY_MANIFEST.relative_to(_REPO_ROOT)).replace("\\", "/"),
            "game_manifest": str(_GAME_MANIFEST.relative_to(_REPO_ROOT)).replace("\\", "/"),
            "base_sft": str(_BASE_SFT.relative_to(_REPO_ROOT)).replace("\\", "/"),
        },
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return chatml_path, metadata_path, metadata


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build mixed retry training rounds")
    parser.add_argument("--round", required=True, help="Round name, e.g. round_geometry_v2")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        chatml_path, metadata_path, metadata = build_round(args.round)
    except Exception as exc:
        print(f"[mixed-retry] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"[mixed-retry] round={args.round}")
    print(f"  records  = {metadata['records']}")
    print(f"  roles    = {metadata['sample_roles']}")
    print(f"  chatml   >> {chatml_path}")
    print(f"  metadata >> {metadata_path}")


if __name__ == "__main__":
    main()
