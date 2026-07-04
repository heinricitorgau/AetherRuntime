"""Chinese-to-English problem statement translation via a local Ollama model.

Used by the two data-import surfaces (corpus import and ingest training prep)
to translate Chinese exam problems into English BEFORE they reach the solver.
Translation is opt-in (--translate CLI flag at each call site), runs against a
dedicated general-instruct model (separate from the solver models), and every
translation is recorded for audit: the original text is always preserved next
to the translated text, and call sites write a JSON+MD translation report.

Failure policy: a failed translation never drops or mutates a record — the
original text is kept, the error is recorded in the returned entry, and the
call site surfaces it in the report.

Env:
  CLAW_TRANSLATE_MODEL             translation model (default: qwen2.5:7b-instruct)
  CLAW_OLLAMA_URL                  Ollama base URL (default: http://127.0.0.1:11434)
  CLAW_TRANSLATE_TIMEOUT_SECONDS   per-request timeout seconds (default: 180)

Usage:
  python local_ai/shared/translator.py --self-test
  python local_ai/shared/translator.py --text "寫一個C程式..."
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from local_ai.shared.report_utils import now_iso  # noqa: E402

DEFAULT_TRANSLATE_MODEL = "qwen2.5:7b-instruct"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_TIMEOUT_SECONDS = 180

# CJK Unified Ideographs + Extension A; enough to detect Chinese problem text.
_CJK_RE = re.compile(r"[㐀-䶿一-鿿]")

_TRANSLATE_SYSTEM = (
    "You are a professional translator for programming exam problems. "
    "Translate the given Chinese programming problem statement into English.\n"
    "Rules:\n"
    "- Preserve verbatim (do NOT translate or alter): code blocks, identifiers, "
    "numbers, sample input/output values, expected output tokens, file names.\n"
    "- Keep the original line structure. Existing markers such as point rubrics "
    "([3 pts]) or sub-task labels ((a), (b)) stay exactly where they appear; "
    "NEVER add markers, headings, or text that are not in the original.\n"
    "- Output ONLY the translated problem text. No explanations, no preamble."
)


def resolve_model(model: str | None = None) -> str:
    return model or os.environ.get("CLAW_TRANSLATE_MODEL", "").strip() or DEFAULT_TRANSLATE_MODEL


def resolve_ollama_url(url: str | None = None) -> str:
    return url or os.environ.get("CLAW_OLLAMA_URL", "").strip() or DEFAULT_OLLAMA_URL


def resolve_timeout(timeout: int | None = None) -> int:
    if timeout is not None:
        return timeout
    raw = os.environ.get("CLAW_TRANSLATE_TIMEOUT_SECONDS", "").strip()
    return int(raw) if raw.isdigit() else DEFAULT_TIMEOUT_SECONDS


def contains_chinese(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


def _ollama_chat(
    user_text: str,
    *,
    model: str,
    ollama_url: str,
    timeout: int,
) -> str:
    """Single non-streaming chat call to Ollama. Returns response text; raises on error."""
    payload = json.dumps({
        "model": model,
        "stream": False,
        "options": {"temperature": 0.0},
        "messages": [
            {"role": "system", "content": _TRANSLATE_SYSTEM},
            {"role": "user", "content": user_text},
        ],
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{ollama_url.rstrip('/')}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return str(body.get("message", {}).get("content", "")).strip()


def translate_if_chinese(
    text: str,
    *,
    model: str | None = None,
    ollama_url: str | None = None,
    timeout: int | None = None,
    transport: Callable[..., str] | None = None,
) -> dict[str, Any]:
    """Translate *text* zh->en when it contains Chinese; pass through otherwise.

    Returns an audit-ready entry:
      text        translated text on success, original text otherwise
      original    the input text (always kept)
      translated  True only when a translation was applied
      detected_chinese / model / latency_ms / error / output_contains_chinese / at

    *transport* is injectable for offline self-tests; defaults to Ollama.
    """
    model = resolve_model(model)
    ollama_url = resolve_ollama_url(ollama_url)
    timeout = resolve_timeout(timeout)
    call = transport or _ollama_chat

    entry: dict[str, Any] = {
        "text": text,
        "original": text,
        "translated": False,
        "detected_chinese": contains_chinese(text),
        "model": model,
        "latency_ms": 0,
        "error": None,
        "output_contains_chinese": False,
        "at": now_iso(),
    }
    if not entry["detected_chinese"]:
        return entry

    t0 = time.monotonic()
    try:
        translated = call(text, model=model, ollama_url=ollama_url, timeout=timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError,
            json.JSONDecodeError) as exc:
        entry["error"] = f"translation call failed: {exc}"
        return entry
    entry["latency_ms"] = int((time.monotonic() - t0) * 1000)

    if not translated:
        entry["error"] = "translation returned empty text; original kept"
        return entry

    entry["text"] = translated
    entry["translated"] = True
    entry["output_contains_chinese"] = contains_chinese(translated)
    return entry


# ── Translation report (shared JSON+MD shape for call sites) ─────────────────

def build_translation_report(
    entries: list[dict[str, Any]],
    *,
    surface: str,
    model: str,
) -> dict[str, Any]:
    """Aggregate per-record audit entries into a report dict.

    Each entry is a `translate_if_chinese` result plus a caller-added `id`.
    """
    translated = [e for e in entries if e.get("translated")]
    errors = [e for e in entries if e.get("error")]
    return {
        "surface": surface,
        "model": model,
        "generated_at": now_iso(),
        "records_seen": len(entries),
        "records_with_chinese": sum(1 for e in entries if e.get("detected_chinese")),
        "records_translated": len(translated),
        "records_failed": len(errors),
        "records_output_still_chinese": sum(
            1 for e in translated if e.get("output_contains_chinese")
        ),
        "entries": [
            {
                "id": e.get("id", "?"),
                "detected_chinese": e.get("detected_chinese", False),
                "translated": e.get("translated", False),
                "latency_ms": e.get("latency_ms", 0),
                "error": e.get("error"),
                "output_contains_chinese": e.get("output_contains_chinese", False),
                "original_head": (e.get("original") or "")[:120],
                "translated_head": ((e.get("text") or "")[:120]) if e.get("translated") else "",
            }
            for e in entries
        ],
    }


def render_translation_report_md(report: dict[str, Any]) -> str:
    lines = [
        "# Translation Report",
        "",
        f"- surface: `{report['surface']}`",
        f"- model: `{report['model']}`",
        f"- generated_at: {report['generated_at']}",
        f"- records seen: {report['records_seen']}",
        f"- records with Chinese: {report['records_with_chinese']}",
        f"- records translated: {report['records_translated']}",
        f"- records failed: {report['records_failed']}",
        f"- outputs still containing Chinese: {report['records_output_still_chinese']}",
        "",
        "| id | zh detected | translated | latency (ms) | error |",
        "|----|-------------|------------|--------------|-------|",
    ]
    for e in report["entries"]:
        lines.append(
            f"| {e['id']} | {'yes' if e['detected_chinese'] else 'no'} "
            f"| {'yes' if e['translated'] else 'no'} | {e['latency_ms']} "
            f"| {e['error'] or '-'} |"
        )
    lines.append("")
    return "\n".join(lines)


# ── Self-test (offline, mocked transport) ─────────────────────────────────────

def _self_test() -> bool:
    ok = True

    def check(name: str, cond: bool) -> None:
        nonlocal ok
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")
        ok = ok and cond

    check("detects Chinese", contains_chinese("寫一個C程式"))
    check("ignores English", not contains_chinese("Write a C program [3 pts]"))
    check("ignores empty", not contains_chinese(""))

    def fake_ok(text: str, **_kw: Any) -> str:
        return "Write a C program."

    def fake_empty(text: str, **_kw: Any) -> str:
        return ""

    def fake_boom(text: str, **_kw: Any) -> str:
        raise OSError("connection refused")

    passthrough = translate_if_chinese("Write a C program.", transport=fake_ok)
    check("English passes through untranslated",
          not passthrough["translated"] and passthrough["text"] == "Write a C program.")

    done = translate_if_chinese("寫一個C程式", transport=fake_ok)
    check("Chinese gets translated",
          done["translated"] and done["text"] == "Write a C program."
          and done["original"] == "寫一個C程式" and done["error"] is None)

    empty = translate_if_chinese("寫一個C程式", transport=fake_empty)
    check("empty output keeps original",
          not empty["translated"] and empty["text"] == "寫一個C程式" and empty["error"])

    boom = translate_if_chinese("寫一個C程式", transport=fake_boom)
    check("transport error keeps original",
          not boom["translated"] and boom["text"] == "寫一個C程式" and boom["error"])

    entries = [dict(done, id="a"), dict(passthrough, id="b"), dict(boom, id="c")]
    report = build_translation_report(entries, surface="self_test", model="fake")
    check("report aggregates counts",
          report["records_seen"] == 3 and report["records_translated"] == 1
          and report["records_failed"] == 1 and report["records_with_chinese"] == 2)
    md = render_translation_report_md(report)
    check("markdown renders all rows", md.count("\n| ") == 3 + 1)

    print(f"[translator] self-test {'ok' if ok else 'FAIL'}")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="zh->en problem translator (local Ollama)")
    parser.add_argument("--self-test", action="store_true", help="Run offline self-test")
    parser.add_argument("--text", help="Translate a single text and print the result JSON")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    if args.self_test:
        sys.exit(0 if _self_test() else 1)
    if args.text is None:
        parser.error("provide --text or --self-test")
    entry = translate_if_chinese(args.text, model=args.model)
    print(json.dumps(entry, ensure_ascii=False, indent=2))
    sys.exit(0 if entry["error"] is None else 1)


if __name__ == "__main__":
    main()
