#!/usr/bin/env python3
"""Shared library for the Human-Verified Corpus Platform (V10).

This is data-platform infrastructure, not a new governance framework. It defines
the corpus record schema, the stage lifecycle, the append-only audit trail, and
agent verification (reusing the benchmark compile/runtime/semantic helpers).

Lifecycle stages (directories under local_ai/corpus/):
  raw/      imported items, not yet agent-verified (pre-corpus)
  verified/ the corpus — candidate / human_verified / golden, by verification_level
  review/   items currently in human review (excluded from training)
  archive/  rejected or archived terminal items
  metadata/ corpus_index.json + audit_log.jsonl
  reports/  dashboard + validation reports

verification_level: agent_verified < human_verified < golden
review_status:      raw, candidate, in_review, approved, rejected, archived, golden
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_REPO_ROOT = _LOCAL_AI.parent
sys.path.insert(0, str(_LOCAL_AI / "benchmark"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

CORPUS_ROOT = _HERE
RAW_DIR = CORPUS_ROOT / "raw"
VERIFIED_DIR = CORPUS_ROOT / "verified"
REVIEW_DIR = CORPUS_ROOT / "review"
ARCHIVE_DIR = CORPUS_ROOT / "archive"
METADATA_DIR = CORPUS_ROOT / "metadata"
REPORTS_DIR = CORPUS_ROOT / "reports"

STAGE_DIRS = {
    "raw": RAW_DIR,
    "verified": VERIFIED_DIR,
    "review": REVIEW_DIR,
    "archive": ARCHIVE_DIR,
}
_INDEX = METADATA_DIR / "corpus_index.json"
_AUDIT_LOG = METADATA_DIR / "audit_log.jsonl"

REQUIRED_FIELDS = (
    "task_id", "source", "topic", "difficulty", "prompt", "reference_solution",
    "compile_verified", "runtime_verified", "semantic_verified",
    "review_status", "reviewer", "review_timestamp", "verification_level",
)

VALID_LEVELS = ("agent_verified", "human_verified", "golden")
VALID_STATUSES = ("raw", "candidate", "in_review", "approved", "rejected", "archived", "golden")

# Benchmark preference order: human_verified first, then golden, then agent.
# (golden is a hand-locked subset; human_verified is the broad trusted tier.)
BENCHMARK_LEVEL_PRIORITY = ("human_verified", "golden", "agent_verified")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_dirs() -> None:
    for d in (RAW_DIR, VERIFIED_DIR, REVIEW_DIR, ARCHIVE_DIR, METADATA_DIR, REPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def new_record(
    task_id: str,
    source: str,
    prompt: str,
    *,
    topic: str = "",
    difficulty: str = "",
    reference_solution: str = "",
    sample_input: str = "",
    expected_output_contains: list[str] | None = None,
) -> dict[str, Any]:
    ts = now()
    return {
        "task_id": task_id,
        "source": source,
        "topic": topic,
        "difficulty": difficulty,
        "prompt": prompt,
        "reference_solution": reference_solution,
        "sample_input": sample_input,
        "expected_output_contains": expected_output_contains or [],
        "compile_verified": False,
        "runtime_verified": False,
        "semantic_verified": False,
        "review_status": "raw",
        "reviewer": None,
        "review_timestamp": None,
        "verification_level": None,
        "created_at": ts,
        "history": [{"action": "import", "to_status": "raw", "at": ts, "by": source}],
    }


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_item(item: dict[str, Any], stage: str) -> Path:
    ensure_dirs()
    path = STAGE_DIRS[stage] / f"{item['task_id']}.json"
    path.write_text(json.dumps(item, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def find_item(task_id: str) -> tuple[str, Path, dict[str, Any]] | None:
    for stage, d in STAGE_DIRS.items():
        p = d / f"{task_id}.json"
        if p.exists():
            return stage, p, _load(p)
    return None


def iter_items(stage: str) -> Iterator[dict[str, Any]]:
    d = STAGE_DIRS[stage]
    if not d.exists():
        return
    for p in sorted(d.glob("*.json")):
        try:
            yield _load(p)
        except Exception:  # noqa: BLE001
            continue


def all_items() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for stage in STAGE_DIRS:
        for item in iter_items(stage):
            item["_stage"] = stage
            out.append(item)
    return out


def append_audit(entry: dict[str, Any]) -> None:
    ensure_dirs()
    entry = {"at": now(), **entry}
    with _AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def move_item(task_id: str, from_stage: str, to_stage: str) -> None:
    """Move an item's file between stages (history is preserved inside the record)."""
    src = STAGE_DIRS[from_stage] / f"{task_id}.json"
    if src.exists() and from_stage != to_stage:
        src.unlink()


def transition(
    item: dict[str, Any],
    action: str,
    to_status: str,
    *,
    to_level: str | None = None,
    reviewer: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    """Append-only state transition. Never rewrites prior history entries."""
    frm = item.get("review_status")
    item["review_status"] = to_status
    if to_level is not None:
        item["verification_level"] = to_level
    if reviewer is not None:
        item["reviewer"] = reviewer
        item["review_timestamp"] = now()
    item.setdefault("history", []).append({
        "action": action,
        "from_status": frm,
        "to_status": to_status,
        "to_level": to_level,
        "by": reviewer or "agent",
        "note": note,
        "at": now(),
    })
    return item


# ── Agent verification (reuses benchmark helpers; best-effort) ────────────────

def agent_verify(item: dict[str, Any]) -> dict[str, Any]:
    """Run compile / runtime / semantic checks on the reference_solution.

    Sets compile_verified / runtime_verified / semantic_verified. Best-effort:
    if no compiler is available, compile/runtime are left as-is and a note is
    recorded. Never fabricates a pass.
    """
    code = item.get("reference_solution") or ""
    if not code.strip():
        item["_verify_note"] = "no reference_solution"
        return item
    try:
        from _bench_common import compile_code, find_compiler, run_exe, semantic_check  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        item["_verify_note"] = f"helpers unavailable: {exc}"
        return item

    # Semantic check is static — always runs.
    try:
        sem = semantic_check(code)
        item["semantic_verified"] = bool(sem.get("passed"))
    except Exception:  # noqa: BLE001
        item["semantic_verified"] = False

    compiler = find_compiler()
    if not compiler:
        item["_verify_note"] = "no compiler; compile/runtime skipped"
        return item

    with tempfile.TemporaryDirectory() as tmp:
        comp = compile_code(code, item.get("task_id", "corpus"), Path(tmp), compiler)
        item["compile_verified"] = bool(comp.get("ok"))
        if comp.get("ok") and comp.get("exe"):
            run = run_exe(str(comp["exe"]), item.get("sample_input", ""), timeout=5)
            out = run.get("output", "") or ""
            expected = item.get("expected_output_contains", []) or []
            item["runtime_verified"] = bool(run.get("ok")) and all(t in out for t in expected)
        else:
            item["runtime_verified"] = False
    return item


def corpus_for_benchmark() -> list[dict[str, Any]]:
    """Return verified-corpus items in benchmark preference order
    (human_verified > golden > agent_verified). Never the reverse."""
    items = [i for i in iter_items("verified")]
    ranked = sorted(
        items,
        key=lambda i: BENCHMARK_LEVEL_PRIORITY.index(i.get("verification_level"))
        if i.get("verification_level") in BENCHMARK_LEVEL_PRIORITY else 99,
    )
    return ranked


def candidate_corpus_for_training() -> list[dict[str, Any]]:
    """LoRA-usable candidate corpus: agent_verified items NOT in review.
    Review-stage items are intentionally excluded."""
    return [
        i for i in iter_items("verified")
        if i.get("verification_level") == "agent_verified" and i.get("review_status") == "candidate"
    ]
