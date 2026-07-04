#!/usr/bin/env python3
"""Import real exam material into the corpus raw/ stage (V10).

Supports PDF, Markdown, JSON, and TXT. Imported items land in `raw/` as
unverified pre-corpus records that still need a human to author/clean the
prompt and reference_solution before agent verification and review.

GUARDRAIL: raw OCR/PDF text is NEVER treated as finished corpus. PDF/TXT/MD
imports are stored with review_status='raw' and an explicit needs_manual_curation
flag; they must be curated by a human and then run through the review workflow.

Translation (--translate): prompts containing Chinese are translated to
English with the dedicated local translation model BEFORE the record lands in
raw/. The original prompt is preserved in `prompt_original`, the translation is
logged to the audit trail, and a translation report is written to
reports/translation_report.{json,md}. A failed translation keeps the original
prompt and is surfaced in the report.

RAG export (default on, disable with --no-rag-md): every newly imported
prompt (English natively or after --translate) is also written as a plain
problem .md into local_ai/rag/docs/problems/ and the RAG index is rebuilt,
so the local model can retrieve the problem text via --rag.

Usage:
  python local_ai/corpus/import_exam.py --file exam.json
  python local_ai/corpus/import_exam.py --file exam.json --translate
  python local_ai/corpus/import_exam.py --file exam.pdf --task-id 2024_exam1_001 --topic geometry
  python local_ai/corpus/import_exam.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_HERE))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import corpus_lib as cl  # noqa: E402

from local_ai.shared import rag_export, translator  # noqa: E402
from local_ai.shared.report_utils import write_json_report, write_text_report  # noqa: E402


def _import_json(path: Path) -> list[dict]:
    """JSON import: a single object or a list of corpus-shaped records."""
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data if isinstance(data, list) else [data]
    out = []
    for i, rec in enumerate(records):
        tid = rec.get("task_id") or rec.get("id") or f"{path.stem}_{i+1:03d}"
        item = cl.new_record(
            task_id=tid,
            source=f"import_json:{path.name}",
            prompt=rec.get("prompt", ""),
            topic=rec.get("topic", ""),
            difficulty=rec.get("difficulty", ""),
            reference_solution=rec.get("reference_solution", ""),
            sample_input=rec.get("sample_input", ""),
            expected_output_contains=rec.get("expected_output_contains", []),
        )
        out.append(item)
    return out


def _import_text(path: Path, task_id: str | None, topic: str, difficulty: str) -> list[dict]:
    """PDF/TXT/MD import: capture raw text as the prompt; flag for manual curation."""
    text = ""
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader  # noqa: PLC0415
            reader = PdfReader(str(path))
            text = "\n".join((pg.extract_text() or "") for pg in reader.pages)
        except Exception as exc:  # noqa: BLE001
            text = ""
            print(f"[import-exam] PDF text extraction unavailable ({exc}); "
                  f"importing empty raw item for manual entry", file=sys.stderr)
    else:
        text = path.read_text(encoding="utf-8", errors="replace")

    tid = task_id or path.stem
    item = cl.new_record(
        task_id=tid,
        source=f"import_{path.suffix.lstrip('.').lower()}:{path.name}",
        prompt=text.strip(),
        topic=topic,
        difficulty=difficulty,
    )
    item["needs_manual_curation"] = True
    item["history"][-1]["note"] = "raw text import; requires human curation before verification"
    return [item]


def _translate_items(
    items: list[dict],
    model: str | None = None,
    transport: Callable[..., str] | None = None,
) -> list[dict]:
    """Translate Chinese prompts in-place; return per-item audit entries."""
    resolved_model = translator.resolve_model(model)
    entries: list[dict] = []
    for item in items:
        entry = translator.translate_if_chinese(
            item.get("prompt", ""), model=resolved_model, transport=transport
        )
        entry["id"] = item["task_id"]
        entries.append(entry)
        if entry["error"]:
            print(f"[import-exam] WARNING: translation failed for {item['task_id']}: "
                  f"{entry['error']} (original prompt kept)", file=sys.stderr)
            continue
        if not entry["translated"]:
            continue
        item["prompt_original"] = entry["original"]
        item["prompt"] = entry["text"]
        item["translation"] = {
            "model": resolved_model,
            "at": entry["at"],
            "latency_ms": entry["latency_ms"],
            "output_contains_chinese": entry["output_contains_chinese"],
        }
        item["history"].append({
            "action": "translate",
            "to_status": item.get("review_status", "raw"),
            "at": entry["at"],
            "by": f"translator:{resolved_model}",
            "note": "prompt translated zh->en; original kept in prompt_original",
        })
    return entries


def _write_translation_report(entries: list[dict], model: str | None = None) -> Path:
    report = translator.build_translation_report(
        entries, surface="corpus_import", model=translator.resolve_model(model)
    )
    json_path = write_json_report(cl.REPORTS_DIR / "translation_report.json", report)
    write_text_report(
        cl.REPORTS_DIR / "translation_report.md",
        translator.render_translation_report_md(report),
    )
    return json_path


def import_file(
    path: Path,
    task_id: str | None = None,
    topic: str = "",
    difficulty: str = "",
    translate: bool = False,
    translate_model: str | None = None,
    rag_md: bool = True,
) -> int:
    cl.ensure_dirs()
    suffix = path.suffix.lower()
    if suffix == ".json":
        items = _import_json(path)
    elif suffix in (".pdf", ".txt", ".md"):
        items = _import_text(path, task_id, topic, difficulty)
    else:
        print(f"[import-exam] unsupported file type: {suffix}", file=sys.stderr)
        return 0

    if translate:
        entries = _translate_items(items, model=translate_model)
        report_path = _write_translation_report(entries, model=translate_model)
        translated = sum(1 for e in entries if e["translated"])
        failed = sum(1 for e in entries if e["error"])
        print(f"[import-exam] translation: {translated} translated, {failed} failed "
              f"-> {report_path}")

    written = 0
    imported_items: list[dict] = []
    for item in items:
        if cl.find_item(item["task_id"]):
            print(f"[import-exam] skip existing: {item['task_id']}")
            continue
        cl.save_item(item, "raw")
        audit = {"action": "import", "task_id": item["task_id"], "source": item["source"]}
        if item.get("translation"):
            audit["translated"] = True
            audit["translation_model"] = item["translation"]["model"]
        cl.append_audit(audit)
        imported_items.append(item)
        written += 1

    exportable = [it for it in imported_items if (it.get("prompt") or "").strip()]
    if rag_md and exportable:
        md_paths = rag_export.export_problems(
            [(item["task_id"], item["prompt"]) for item in exportable]
        )
        for item, md_path in zip(exportable, md_paths):
            cl.append_audit({
                "action": "rag_md_export",
                "task_id": item["task_id"],
                "path": str(md_path),
            })
        print(f"[import-exam] rag docs: {len(md_paths)} problem .md exported, index rebuilt")
    return written


def _self_test() -> bool:
    # Validate the JSON import shape without touching real files.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "x.json"
        p.write_text(json.dumps({"task_id": "t_selftest", "prompt": "p", "topic": "x"}), encoding="utf-8")
        items = _import_json(p)
    ok = len(items) == 1 and items[0]["review_status"] == "raw" and items[0]["task_id"] == "t_selftest"
    print(f"[import-exam] self-test {'ok' if ok else 'FAIL'}: parsed={len(items)}")

    # Translation path with a mocked transport (no Ollama needed).
    zh_item = cl.new_record(task_id="t_zh", source="self_test", prompt="寫一個C程式")
    en_item = cl.new_record(task_id="t_en", source="self_test", prompt="Write a C program")
    entries = _translate_items(
        [zh_item, en_item], model="fake", transport=lambda text, **_kw: "Write a C program."
    )
    t_ok = (
        zh_item["prompt"] == "Write a C program."
        and zh_item["prompt_original"] == "寫一個C程式"
        and zh_item["translation"]["model"] == "fake"
        and zh_item["history"][-1]["action"] == "translate"
        and "prompt_original" not in en_item
        and len(entries) == 2 and entries[0]["translated"] and not entries[1]["translated"]
    )
    print(f"[import-exam] translate self-test {'ok' if t_ok else 'FAIL'}")
    return ok and t_ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Import exam material into corpus raw/")
    parser.add_argument("--file", help="Path to PDF/MD/JSON/TXT")
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--topic", default="")
    parser.add_argument("--difficulty", default="")
    parser.add_argument(
        "--translate", action="store_true",
        help="Translate Chinese prompts to English before saving (original kept)",
    )
    parser.add_argument(
        "--translate-model", default=None,
        help=f"Translation model (default: env CLAW_TRANSLATE_MODEL or "
             f"{translator.DEFAULT_TRANSLATE_MODEL})",
    )
    parser.add_argument(
        "--no-rag-md", action="store_true",
        help="Skip exporting imported prompts as .md files into local_ai/rag/docs/problems/",
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        sys.exit(0 if _self_test() else 1)
    if not args.file:
        print("[import-exam] ERROR: --file required (or --self-test)", file=sys.stderr)
        sys.exit(2)
    n = import_file(
        Path(args.file), args.task_id, args.topic, args.difficulty,
        translate=args.translate, translate_model=args.translate_model,
        rag_md=not args.no_rag_md,
    )
    print(f"[import-exam] imported {n} item(s) into raw/ (require curation + review before verified)")


if __name__ == "__main__":
    main()
