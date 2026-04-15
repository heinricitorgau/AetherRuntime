#!/usr/bin/env bash
# Docker 容器啟動腳本
set -euo pipefail

# 啟動 Ollama
ollama serve >/tmp/ollama.log 2>&1 &

# 等待 Ollama 就緒
for i in $(seq 1 30); do
    if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

# 啟動 proxy（背景）
python3 /app/local_ai/proxy.py \
    --model "${MODEL}" \
    --port "${PROXY_PORT}" \
    --ollama-url "${OLLAMA_URL}" \
    >/tmp/claw-proxy.log 2>&1 &

# 等待 proxy 就緒
for i in $(seq 1 10); do
    if curl -sf "http://localhost:${PROXY_PORT}/health" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

echo "✓ 本地 AI 就緒（模型: ${MODEL}，完全離線）"

# 啟動 claw
exec claw "$@"
