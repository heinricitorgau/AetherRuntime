#!/usr/bin/env python3
"""Generate outputs for concept_summary records with empty output.

Reads : local_ai/training_quality/reports/semantic_accepted.jsonl
Writes: local_ai/training_quality/reports/semantic_accepted_filled.jsonl
        local_ai/training_quality/reports/fill_concept_summary_report.json

Does NOT mutate the original semantic_accepted.jsonl.

Usage:
    python local_ai/training_quality/fill_concept_summaries.py
    python local_ai/training_quality/fill_concept_summaries.py --skip-existing

Env:
    CLAW_MODEL                  model name (default: qwen2.5-coder:3b)
    CLAW_CONCEPT_MAX_TOKENS     max tokens per response (default: 384)
    CLAW_CONCEPT_TIMEOUT_SECONDS request timeout in seconds (default: 120)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from _common import now_iso

_DEFAULT_PROXY     = "http://127.0.0.1:8082"
_DEFAULT_MODEL     = "qwen2.5-coder:3b"
_DEFAULT_TOKENS    = 384
_DEFAULT_TIMEOUT   = 120

_SYSTEM = "You are a concise C programming tutor. Explain clearly and briefly."

_USER_PREFIX = (
    "Summarize this C programming material for a beginner.\n"
    "Focus on key concepts, common mistakes, and one short example if useful.\n\n"
    "Content:\n"
)


# ── Proxy call ─────────────────────────────────────────────────────────────

def _call_proxy(
    proxy_url: str,
    model: str,
    content: str,
    max_tokens: int,
    timeout: int,
) -> tuple[str, str | None]:
    """Return (text, error_message). error_message is None on success."""
    payload = json.dumps({
        "model":      model,
        "max_tokens": max_tokens,
        "system":     _SYSTEM,
        "messages":   [{"role": "user", "content": _USER_PREFIX + content}],
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{proxy_url.rstrip('/')}/v1/messages",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        parts = body.get("content", [])
        text = "".join(b.get("text", "") for b in parts if b.get("type") == "text")
        return text.strip(), None
    except urllib.error.URLError as exc:
        return "", f"proxy unreachable: {exc}"
    except Exception as exc:
        return "", str(exc)[:200]


# ── Content extraction ─────────────────────────────────────────────────────

def _content_for_prompt(rec: dict) -> str:
    """Extract the meaningful content from a concept_summary record."""
    instruction = rec.get("instruction", "").strip()
    # The instruction already has a prefix like "Summarize the following C programming concept\n..."
    # Extract just the actual content after the prefix line
    lines = instruction.splitlines()
    # Skip leading instruction lines (up to and including a blank line separator)
    content_lines: list[str] = []
    past_prefix = False
    for line in lines:
        if not past_prefix and (
            line.startswith("Summarize") or
            line.startswith("Explain") or
            line.strip() == ""
        ):
            if line.strip() == "" and content_lines:
                past_prefix = True
            continue
        content_lines.append(line)
        past_prefix = True

    content = "\n".join(content_lines).strip()
    return content if content else instruction


# ── Main ───────────────────────────────────────────────────────────────────

def fill(
    input_path: Path,
    out_path:   Path,
    proxy_url:  str,
    model:      str,
    max_tokens: int,
    timeout:    int,
    skip_existing: bool,
) -> dict:
    records = [
        json.loads(l)
        for l in input_path.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]

    need_fill = [
        r for r in records
        if r.get("type") == "concept_summary" and not r.get("output", "").strip()
    ]
    already_filled = [
        r for r in records
        if r.get("type") == "concept_summary" and r.get("output", "").strip()
    ]

    print(f"Input:   {input_path.name}  ({len(records)} records)")
    print(f"Proxy:   {proxy_url}  model={model}  max_tokens={max_tokens}")
    print(f"Need fill: {len(need_fill)}  already filled: {len(already_filled)}\n")

    filled_ids:  list[str] = []
    failed_ids:  list[str] = []
    skipped_ids: list[str] = []

    # Build output as a copy; patch the filled records in-place
    output_map = {r["id"]: dict(r) for r in records}

    for i, rec in enumerate(need_fill, 1):
        rec_id  = rec["id"]
        prefix  = f"[{i:02d}/{len(need_fill)}] {rec_id}"

        # Skip if already in output_map with a filled output (--skip-existing)
        existing = output_map[rec_id].get("output", "").strip()
        if skip_existing and existing:
            print(f"{prefix}  skip (already filled)")
            skipped_ids.append(rec_id)
            continue

        content = _content_for_prompt(rec)
        print(f"{prefix}  generating ({len(content)} chars)...", end="", flush=True)

        text, err = _call_proxy(proxy_url, model, content, max_tokens, timeout)
        if err or not text:
            print(f"  FAILED: {err or 'empty response'}")
            failed_ids.append(rec_id)
            continue

        # Patch the record
        output_map[rec_id]["output"]      = text
        output_map[rec_id]["messages"][2]["content"] = text
        print(f"  ok  ({len(text)} chars)")
        filled_ids.append(rec_id)

    # Write filled JSONL (preserve original ordering)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(output_map[rec["id"]], ensure_ascii=False) + "\n")

    report = {
        "timestamp":   now_iso(),
        "input":       str(input_path),
        "output":      str(out_path),
        "model":       model,
        "max_tokens":  max_tokens,
        "total":       len(records),
        "need_fill":   len(need_fill),
        "filled":      len(filled_ids),
        "skipped":     len(skipped_ids),
        "failed":      len(failed_ids),
        "filled_ids":  filled_ids,
        "skipped_ids": skipped_ids,
        "failed_ids":  failed_ids,
    }

    report_path = out_path.parent / "fill_concept_summary_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nFilled:  {len(filled_ids)}  skipped: {len(skipped_ids)}  failed: {len(failed_ids)}")
    print(f"Output:  {out_path}")
    print(f"Report:  {report_path}")
    return report


def main() -> None:
    default_input  = _HERE / "reports" / "semantic_accepted.jsonl"
    default_output = _HERE / "reports" / "semantic_accepted_filled.jsonl"

    parser = argparse.ArgumentParser(
        description="Generate outputs for concept_summary records"
    )
    parser.add_argument("--input",    default=str(default_input))
    parser.add_argument("--output",   default=str(default_output))
    parser.add_argument("--proxy-url", default=_DEFAULT_PROXY)
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip records that already have output filled")
    args = parser.parse_args()

    model      = os.environ.get("CLAW_MODEL", "").strip()  or _DEFAULT_MODEL
    max_tokens = int(os.environ.get("CLAW_CONCEPT_MAX_TOKENS", _DEFAULT_TOKENS))
    timeout    = int(os.environ.get("CLAW_CONCEPT_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT))

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    fill(
        input_path     = input_path,
        out_path       = Path(args.output),
        proxy_url      = args.proxy_url,
        model          = model,
        max_tokens     = max_tokens,
        timeout        = timeout,
        skip_existing  = args.skip_existing,
    )


if __name__ == "__main__":
    main()
