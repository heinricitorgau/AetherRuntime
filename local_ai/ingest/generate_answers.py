#!/usr/bin/env python3
"""Generate reference C answers for training records via proxy AI.

Reads output/training/code_generation.jsonl, calls the proxy for each
record, extracts the C code, and writes to output/training/answers/<id>.c.

Then re-runs prepare_training.py --fill-answers and split_training.py so
the training splits have populated output fields.

Usage:
    python local_ai/ingest/generate_answers.py
    python local_ai/ingest/generate_answers.py --proxy-url http://127.0.0.1:8082
    python local_ai/ingest/generate_answers.py --model qwen2.5-coder:3b --max-tokens 1536
    python local_ai/ingest/generate_answers.py --skip-existing   # skip already-generated .c files
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path


_DEFAULT_PROXY   = "http://127.0.0.1:8082"
_DEFAULT_MODEL   = "qwen2.5-coder:3b"
_DEFAULT_TOKENS  = 1536
_DEFAULT_TIMEOUT = 120  # seconds per request

_SYSTEM = (
    "You are a C programming assistant. "
    "Output exactly one complete, compilable C99 program. "
    "Include all necessary #include directives and a main() function. "
    "Do not add explanations outside the code. "
    "Do not use markdown fences."
)


# ── Proxy call ─────────────────────────────────────────────────────────────

def call_proxy(
    proxy_url: str,
    model: str,
    instruction: str,
    max_tokens: int,
    timeout: int,
) -> str:
    """Return raw text response from proxy, or '' on error."""
    payload = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "system": _SYSTEM,
        "messages": [{"role": "user", "content": instruction}],
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
        content = body.get("content", [])
        if isinstance(content, list):
            return "".join(b.get("text", "") for b in content if b.get("type") == "text")
        return str(content)
    except urllib.error.URLError as exc:
        print(f"    proxy error: {exc}", file=sys.stderr)
        return ""
    except Exception as exc:
        print(f"    unexpected error: {exc}", file=sys.stderr)
        return ""


# ── C extraction ────────────────────────────────────────────────────────────

def _balanced_close(text: str, start: int) -> int:
    """Find the position after the closing brace matching the first '{' at or after start."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    return len(text)


def extract_c(text: str) -> str:
    """Extract a complete C program from model output."""
    # 1. Fenced code block
    m = re.search(r"```(?:c|C)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        code = m.group(1).strip()
        if "#include" in code and re.search(r"\bint\s+main\s*\(", code):
            return code

    # 2. Heuristic: find #include and main(), grab until balanced brace
    include_pos = text.find("#include")
    main_m = re.search(r"\bint\s+main\s*\(", text)
    if include_pos >= 0 and main_m:
        start = min(include_pos, main_m.start())
        # find opening brace of main
        brace_start = text.find("{", main_m.end())
        if brace_start >= 0:
            end = _balanced_close(text, brace_start)
            return text[start:end].strip()

    return ""


# ── Pipeline ────────────────────────────────────────────────────────────────

def _ingest_dir() -> Path:
    return Path(__file__).resolve().parent


def generate_answers(
    proxy_url: str,
    model: str,
    max_tokens: int,
    timeout: int,
    skip_existing: bool,
) -> dict:
    training_dir = _ingest_dir() / "output" / "training"
    input_path   = training_dir / "code_generation.jsonl"
    answers_dir  = training_dir / "answers"
    answers_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"Error: {input_path} not found – run prepare_training.py first", file=sys.stderr)
        sys.exit(1)

    records = [json.loads(l) for l in input_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"Loaded {len(records)} code_generation records")
    print(f"Proxy:  {proxy_url}  model={model}  max_tokens={max_tokens}\n")

    stats = {"total": len(records), "generated": 0, "skipped": 0, "failed": 0}

    for i, rec in enumerate(records, 1):
        case_id     = rec["id"]
        instruction = rec.get("instruction", "")
        out_path    = answers_dir / f"{case_id}.c"

        prefix = f"[{i:02d}/{len(records)}] {case_id}"

        if skip_existing and out_path.exists():
            print(f"{prefix}  skip (exists)")
            stats["skipped"] += 1
            continue

        print(f"{prefix}  generating...", end="", flush=True)
        raw = call_proxy(proxy_url, model, instruction, max_tokens, timeout)
        if not raw:
            print("  FAILED (empty response)")
            stats["failed"] += 1
            continue

        code = extract_c(raw)
        if not code:
            print("  FAILED (no C code extracted)")
            print(f"    raw tail: {raw[-200:]!r}", file=sys.stderr)
            stats["failed"] += 1
            continue

        out_path.write_text(code, encoding="utf-8")
        print(f"  ok  ({len(code)} chars)")
        stats["generated"] += 1

    print(f"\nDone: {stats['generated']} generated, {stats['skipped']} skipped, {stats['failed']} failed")
    return stats


def _rerun_pipeline(answers_dir: Path) -> None:
    here = _ingest_dir()
    print("\nRe-running prepare_training.py --fill-answers ...")
    subprocess.run(
        [sys.executable, str(here / "prepare_training.py"), "--fill-answers", str(answers_dir)],
        check=True,
    )
    print("\nRe-running split_training.py ...")
    subprocess.run(
        [sys.executable, str(here / "split_training.py")],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate C answers via proxy AI")
    parser.add_argument("--proxy-url",    default=_DEFAULT_PROXY,  help="Proxy base URL")
    parser.add_argument("--model",        default=_DEFAULT_MODEL,  help="Model name")
    parser.add_argument("--max-tokens",   type=int, default=_DEFAULT_TOKENS)
    parser.add_argument("--timeout",      type=int, default=_DEFAULT_TIMEOUT, help="Per-request timeout (s)")
    parser.add_argument("--skip-existing", action="store_true", help="Skip cases with existing .c files")
    parser.add_argument("--no-pipeline",  action="store_true", help="Don't re-run prepare/split after generation")
    args = parser.parse_args()

    stats = generate_answers(
        proxy_url=args.proxy_url,
        model=args.model,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
        skip_existing=args.skip_existing,
    )

    answers_dir = _ingest_dir() / "output" / "training" / "answers"
    if not args.no_pipeline and stats["generated"] > 0:
        _rerun_pipeline(answers_dir)
    elif stats["generated"] == 0:
        print("No new answers generated – pipeline not re-run.")


if __name__ == "__main__":
    main()
