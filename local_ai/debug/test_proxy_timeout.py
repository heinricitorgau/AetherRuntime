#!/usr/bin/env python3
"""Probe the proxy with one long request and report the exact timeout behavior."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request


PROXY_URL = os.environ.get("CLAW_PROXY_URL", "http://127.0.0.1:8082").rstrip("/")
MODEL = os.environ.get("CLAW_MODEL", "qwen2.5-coder:3b")
CLIENT_TIMEOUT = int(os.environ.get("CLAW_DEBUG_CLIENT_TIMEOUT_SECONDS", "360"))

LONG_PROMPT = """Write one complete C99 program that:
1. reads 200 integers,
2. sorts them,
3. prints min, max, median, mean, and a histogram,
4. validates malformed input,
5. uses helper functions,
6. includes comments explaining edge cases.

Return only code. Make the implementation complete and robust."""


def _read_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    print(f"[stress] proxy={PROXY_URL}")
    print(f"[stress] model={MODEL}")
    try:
        config = _read_json(f"{PROXY_URL}/config")
        print(f"[stress] config={json.dumps(config, sort_keys=True)}")
    except Exception as exc:
        print(f"[stress] config_read_failed={exc!r}")

    payload = json.dumps(
        {
            "model": MODEL,
            "max_tokens": 1024,
            "temperature": 0.0,
            "messages": [{"role": "user", "content": LONG_PROMPT}],
            "stream": False,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{PROXY_URL}/v1/messages",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    start = time.monotonic()
    print(f"[stress] request_start={start:.6f}")
    try:
        with urllib.request.urlopen(req, timeout=CLIENT_TIMEOUT) as resp:
            body = resp.read()
        end = time.monotonic()
        print(f"[stress] status=ok")
        print(f"[stress] elapsed_seconds={end - start:.3f}")
        print(f"[stress] response_bytes={len(body)}")
    except urllib.error.HTTPError as exc:
        end = time.monotonic()
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"[stress] status=http_error")
        print(f"[stress] http_status={exc.code}")
        print(f"[stress] elapsed_seconds={end - start:.3f}")
        print(f"[stress] detail={detail[:500]}")
    except Exception as exc:
        end = time.monotonic()
        print(f"[stress] status=client_error")
        print(f"[stress] elapsed_seconds={end - start:.3f}")
        print(f"[stress] error={exc!r}")


if __name__ == "__main__":
    main()
