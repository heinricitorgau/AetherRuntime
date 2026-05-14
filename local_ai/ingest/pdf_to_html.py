#!/usr/bin/env python3
"""PDF → HTML conversion with offline best-effort fallback.

Fallback order: pymupdf (fitz) → pdfminer.six → pypdf
No network access required. Uses only already-installed packages.

Usage:
    python local_ai/ingest/pdf_to_html.py input.pdf
    python local_ai/ingest/pdf_to_html.py input.pdf -o output/input.html
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path
from typing import Any


# ── Shared helpers ─────────────────────────────────────────────────────────

_CODE_PATTERNS = re.compile(
    r"#include\s*[<\"]"
    r"|\bint\s+main\s*\("
    r"|\b(printf|scanf|malloc|free|sizeof)\s*\("
    r"|[{};]\s*$"
    r"|^\s*(for|while|if|return|void|int|char|float|double|struct|typedef)\b",
    re.MULTILINE,
)

_MONO_FONT_NAMES = ("mono", "courier", "consolas", "code", "fixed", "typewriter", "inconsolata")


def _looks_like_code(text: str) -> bool:
    return bool(_CODE_PATTERNS.search(text))


def _is_monospace_font(font_name: str) -> bool:
    lower = font_name.lower()
    return any(m in lower for m in _MONO_FONT_NAMES)


def _html_envelope(title: str, body: str) -> str:
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="UTF-8">\n'
        f'<title>{html.escape(title)}</title>\n'
        '</head>\n<body>\n'
        f'{body}'
        '</body>\n</html>\n'
    )


# ── Strategy 1: PyMuPDF ────────────────────────────────────────────────────

def _extract_pymupdf(pdf_path: Path) -> str:
    import fitz  # type: ignore  # pip: pymupdf

    doc = fitz.open(str(pdf_path))

    # ── Pass 1: collect font sizes for heading classification ──────────────
    # Also collect per-block metadata: max font size, bold flag, mono flag.
    # Key: (page_index, block_no) → {max_size, is_bold, is_mono}
    block_meta: dict[tuple[int, int], dict] = {}
    all_sizes: list[float] = []

    for page_idx, page in enumerate(doc):
        d = page.get_text("dict").get("blocks", [])
        for block in d:
            if block.get("type") != 0:
                continue
            bno = block.get("number", id(block))
            max_sz = 0.0
            bold = False
            mono = False
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    sz = float(span.get("size", 0))
                    if sz > 4:
                        all_sizes.append(sz)
                    if sz > max_sz:
                        max_sz = sz
                    if span.get("flags", 0) & 16:
                        bold = True
                    if _is_monospace_font(span.get("font", "")):
                        mono = True
            block_meta[(page_idx, bno)] = {"max_size": max_sz, "is_bold": bold, "is_mono": mono}

    if not all_sizes:
        doc.close()
        raise ValueError("No text content found in PDF")

    all_sizes.sort()
    body_sz = all_sizes[len(all_sizes) // 2]
    h1_min = body_sz * 1.55
    h2_min = body_sz * 1.25
    h3_min = body_sz * 1.10

    # ── Pass 2: reconstruct text using word bounding boxes ─────────────────
    # get_text("words") returns (x0,y0,x1,y1,word,block_no,line_no,word_no)
    # Grouping by (block_no, line_no) and joining with spaces gives correct
    # word spacing even when the PDF omits explicit space characters.
    parts: list[str] = []

    for page_idx, page in enumerate(doc):
        # Group words: {block_no: {line_no: [(x0, word)]}}
        word_map: dict[int, dict[int, list[tuple[float, str]]]] = {}
        for w in page.get_text("words"):
            x0, _y0, _x1, _y1, word, bno, lno, _wno = w
            word_map.setdefault(bno, {}).setdefault(lno, []).append((x0, word))

        # Also need block ordering by vertical position
        block_order: list[tuple[float, int]] = []
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            bno = block.get("number", -1)
            y0 = block.get("bbox", (0, 0, 0, 0))[1]
            block_order.append((y0, bno))
        block_order.sort()

        for _y, bno in block_order:
            if bno not in word_map:
                continue
            meta = block_meta.get((page_idx, bno), {})
            max_size = meta.get("max_size", 0.0)
            is_bold = meta.get("is_bold", False)
            is_mono = meta.get("is_mono", False)

            # Reconstruct lines in reading order (sort lines by number, words by x)
            block_lines: list[str] = []
            for lno in sorted(word_map[bno]):
                words_in_line = sorted(word_map[bno][lno], key=lambda t: t[0])
                line_text = " ".join(w for _, w in words_in_line)
                if line_text.strip():
                    block_lines.append(line_text)

            text = "\n".join(block_lines).strip()
            if not text:
                continue

            escaped = html.escape(text)

            if is_mono or _looks_like_code(text):
                parts.append(f"<pre><code>{escaped}</code></pre>\n")
            elif max_size >= h1_min:
                parts.append(f"<h1>{escaped}</h1>\n")
            elif max_size >= h2_min or (is_bold and max_size >= h3_min):
                parts.append(f"<h2>{escaped}</h2>\n")
            elif max_size >= h3_min:
                parts.append(f"<h3>{escaped}</h3>\n")
            else:
                parts.append(f"<p>{escaped}</p>\n")

    doc.close()
    return _html_envelope(pdf_path.stem, "".join(parts))


# ── Strategy 2: pdfminer.six ───────────────────────────────────────────────

def _extract_pdfminer(pdf_path: Path) -> str:
    from pdfminer.high_level import extract_text  # type: ignore  # pip: pdfminer.six
    from pdfminer.layout import LAParams  # type: ignore

    params = LAParams(line_margin=0.5, char_margin=2.0, word_margin=0.1)
    raw = extract_text(str(pdf_path), laparams=params)
    return _text_to_html(raw, pdf_path.stem)


# ── Strategy 3: pypdf ──────────────────────────────────────────────────────

def _extract_pypdf(pdf_path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore  # pip: pypdf
    except ImportError:
        from PyPDF2 import PdfReader  # type: ignore  # pip: PyPDF2 (legacy)

    reader = PdfReader(str(pdf_path))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)
    return _text_to_html("\n\n".join(pages), pdf_path.stem)


# ── Text → HTML (used by pdfminer / pypdf fallbacks) ──────────────────────

def _text_to_html(raw: str, title: str) -> str:
    """Convert plain extracted text to basic HTML with heuristic heading/code detection."""
    lines = raw.splitlines()
    parts: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Underline-style headings: line followed by === or ---
        if i + 1 < len(lines):
            underline = lines[i + 1].strip()
            if re.fullmatch(r"=+", underline) and len(underline) >= 3:
                parts.append(f"<h1>{html.escape(stripped)}</h1>\n")
                i += 2
                continue
            if re.fullmatch(r"-+", underline) and len(underline) >= 3:
                parts.append(f"<h2>{html.escape(stripped)}</h2>\n")
                i += 2
                continue

        # Short all-caps line → probable heading
        if len(stripped) <= 60 and stripped.isupper() and len(stripped) > 3:
            parts.append(f"<h2>{html.escape(stripped)}</h2>\n")
            i += 1
            continue

        # Code block: indented 4+ spaces or tab, or C-pattern match
        if line.startswith("    ") or line.startswith("\t") or _looks_like_code(stripped):
            code_lines = [line]
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if not nxt.strip():
                    # Allow one blank line inside code block
                    if i + 1 < len(lines) and (
                        lines[i + 1].startswith("    ")
                        or lines[i + 1].startswith("\t")
                        or _looks_like_code(lines[i + 1].strip())
                    ):
                        code_lines.append(nxt)
                        i += 1
                        continue
                    break
                if nxt.startswith("    ") or nxt.startswith("\t") or _looks_like_code(nxt.strip()):
                    code_lines.append(nxt)
                    i += 1
                else:
                    break
            code = "\n".join(code_lines)
            parts.append(f"<pre><code>{html.escape(code)}</code></pre>\n")
            continue

        # Paragraph: accumulate until blank line or code start
        para: list[str] = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt:
                i += 1
                break
            if lines[i].startswith("    ") or lines[i].startswith("\t") or _looks_like_code(nxt):
                break
            para.append(nxt)
            i += 1
        parts.append(f"<p>{html.escape(' '.join(para))}</p>\n")

    return _html_envelope(title, "".join(parts))


# ── Dispatch ───────────────────────────────────────────────────────────────

_STRATEGIES = [
    ("pymupdf", _extract_pymupdf),
    ("pdfminer", _extract_pdfminer),
    ("pypdf", _extract_pypdf),
]


def pdf_to_html(pdf_path: Path, output_path: Path | None = None) -> Path:
    """Convert a PDF to HTML using the best available offline library.

    Tries pymupdf → pdfminer.six → pypdf and returns the output path.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if output_path is None:
        output_path = pdf_path.with_suffix(".html")

    last_err: Exception | None = None
    for name, strategy in _STRATEGIES:
        try:
            print(f"  trying {name}...", file=sys.stderr)
            content = strategy(pdf_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            print(f"  ok [{name}] → {output_path}", file=sys.stderr)
            return output_path
        except ImportError:
            print(f"  {name}: not installed, skipping", file=sys.stderr)
        except Exception as exc:
            print(f"  {name}: failed ({exc})", file=sys.stderr)
            last_err = exc

    raise RuntimeError(
        f"All PDF extraction strategies failed for {pdf_path}. "
        "Install pymupdf, pdfminer.six, or pypdf."
    ) from last_err


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert PDF to HTML (offline, best-effort)"
    )
    parser.add_argument("input", help="Input PDF file path")
    parser.add_argument("-o", "--output", help="Output HTML path (default: <input>.html)")
    args = parser.parse_args()

    try:
        result = pdf_to_html(
            Path(args.input),
            Path(args.output) if args.output else None,
        )
        print(result)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
