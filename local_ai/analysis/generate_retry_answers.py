"""generate_retry_answers.py — call local model to produce corrected_output for retry records.

Reads:
    local_ai/analysis/reports/retry_needs_correction.jsonl   (or retry_training_dataset.jsonl)

Calls (two modes):
    --proxy-url  : Anthropic-format proxy (default http://127.0.0.1:8082)
                   The proxy converts to Ollama format.  Single-threaded — only one
                   concurrent request is served; new connections are refused while busy.
    --ollama-direct : Call Ollama's OpenAI-compat endpoint directly, bypassing the proxy.
                   Faster and more reliable for batch generation.
                   Default: http://127.0.0.1:11434 (override with --ollama-url)

Writes:
    local_ai/analysis/reports/retry_training_dataset.jsonl   (updated in-place with corrected_output)

After running this script, re-run package_retry_dataset.py to rebuild retry_sft_chatml.jsonl.

Usage:
    python local_ai/analysis/generate_retry_answers.py
    python local_ai/analysis/generate_retry_answers.py --ollama-direct
    python local_ai/analysis/generate_retry_answers.py --ollama-direct --ollama-url http://127.0.0.1:11434
    python local_ai/analysis/generate_retry_answers.py --proxy-url http://127.0.0.1:8082
    python local_ai/analysis/generate_retry_answers.py --max-tokens 1024
    python local_ai/analysis/generate_retry_answers.py --skip-existing
    python local_ai/analysis/generate_retry_answers.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
if str(_LOCAL_AI.parent) not in sys.path:
    sys.path.insert(0, str(_LOCAL_AI.parent))

from local_ai.shared.jsonl import read_jsonl, write_jsonl
from local_ai.analysis.package_retry_dataset import validate_c

RETRY_DATASET = _HERE / "reports" / "retry_training_dataset.jsonl"
NEEDS_FILE    = _HERE / "reports" / "retry_needs_correction.jsonl"

_DEFAULT_PROXY       = "http://127.0.0.1:8082"
_DEFAULT_OLLAMA_URL  = "http://127.0.0.1:11434"
_DEFAULT_MODEL       = "qwen2.5-coder:3b"
_DEFAULT_MAX_TOKENS  = 512   # concise solutions; reduces generation time to ~120s on 3B
_DEFAULT_TIMEOUT     = 300   # seconds per call; 512 tokens @ ~90s/384tok ≈ 120s needed

_SYSTEM = (
    "You are a C programming repair assistant. "
    "Output exactly one complete, compilable C99 program. "
    "Rules:\n"
    "1. Always include all necessary #include directives.\n"
    "2. Always include int main(void) { ... return 0; }\n"
    "3. Output only raw C code — no markdown fences, no explanations.\n"
    "4. Keep the solution as concise as possible to avoid truncation.\n"
    "5. Never use undeclared identifiers or missing headers.\n"
    "6. Ensure all braces are balanced."
)


# ── prompt builder ────────────────────────────────────────────────────────────

def _build_repair_prompt(record: dict) -> str:
    failure_type = record.get("failure_type", "unknown")
    hint         = (record.get("improvement_hint") or "").strip()
    prompt       = (record.get("original_prompt") or "").strip()
    expected     = (record.get("expected_behavior") or "").strip()
    bad_out      = (record.get("bad_output") or "").strip()

    lines: list[str] = [
        f"Fix the following failed C program.",
        f"",
        f"Failure type: {failure_type}",
        f"Repair hint:  {hint}",
        f"",
    ]

    if expected:
        lines += [f"Expected behavior: {expected}", ""]

    if prompt:
        lines += ["Original problem:", prompt, ""]

    if bad_out and failure_type not in ("partial_generation", "truncation"):
        # Include bad output only if it has real code content (not proxy errors)
        if "#include" in bad_out or "int main" in bad_out:
            lines += [
                "Previous (broken) output to fix:",
                bad_out[:800],  # cap to keep prompt + completion within token budget
                "",
            ]

    lines += [
        "Write one complete, correct C99 program. "
        "Start immediately with #include. No markdown. No explanation.",
    ]
    return "\n".join(lines)


# ── proxy call ────────────────────────────────────────────────────────────────

def _call_proxy(
    proxy_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    timeout: int,
) -> str:
    """Call Anthropic-format proxy (wraps Ollama)."""
    payload = json.dumps({
        "model":      model,
        "max_tokens": max_tokens,
        "system":     _SYSTEM,
        "messages":   [{"role": "user", "content": prompt}],
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


def _call_ollama_direct(
    ollama_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    timeout: int,
) -> str:
    """Call Ollama /api/chat with streaming to avoid read-timeout on long completions.

    With stream=True, each token is sent as a JSON line as it is generated.
    The urllib timeout applies per-read, not to the total response, so generation
    can exceed `timeout` seconds without triggering a Python socket timeout as long
    as tokens keep flowing.
    """
    messages = [
        {"role": "system",  "content": _SYSTEM},
        {"role": "user",    "content": prompt},
    ]
    payload = json.dumps({
        "model":    model,
        "messages": messages,
        "stream":   True,
        "options":  {"num_predict": max_tokens, "temperature": 0.2},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{ollama_url.rstrip('/')}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        chunks: list[str] = []
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = obj.get("message", {}).get("content", "")
                if content:
                    chunks.append(content)
                if obj.get("done"):
                    break
        return "".join(chunks)
    except urllib.error.URLError as exc:
        print(f"    ollama error: {exc}", file=sys.stderr)
        return ""
    except Exception as exc:
        print(f"    unexpected error: {exc}", file=sys.stderr)
        return ""


# ── C extractor ───────────────────────────────────────────────────────────────

def _extract_c(text: str) -> str:
    """Pull out a C program from model output (strip fences, find main)."""
    # 1. fenced block
    m = re.search(r"```(?:c|C)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        code = m.group(1).strip()
        if "#include" in code:
            return code

    # 2. raw — starts with #include
    if text.lstrip().startswith("#include"):
        return text.strip()

    # 3. heuristic: locate #include and int main
    inc = text.find("#include")
    mm  = re.search(r"\bint\s+main\s*\(", text)
    if inc >= 0 and mm:
        start = min(inc, mm.start())
        brace = text.find("{", mm.end())
        if brace >= 0:
            depth = 0
            for i in range(brace, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        return text[start:i + 1].strip()

    return text.strip()


# ── main ──────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate corrected C outputs for retry dataset")
    p.add_argument("--proxy-url",      default=_DEFAULT_PROXY,
                   help=f"Anthropic-format proxy URL (default: {_DEFAULT_PROXY})")
    p.add_argument("--ollama-direct",  action="store_true",
                   help="Call Ollama /api/chat directly instead of through the proxy. "
                        "Faster for batch generation; avoids proxy single-thread bottleneck.")
    p.add_argument("--ollama-url",     default=_DEFAULT_OLLAMA_URL,
                   help=f"Ollama base URL used with --ollama-direct (default: {_DEFAULT_OLLAMA_URL})")
    p.add_argument("--model",          default=_DEFAULT_MODEL)
    p.add_argument("--max-tokens",     type=int, default=_DEFAULT_MAX_TOKENS)
    p.add_argument("--timeout",        type=int, default=_DEFAULT_TIMEOUT)
    p.add_argument("--skip-existing",  action="store_true",
                   help="Skip records that already have a corrected_output")
    p.add_argument("--dry-run",        action="store_true",
                   help="Print prompts without calling proxy or Ollama")
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    if not RETRY_DATASET.exists():
        print(f"[gen_answers] ERROR: {RETRY_DATASET} not found. Run generate_retry_dataset.py first.")
        sys.exit(1)

    all_records = read_jsonl(RETRY_DATASET)
    print(f"[gen_answers] Loaded {len(all_records)} records from retry_training_dataset.jsonl")

    # Determine which records need correction
    to_process = [
        r for r in all_records
        if not args.skip_existing or not (r.get("corrected_output") or "").strip()
    ]
    print(f"[gen_answers] {len(to_process)} records to process")

    if args.dry_run:
        for r in to_process:
            print(f"\n{'='*60}")
            print(f"ID: {r.get('meta', {}).get('task_id')}  failure={r.get('failure_type')}")
            print(_build_repair_prompt(r)[:400])
        return

    mode = "ollama-direct" if args.ollama_direct else "proxy"
    print(f"[gen_answers] Using {mode} backend")

    # Warm up the model — the first Ollama call loads the model into VRAM (60-120s).
    # Subsequent calls are fast (3-10s each).  Fire a tiny warm-up before the real loop
    # so the per-record timeout budget is not consumed by cold-start.
    if args.ollama_direct:
        print("[gen_answers] Warming up model (first call loads VRAM) …", end="", flush=True)
        t0 = time.time()
        _ = _call_ollama_direct(
            args.ollama_url, args.model,
            "Write one line of C: int main(void){return 0;}",
            max_tokens=20, timeout=args.timeout,
        )
        print(f" {time.time()-t0:.1f}s  (model warm)")


    # index by (task_id, model) for in-place update
    index: dict[tuple, dict] = {}
    for r in all_records:
        key = (r.get("meta", {}).get("task_id", ""), r.get("meta", {}).get("model", ""))
        index[key] = r

    ok_count = skip_count = fail_count = 0

    for i, record in enumerate(to_process, 1):
        task_id = record.get("meta", {}).get("task_id", f"record_{i}")
        ftype   = record.get("failure_type", "?")
        print(f"\n[{i}/{len(to_process)}] {task_id}  ({ftype})")

        if args.skip_existing and (record.get("corrected_output") or "").strip():
            print(f"  [skip] already has corrected_output")
            skip_count += 1
            continue

        repair_prompt = _build_repair_prompt(record)
        label = "ollama" if args.ollama_direct else "proxy"
        print(f"  calling {label} …", end="", flush=True)
        t0 = time.time()
        if args.ollama_direct:
            raw = _call_ollama_direct(
                args.ollama_url, args.model, repair_prompt, args.max_tokens, args.timeout
            )
        else:
            raw = _call_proxy(
                args.proxy_url, args.model, repair_prompt, args.max_tokens, args.timeout
            )
        elapsed = time.time() - t0
        print(f" {elapsed:.1f}s")

        if not raw:
            print(f"  [FAIL] empty response from proxy")
            fail_count += 1
            continue

        code = _extract_c(raw)
        if not code:
            print(f"  [FAIL] could not extract C code from response")
            fail_count += 1
            continue

        violations = validate_c(code)
        if violations:
            print(f"  [WARN] validation failed: {violations}")
            print(f"  keeping output anyway (will be filtered by package_retry_dataset.py)")

        # Update record in-place
        key = (task_id, record.get("meta", {}).get("model", ""))
        if key in index:
            index[key]["corrected_output"] = code
            index[key]["correction_violations"] = violations
        ok_count += 1
        short = code[:80].replace("\n", " ")
        print(f"  [OK]  {len(code)} chars  violations={violations}  preview: {short}…")

    # Write back updated dataset
    updated = list(index.values())
    write_jsonl(RETRY_DATASET, updated)

    print(f"\n[gen_answers] Done.  ok={ok_count}  skip={skip_count}  fail={fail_count}")
    print(f"  Updated: {RETRY_DATASET}")
    print(f"\n  Run package_retry_dataset.py to rebuild retry_sft_chatml.jsonl")


if __name__ == "__main__":
    main()
