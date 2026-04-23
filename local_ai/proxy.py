#!/usr/bin/env python3
"""
local_ai/proxy.py
─────────────────
Anthropic API ↔ Ollama (OpenAI-compat) 格式轉換代理。
純 Python 標準庫，無需安裝任何套件。

claw 以 Anthropic 格式呼叫 → 本代理轉換 → Ollama 本地模型回應
→ 轉回 Anthropic 格式 → claw 收到回應

用法（通常由 run.sh 呼叫）：
    python3 local_ai/proxy.py --model llama3.2 --port 8082 --ollama-url http://localhost:11434
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import URLError
from urllib.request import Request, urlopen


# ── 設定 ──────────────────────────────────────────────────────────────────────

DEFAULT_PORT = 8082
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"
DEFAULT_SYSTEM_PROMPT = (
    "你是離線終端機助理。"
    "請全程只使用繁體中文回答，不要混用英文、日文、韓文、越南文或其他語言。"
    "不要自己切換語言，也不要詢問是否要改用別的語言。"
    "請直接在對話中輸出答案，不要主動建立、修改或輸出成檔案，除非使用者明確要求你這樣做。"
    "如果使用者要求寫程式，請直接給正確答案。"
    "如果使用者沒有明確指定程式語言，預設輸出 C 語言程式。"
    "如果使用者已經指定 Python、Java、C++ 或其他語言，就照使用者指定的語言回答。"
    "如果題目很簡單，例如要求輸出 1，請直接提供最短、正確的 C 程式。"
    "不要離題，不要自我對話，不要補無關說明。"
    "如果使用者沒有特別指定格式，請優先用清楚、直接、適合終端機閱讀的方式回覆。"
)

PROGRAMMING_KEYWORDS = (
    "write a program",
    "write a c program",
    "program",
    "code",
    "coding",
    "function",
    "array",
    "matrix",
    "sort",
    "struct",
    "read n",
    "generate",
    "c語言",
    "程式",
    "寫一個程式",
    "寫程式",
    "函式",
    "陣列",
    "排序",
    "讀檔",
    "輸出",
)

LANGUAGE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("c", ("c語言", " c language", " in c", "write a c program", "language c")),
    ("c++", ("c++", "cpp", "c plus plus")),
    ("python", ("python", "py ")),
    ("java", ("java",)),
    ("javascript", ("javascript", "js ")),
    ("go", ("golang", "go language", " in go")),
    ("rust", ("rust",)),
)


# ── Anthropic → OpenAI 格式轉換 ───────────────────────────────────────────────

def _flatten_message_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type", "")
            if btype == "text":
                parts.append(str(block.get("text", "")))
            elif btype == "tool_result":
                inner = block.get("content", [])
                if isinstance(inner, str):
                    parts.append(inner)
                elif isinstance(inner, list):
                    for inner_block in inner:
                        if isinstance(inner_block, dict) and inner_block.get("type") == "text":
                            parts.append(str(inner_block.get("text", "")))
        return "\n".join(parts)
    return ""


def _latest_user_text(body: dict) -> str:
    for msg in reversed(body.get("messages", [])):
        if msg.get("role") == "user":
            return _flatten_message_content(msg.get("content", ""))
    return ""


def _looks_like_programming_request(text: str) -> bool:
    lowered = f" {text.lower()} "
    if any(keyword in lowered for keyword in PROGRAMMING_KEYWORDS):
        return True
    return bool(re.search(r"\b(int|double|float|printf|scanf|main|struct|typedef)\b", lowered))


def _detect_explicit_language(text: str) -> str | None:
    lowered = f" {text.lower()} "
    for language, patterns in LANGUAGE_PATTERNS:
        if any(pattern in lowered for pattern in patterns):
            return language
    return None


def _programming_mode_instruction(user_text: str) -> str | None:
    if not _looks_like_programming_request(user_text):
        return None
    explicit_language = _detect_explicit_language(user_text)
    if explicit_language in (None, "c"):
        return (
            "這是一題程式設計題。"
            "請直接輸出一份完整、可編譯、可執行的 C 語言程式。"
            "除非使用者明確要求說明，否則只輸出一個 ```c 程式碼區塊，不要加前言、結語、道歉或多餘解釋。"
            "不要輸出偽代碼，不要輸出錯誤或未完成的程式。"
        )
    return (
        f"這是一題程式設計題。使用者已指定 {explicit_language}。"
        f"請直接輸出一份完整、可執行的 {explicit_language} 程式。"
        "除非使用者明確要求說明，否則只輸出一個程式碼區塊，不要加前言、結語或多餘解釋。"
    )


def anthropic_to_openai(body: dict, model: str, default_system_prompt: str | None = None) -> dict:
    """將 Anthropic /v1/messages 請求轉換為 OpenAI /v1/chat/completions 格式。"""
    messages: list[dict] = []

    # system prompt
    system = body.get("system")
    system_parts: list[str] = []
    if system:
        if isinstance(system, list):
            text = " ".join(b.get("text", "") for b in system if isinstance(b, dict))
        else:
            text = str(system)
        if text.strip():
            system_parts.append(text.strip())
    if default_system_prompt and default_system_prompt.strip():
        system_parts.append(default_system_prompt.strip())
    programming_instruction = _programming_mode_instruction(_latest_user_text(body))
    if programming_instruction:
        system_parts.append(programming_instruction)
    if system_parts:
        messages.append({"role": "system", "content": "\n\n".join(system_parts)})

    # 歷史訊息
    for msg in body.get("messages", []):
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, str):
            messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            # 把所有 text 塊合併；tool_result/tool_use 簡化為文字
            parts: list[str] = []
            for block in content:
                btype = block.get("type", "")
                if btype == "text":
                    parts.append(block.get("text", ""))
                elif btype == "tool_result":
                    inner = block.get("content", [])
                    if isinstance(inner, list):
                        for ib in inner:
                            if ib.get("type") == "text":
                                parts.append(f"[Tool result] {ib.get('text','')}")
                    elif isinstance(inner, str):
                        parts.append(f"[Tool result] {inner}")
                elif btype == "tool_use":
                    inp = json.dumps(block.get("input", {}))
                    parts.append(f"[Tool call: {block.get('name','')}({inp})]")
            messages.append({"role": role, "content": "\n".join(parts)})

    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": body.get("stream", False),
    }
    if "max_tokens" in body:
        payload["max_tokens"] = body["max_tokens"]
    if "temperature" in body:
        payload["temperature"] = body["temperature"]
    else:
        payload["temperature"] = 0.1

    return payload


# ── OpenAI → Anthropic 格式轉換（非串流）────────────────────────────────────

def openai_to_anthropic(oai: dict, model: str) -> dict:
    """將 OpenAI chat.completion 回應轉換為 Anthropic Messages 格式。"""
    msg_id = "msg_" + uuid.uuid4().hex[:24]
    choice = oai.get("choices", [{}])[0]
    content_text = choice.get("message", {}).get("content", "")
    finish = choice.get("finish_reason", "stop")
    stop_reason = "end_turn" if finish in ("stop", None) else finish

    usage = oai.get("usage", {})
    return {
        "id": msg_id,
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": content_text}],
        "model": model,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


# ── SSE 串流轉換 ──────────────────────────────────────────────────────────────

def stream_openai_to_anthropic(ollama_response, model: str):
    """
    把 Ollama 的 OpenAI-compat SSE 串流轉換為 Anthropic SSE 串流。
    每次 yield 一行已編碼的 bytes。
    """
    msg_id = "msg_" + uuid.uuid4().hex[:24]

    def sse_line(event: str, data: dict) -> bytes:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()

    # message_start
    yield sse_line("message_start", {
        "type": "message_start",
        "message": {
            "id": msg_id, "type": "message", "role": "assistant",
            "content": [], "model": model,
            "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }
    })
    # content_block_start
    yield sse_line("content_block_start", {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "text", "text": ""},
    })
    yield b"event: ping\ndata: {\"type\":\"ping\"}\n\n"

    output_tokens = 0
    finish_reason = "end_turn"

    for raw_line in ollama_response:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line or not line.startswith("data: "):
            continue
        payload_str = line[6:]
        if payload_str == "[DONE]":
            break
        try:
            chunk = json.loads(payload_str)
        except json.JSONDecodeError:
            continue

        choices = chunk.get("choices", [])
        if not choices:
            continue
        delta = choices[0].get("delta", {})
        text_delta = delta.get("content", "")
        fr = choices[0].get("finish_reason")
        if fr:
            finish_reason = "end_turn" if fr in ("stop", None) else fr

        if text_delta:
            output_tokens += 1
            yield sse_line("content_block_delta", {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": text_delta},
            })

    # content_block_stop
    yield sse_line("content_block_stop", {"type": "content_block_stop", "index": 0})
    # message_delta
    yield sse_line("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": finish_reason, "stop_sequence": None},
        "usage": {"output_tokens": output_tokens},
    })
    # message_stop
    yield sse_line("message_stop", {"type": "message_stop"})


# ── HTTP 請求處理器 ───────────────────────────────────────────────────────────

class ProxyHandler(BaseHTTPRequestHandler):
    """處理所有 HTTP 請求的代理。"""

    ollama_url: str = DEFAULT_OLLAMA_URL
    local_model: str = DEFAULT_MODEL
    default_system_prompt: str = DEFAULT_SYSTEM_PROMPT

    def log_message(self, fmt: str, *args) -> None:  # 簡化日誌
        sys.stderr.write(f"[proxy] {fmt % args}\n")

    def do_GET(self) -> None:  # noqa: N802
        """健康檢查端點。"""
        if self.path in ("/health", "/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "model": self.local_model}).encode())
        else:
            self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        if self.path in ("/v1/messages",):
            self._handle_messages(body)
        else:
            self.send_error(404, f"Unknown endpoint: {self.path}")

    def _handle_messages(self, body: dict) -> None:
        streaming = body.get("stream", False)
        oai_payload = anthropic_to_openai(body, self.local_model, self.default_system_prompt)
        oai_json = json.dumps(oai_payload).encode()

        req = Request(
            f"{self.ollama_url}/v1/chat/completions",
            data=oai_json,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer ollama",
            },
            method="POST",
        )

        try:
            if streaming:
                self._stream_response(req, body.get("model", self.local_model))
            else:
                self._sync_response(req, body.get("model", self.local_model))
        except URLError as exc:
            sys.stderr.write(f"[proxy] Ollama 連線失敗：{exc}\n")
            self.send_error(502, "Ollama 無法連線，請確認 Ollama 正在執行")

    def _sync_response(self, req: Request, model: str) -> None:
        with urlopen(req, timeout=120) as resp:
            oai_data = json.loads(resp.read())
        result = openai_to_anthropic(oai_data, model)
        body_bytes = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def _stream_response(self, req: Request, model: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        with urlopen(req, timeout=120) as resp:
            try:
                for chunk in stream_openai_to_anthropic(resp, model):
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except BrokenPipeError:
                sys.stderr.write("[proxy] client disconnected during stream\n")


# ── 主程式 ────────────────────────────────────────────────────────────────────

def wait_for_ollama(ollama_url: str, timeout: int = 30) -> bool:
    """等待 Ollama 服務啟動，回傳是否成功。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(f"{ollama_url}/api/tags", timeout=2):
                return True
        except Exception:
            time.sleep(1)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Anthropic ↔ Ollama 代理")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama 模型名稱")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="代理監聽埠")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama 服務 URL")
    parser.add_argument(
        "--system-prompt",
        default=DEFAULT_SYSTEM_PROMPT,
        help="附加到每次請求的預設 system prompt",
    )
    args = parser.parse_args()

    ProxyHandler.ollama_url = args.ollama_url
    ProxyHandler.local_model = args.model
    ProxyHandler.default_system_prompt = args.system_prompt

    sys.stderr.write(f"[proxy] 等待 Ollama 啟動（{args.ollama_url}）...\n")
    if not wait_for_ollama(args.ollama_url):
        sys.stderr.write("[proxy] 錯誤：無法連線到 Ollama，請先執行 ollama serve\n")
        sys.exit(1)

    server = HTTPServer(("127.0.0.1", args.port), ProxyHandler)
    sys.stderr.write(
        f"[proxy] 就緒 ─ 監聽 localhost:{args.port}  →  Ollama({args.model})\n"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\n[proxy] 關閉\n")


if __name__ == "__main__":
    main()
