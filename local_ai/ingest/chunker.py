#!/usr/bin/env python3
"""Semantic chunker: split cleaned HTML into structured JSON chunks.

Chunk boundaries are at heading, code block, and question boundaries —
not fixed-size windows. This keeps each chunk topically coherent,
which matters for small local models with limited context windows.

No external dependencies — stdlib html.parser and json only.

Output format per chunk:
  {
    "id":               "stem_0001",
    "source_file":      "sample.cleaned.html",
    "section":          "Chapter 2: Pointers",
    "content":          "...",
    "content_type":     "text" | "code" | "question",
    "estimated_tokens": 87
  }

Usage:
    python local_ai/ingest/chunker.py sample.cleaned.html
    python local_ai/ingest/chunker.py sample.cleaned.html -o output/sample.chunks.json
    python local_ai/ingest/chunker.py sample.cleaned.html --max-chars 2000
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


_DEFAULT_MAX_CHARS = 3000
# Rough characters-per-token estimates
_CPT_CODE = 4
_CPT_TEXT = 5

_QUESTION_RE = re.compile(
    r"^\s*Q\d*[:.)]"
    r"|^\s*\d+[.:]\s+[A-Z]"
    r"|\?\s*$"
    r"|^\s*(Question|Exercise|Problem|題目|問題)\s*\d*"
    r"|[（(][A-D][)）]",
    re.MULTILINE,
)

# Matches numbered exam questions at paragraph start: "1.", "2.", "3." etc.
# Used to auto-split PDF-derived HTML that has no heading tags.
_NUMBERED_QUESTION_START = re.compile(r"^\s*(\d{1,2})\.\s")


def _estimate_tokens(text: str, content_type: str) -> int:
    cpt = _CPT_CODE if content_type == "code" else _CPT_TEXT
    return max(1, len(text) // cpt)


def _content_type(text: str, tag: str) -> str:
    if tag == "pre":
        return "code"
    if _QUESTION_RE.search(text):
        return "question"
    return "text"


def _chunk_id(stem: str, index: int) -> str:
    safe = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
    return f"{safe}_{index:04d}"


# ── DOM walker ─────────────────────────────────────────────────────────────

class _Walker(HTMLParser):
    """Emit (tag, text) events for block-level elements in cleaned HTML."""

    _BLOCK_TAGS = frozenset({"h1", "h2", "h3", "h4", "p", "pre", "li", "td", "th", "blockquote"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.events: list[tuple[str, str]] = []
        self._cur_tag = ""
        self._buf: list[str] = []
        self._in_pre = False
        self._depth = 0  # nesting depth inside current block tag

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "pre":
            self._in_pre = True
            self._cur_tag = "pre"
            self._buf = []
            self._depth = 1
        elif tag in self._BLOCK_TAGS and not self._cur_tag:
            self._cur_tag = tag
            self._buf = []
            self._depth = 1
        elif self._cur_tag:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self._cur_tag:
            return
        if tag == self._cur_tag:
            self._depth -= 1
            if self._depth <= 0:
                content = "".join(self._buf)
                if tag == "pre":
                    # Strip leading/trailing blank lines; keep internal whitespace
                    content = content.strip("\n")
                else:
                    content = " ".join(content.split())
                if content:
                    self.events.append((self._cur_tag, content))
                self._cur_tag = ""
                self._buf = []
                self._in_pre = False
                self._depth = 0
        else:
            self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._cur_tag:
            self._buf.append(data)


# ── Chunking logic ─────────────────────────────────────────────────────────

def chunk_html(
    input_path: Path,
    output_path: Path | None = None,
    max_chars: int = _DEFAULT_MAX_CHARS,
) -> Path:
    """Split a cleaned HTML file into semantic JSON chunks."""
    if not input_path.exists():
        raise FileNotFoundError(f"HTML file not found: {input_path}")

    if output_path is None:
        # sample.cleaned.html → sample.chunks.json
        stem = re.sub(r"\.cleaned$", "", input_path.stem)
        output_path = input_path.with_name(f"{stem}.chunks.json")

    raw = input_path.read_text(encoding="utf-8", errors="replace")
    walker = _Walker()
    walker.feed(raw)

    source_stem = input_path.stem
    chunks: list[dict[str, Any]] = []
    section = ""
    pending: list[str] = []
    idx = 0

    def _flush() -> None:
        nonlocal idx
        if not pending:
            return
        content = "\n".join(pending).strip()
        if not content:
            pending.clear()
            return
        ctype = "question" if _QUESTION_RE.search(content) else "text"
        chunks.append({
            "id": _chunk_id(source_stem, idx),
            "source_file": input_path.name,
            "section": section,
            "content": content,
            "content_type": ctype,
            "estimated_tokens": _estimate_tokens(content, ctype),
        })
        idx += 1
        pending.clear()

    for tag, content in walker.events:
        if tag in ("h1", "h2", "h3", "h4"):
            _flush()
            section = content
        elif tag == "pre":
            _flush()
            chunks.append({
                "id": _chunk_id(source_stem, idx),
                "source_file": input_path.name,
                "section": section,
                "content": content,
                "content_type": "code",
                "estimated_tokens": _estimate_tokens(content, "code"),
            })
            idx += 1
        else:
            # p / li / td / th / blockquote
            # For PDF-derived HTML with no headings, treat "N. text..." as a
            # question boundary: flush pending and start a new section.
            m = _NUMBERED_QUESTION_START.match(content)
            if m and tag == "p":
                _flush()
                section = f"Question {m.group(1)}"
            # Accumulate with soft size ceiling
            if pending and sum(len(t) for t in pending) + len(content) > max_chars:
                _flush()
            if content:
                pending.append(content)

    _flush()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  chunked → {output_path} ({len(chunks)} chunks)", file=sys.stderr)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split cleaned HTML into semantic JSON chunks"
    )
    parser.add_argument("input", help="Input cleaned HTML file")
    parser.add_argument("-o", "--output", help="Output JSON file")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=_DEFAULT_MAX_CHARS,
        help=f"Soft character ceiling per text chunk (default: {_DEFAULT_MAX_CHARS})",
    )
    args = parser.parse_args()

    try:
        result = chunk_html(
            Path(args.input),
            Path(args.output) if args.output else None,
            args.max_chars,
        )
        print(result)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
