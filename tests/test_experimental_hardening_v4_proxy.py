#!/usr/bin/env python3
"""
test_proxy_experimental.py
──────────────────────────
實驗性測試 local_ai/proxy.py 在近期修正後的行為。

涵蓋：
  1. 純函式單元測試（語言偵測、C 靜態檢查、SSE 產生器、格式轉換）
  2. 錯誤路徑（UTF-8 繁中錯誤訊息）
  3. End-to-end：真正啟動 proxy.py，針對本機假 Ollama 發 /v1/messages 請求
     a. 非串流
     b. 串流（驗證真 SSE 傳遞而不是模擬）
     c. C 題修復流程（假 Ollama 第一次回 C++，第二次回正確 C）

由 Python 標準庫完成，不需要 Ollama、不需要網路。
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
PROXY_PY = PROJECT_DIR / "local_ai" / "proxy.py"

sys.path.insert(0, str(PROJECT_DIR / "local_ai"))
import proxy  # noqa: E402


# ────────────────────────────────────────────────────────────────────────────
# 純函式單元測試
# ────────────────────────────────────────────────────────────────────────────

class TestLanguageDetection(unittest.TestCase):
    def test_explicit_python(self):
        self.assertEqual(
            proxy._detect_programming_language("請用 Python 寫一個程式"), "python"
        )

    def test_explicit_java(self):
        self.assertEqual(
            proxy._detect_programming_language("write a java program"), "java"
        )

    def test_explicit_cpp_not_confused_with_c(self):
        self.assertEqual(
            proxy._detect_programming_language("write a c++ program"), "c++"
        )

    def test_default_falls_back_to_c(self):
        self.assertEqual(
            proxy._detect_programming_language("請寫一個程式輸出 1"), "c"
        )

    def test_non_programming_returns_none(self):
        self.assertIsNone(proxy._detect_programming_language("今天天氣怎麼樣？"))


class TestStaticCCheck(unittest.TestCase):
    def _block(self, code_lang: str, code: str) -> tuple[bool, str]:
        text = f"```{code_lang}\n{code}\n```"
        return proxy._static_check_c_code(text)

    def test_accepts_minimal_valid_c(self):
        ok, err = self._block("c", "#include <stdio.h>\nint main(void){printf(\"1\\n\");return 0;}")
        self.assertTrue(ok, f"expected pass, got err={err!r}")

    def test_rejects_cout(self):
        ok, err = self._block("c", "#include <iostream>\nusing namespace std;\nint main(){cout<<1;}")
        self.assertFalse(ok)
        self.assertIn("cout", err)

    def test_rejects_std_namespace(self):
        ok, err = self._block(
            "c",
            "#include <iostream>\nint main(){std::cout<<1;return 0;}",
        )
        self.assertFalse(ok)

    def test_rejects_vector_template(self):
        ok, err = self._block(
            "c",
            "#include <vector>\nint main(){vector<int> v;return 0;}",
        )
        self.assertFalse(ok)

    def test_missing_main_fails(self):
        ok, err = self._block("c", "void helper(void){}")
        self.assertFalse(ok)
        self.assertIn("main", err)


class TestSeriesMathCheck(unittest.TestCase):
    prompt = "請用 C 寫一個程式計算交錯階乘級數 1/1! - 2/2! + 3/3! ..."

    def test_hello_world_rejected_for_series(self):
        text = "```c\n#include <stdio.h>\nint main(void){printf(\"Hello, World!\\n\");return 0;}\n```"
        # 透過 _compile_check_c_code 確保 Hello World 在程式題被擋
        ok, err = proxy._compile_check_c_code(self.prompt, text)
        self.assertFalse(ok)

    def test_missing_factorial_rejected(self):
        text = (
            "```c\n#include <stdio.h>\nint main(void){int s=0;"
            "for(int i=1;i<=10;i++)s+=i;printf(\"%d\\n\",s);return 0;}\n```"
        )
        ok, err = proxy._check_series_math_c_code(self.prompt, text)
        self.assertFalse(ok)


class TestSendJsonErrorBytes(unittest.TestCase):
    def test_chinese_round_trip_utf8(self):
        msg = "Ollama 連線失敗：請先執行 ollama serve"
        body = json.dumps({"error": msg}, ensure_ascii=False).encode("utf-8")
        decoded = json.loads(body.decode("utf-8"))
        self.assertEqual(decoded["error"], msg)
        # 核心保證：輸出位元組內應看到真的 UTF-8 中文，不是 \u 跳脫
        self.assertIn(msg.encode("utf-8"), body)

    def test_old_behavior_would_escape(self):
        # 如果退回到 ensure_ascii=True 會變什麼，反面驗證
        msg = "繁體中文"
        body = json.dumps({"error": msg}, ensure_ascii=True).encode("utf-8")
        self.assertNotIn(msg.encode("utf-8"), body)  # 舊行為：不是 UTF-8


class TestSseGenerators(unittest.TestCase):
    def test_text_to_anthropic_sse_event_order(self):
        events = list(proxy.text_to_anthropic_sse("你好", "qwen2.5-coder:14b"))
        types = []
        for chunk in events:
            line = chunk.decode("utf-8")
            for part in line.split("\n"):
                if part.startswith("event: "):
                    types.append(part[len("event: "):])
        self.assertEqual(
            types,
            [
                "message_start",
                "content_block_start",
                "content_block_delta",
                "content_block_stop",
                "message_delta",
                "message_stop",
            ],
        )

    def test_text_to_anthropic_sse_preserves_chinese(self):
        events = list(proxy.text_to_anthropic_sse("繁體中文測試", "m"))
        joined = b"".join(events).decode("utf-8")
        # SSE data 行是 JSON，中文會被跳脫為 \uXXXX；反序列化應回來
        for line in joined.split("\n"):
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                if payload.get("type") == "content_block_delta":
                    self.assertEqual(payload["delta"]["text"], "繁體中文測試")


# ────────────────────────────────────────────────────────────────────────────
# End-to-end：真的啟動 proxy.py，把它指向本機假 Ollama
# ────────────────────────────────────────────────────────────────────────────

class FakeOllamaHandler(BaseHTTPRequestHandler):
    """假的 Ollama /v1/chat/completions 端點。

    - 非串流：回一次性的 chat.completion。
    - 串流：逐行送 SSE。
    - /api/tags：回空 JSON（讓 wait_for_ollama 滿足）。
    - 第一次收到 C 題（payload 中含「階乘」）時回 C++ 誘導 repair path；
      之後回正確 C。
    """

    shared_state: dict = {"c_call_count": 0}

    def log_message(self, fmt, *args):  # 靜音
        return

    def do_GET(self):  # noqa: N802
        if self.path == "/api/tags":
            self._json(200, {"models": []})
        else:
            self.send_error(404)

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        body = json.loads(raw)
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        is_stream = bool(body.get("stream", False))
        user_texts = [
            m.get("content", "") for m in body.get("messages", []) if m.get("role") == "user"
        ]
        joined = "\n".join(user_texts)
        is_c_repair_flow = "階乘" in joined or "factorial" in joined.lower()

        if is_c_repair_flow:
            self.shared_state["c_call_count"] += 1
            if self.shared_state["c_call_count"] == 1:
                content = "```c\n#include <iostream>\nusing namespace std;\nint main(){cout<<1;}\n```"
            else:
                content = (
                    "```c\n#include <stdio.h>\nint main(void){"
                    "int s=0;for(int i=1;i<=3;i++){int f=1;for(int j=1;j<=i;j++)f*=j;"
                    "s+=(i%2?1:-1)*(i*i)/f;}printf(\"%d\\n\",s);return 0;}\n```"
                )
        else:
            content = "你好，這是繁體中文測試回覆。"

        if is_stream:
            self._sse_stream(content)
        else:
            self._json(
                200,
                {
                    "id": "cmpl_x",
                    "object": "chat.completion",
                    "created": 0,
                    "model": body.get("model", "m"),
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": content},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                },
            )

    def _json(self, code: int, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _sse_stream(self, full_text: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        # 逐字分塊
        for ch in full_text:
            chunk = {
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": ch},
                        "finish_reason": None,
                    }
                ]
            }
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
            self.wfile.flush()
        done = {
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ]
        }
        self.wfile.write(f"data: {json.dumps(done)}\n\n".encode("utf-8"))
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class EndToEndProxy(unittest.TestCase):
    proxy_proc: subprocess.Popen | None = None
    fake_server: HTTPServer | None = None
    fake_thread: threading.Thread | None = None
    proxy_port: int = 0
    ollama_port: int = 0

    @classmethod
    def setUpClass(cls):
        FakeOllamaHandler.shared_state = {"c_call_count": 0}
        cls.ollama_port = _pick_free_port()
        cls.proxy_port = _pick_free_port()

        cls.fake_server = HTTPServer(
            ("127.0.0.1", cls.ollama_port), FakeOllamaHandler
        )
        cls.fake_thread = threading.Thread(target=cls.fake_server.serve_forever, daemon=True)
        cls.fake_thread.start()

        cls.proxy_proc = subprocess.Popen(
            [
                sys.executable,
                str(PROXY_PY),
                "--model", "qwen2.5-coder:14b",
                "--port", str(cls.proxy_port),
                "--ollama-url", f"http://127.0.0.1:{cls.ollama_port}",
                "--system-prompt", "請用繁體中文回答。",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{cls.proxy_port}/health", timeout=0.5
                ) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError("proxy failed to become healthy")

    @classmethod
    def tearDownClass(cls):
        if cls.proxy_proc:
            cls.proxy_proc.terminate()
            try:
                cls.proxy_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.proxy_proc.kill()
        if cls.fake_server:
            cls.fake_server.shutdown()
            cls.fake_server.server_close()

    def _post(self, path: str, payload: dict) -> urllib.request.http.client.HTTPResponse:
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.proxy_port}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return urllib.request.urlopen(req, timeout=15)

    def test_health_endpoint(self):
        with urllib.request.urlopen(
            f"http://127.0.0.1:{self.proxy_port}/health", timeout=2
        ) as resp:
            data = json.loads(resp.read())
        self.assertEqual(data["status"], "ok")

    def test_non_stream_chinese(self):
        resp = self._post(
            "/v1/messages",
            {
                "model": "qwen2.5-coder:14b",
                "messages": [{"role": "user", "content": "幫我打招呼"}],
                "stream": False,
            },
        )
        data = json.loads(resp.read())
        self.assertEqual(data["type"], "message")
        self.assertEqual(data["role"], "assistant")
        text = data["content"][0]["text"]
        self.assertIn("繁體中文", text)

    def test_unknown_endpoint_returns_utf8_chinese_error(self):
        try:
            self._post("/does-not-exist", {"x": 1})
            self.fail("expected HTTPError")
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            decoded = json.loads(raw.decode("utf-8"))
            self.assertIn("error", decoded)
            # 驗證錯誤訊息是繁中 UTF-8，不是 \u 跳脫
            self.assertIn("未知的端點", decoded["error"])
            self.assertIn("未知的端點".encode("utf-8"), raw)

    def test_invalid_json_returns_chinese_error(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.proxy_port}/v1/messages",
            data=b"this is not json{",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            self.fail("expected HTTPError")
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            decoded = json.loads(raw.decode("utf-8"))
            self.assertIn("合法的 JSON", decoded["error"])

    def test_stream_real_sse_events(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.proxy_port}/v1/messages",
            data=json.dumps(
                {
                    "model": "qwen2.5-coder:14b",
                    "messages": [{"role": "user", "content": "請打個招呼"}],
                    "stream": True,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            method="POST",
        )
        events = []
        with urllib.request.urlopen(req, timeout=15) as resp:
            for raw in resp:
                line = raw.decode("utf-8").strip()
                if line.startswith("event: "):
                    events.append(line[len("event: "):])
        self.assertEqual(events[0], "message_start")
        self.assertEqual(events[-1], "message_stop")
        self.assertIn("content_block_delta", events)

    def test_c_repair_flow_retries_on_cpp(self):
        FakeOllamaHandler.shared_state["c_call_count"] = 0
        resp = self._post(
            "/v1/messages",
            {
                "model": "qwen2.5-coder:14b",
                "messages": [
                    {
                        "role": "user",
                        "content": "請用 C 語言寫一個計算階乘級數的程式",
                    }
                ],
                "stream": False,
            },
        )
        data = json.loads(resp.read())
        final = data["content"][0]["text"]
        # 第一次 fake Ollama 回 C++（cout）；修復流程應觸發第二次呼叫並接受乾淨 C
        self.assertGreaterEqual(FakeOllamaHandler.shared_state["c_call_count"], 2)
        self.assertNotIn("cout", final)
        self.assertIn("printf", final)


if __name__ == "__main__":
    unittest.main(verbosity=2)
