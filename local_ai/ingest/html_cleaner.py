#!/usr/bin/env python3
"""HTML cleaner: strip layout noise, keep semantic structure.

Converts messy HTML (from pdf_to_html.py or web sources) into
simplified HTML using only allowed semantic tags.

No external dependencies — stdlib html.parser only.

Allowed output tags: h1-h4, p, pre, code, ul, ol, li,
                     table, tr, td, th, em, strong, blockquote

Usage:
    python local_ai/ingest/html_cleaner.py sample.html
    python local_ai/ingest/html_cleaner.py sample.html -o output/sample.cleaned.html
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


_ALLOWED: frozenset[str] = frozenset({
    "h1", "h2", "h3", "h4",
    "p", "pre", "code",
    "ul", "ol", "li",
    "table", "tr", "td", "th",
    "em", "strong", "blockquote",
})

# Tags whose entire subtree (including text) is discarded
_STRIP_TREE: frozenset[str] = frozenset({
    "script", "style", "svg", "iframe", "noscript",
    "button", "form", "input", "select", "textarea",
    "nav", "header", "footer",
})

# Attributes kept per-tag (everything else stripped)
_KEEP_ATTRS: dict[str, list[str]] = {
    "a":   ["href"],
    "img": ["alt", "src"],
}


class _Cleaner(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []
        self._strip_depth = 0   # >0 means we're inside a strip-tree tag
        self._in_pre = False    # preserve whitespace inside <pre>

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()

        # Inside a stripped subtree: only track nesting depth
        if self._strip_depth > 0:
            if tag in _STRIP_TREE:
                self._strip_depth += 1
            return

        if tag in _STRIP_TREE:
            self._strip_depth += 1
            return

        if tag == "pre":
            self._in_pre = True

        if tag in _ALLOWED:
            kept = ""
            for name, value in attrs:
                if name in _KEEP_ATTRS.get(tag, []) and value:
                    kept += f' {name}="{html.escape(value)}"'
            self._out.append(f"<{tag}{kept}>")

        # Unknown / layout tags (div, span, section, …): skip the tag, keep content

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if self._strip_depth > 0:
            if tag in _STRIP_TREE:
                self._strip_depth -= 1
            return

        if tag == "pre":
            self._in_pre = False

        if tag in _ALLOWED:
            self._out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self._strip_depth > 0:
            return
        if self._in_pre:
            # Preserve all whitespace inside pre; escape for HTML safety
            self._out.append(html.escape(data))
        else:
            text = " ".join(data.split())
            if text:
                self._out.append(html.escape(text))

    def result(self) -> str:
        return "".join(self._out)


def _post_process(raw: str) -> str:
    """Remove empty tags and add whitespace for readability."""
    # Remove empty block elements
    for tag in ("p", "h1", "h2", "h3", "h4", "li", "td", "th", "blockquote"):
        raw = re.sub(rf"<{tag}>\s*</{tag}>", "", raw, flags=re.IGNORECASE)

    # Newline after closing block tags
    for tag in ("h1", "h2", "h3", "h4", "p", "pre", "ul", "ol", "li",
                "table", "tr", "td", "th", "blockquote"):
        raw = raw.replace(f"</{tag}>", f"</{tag}>\n")
        raw = raw.replace(f"<{tag}>", f"\n<{tag}>")

    # Collapse runs of blank lines
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def clean_html(input_path: Path, output_path: Path | None = None) -> Path:
    """Strip layout noise from HTML, keeping only semantic tags."""
    if not input_path.exists():
        raise FileNotFoundError(f"HTML file not found: {input_path}")

    if output_path is None:
        stem = input_path.stem
        suffix = ".cleaned.html" if not stem.endswith(".cleaned") else ".html"
        output_path = input_path.with_name(stem + suffix)

    raw = input_path.read_text(encoding="utf-8", errors="replace")

    # Extract title before stripping
    title_m = re.search(r"<title[^>]*>(.*?)</title>", raw, re.IGNORECASE | re.DOTALL)
    title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip() if title_m else input_path.stem

    parser = _Cleaner()
    parser.feed(raw)
    body = _post_process(parser.result())

    cleaned = (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="UTF-8">\n'
        f'<title>{html.escape(title)}</title>\n'
        '</head>\n<body>\n'
        f'{body}\n'
        '</body>\n</html>\n'
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(cleaned, encoding="utf-8")
    print(f"  cleaned → {output_path}", file=sys.stderr)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean messy HTML into simplified semantic HTML"
    )
    parser.add_argument("input", help="Input HTML file")
    parser.add_argument("-o", "--output", help="Output cleaned HTML file")
    args = parser.parse_args()

    try:
        result = clean_html(
            Path(args.input),
            Path(args.output) if args.output else None,
        )
        print(result)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
