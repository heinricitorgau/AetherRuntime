# ── local_ai/Dockerfile ──────────────────────────────────────────────────────
# 一個容器同時跑 Ollama + proxy + claw（完全離線）
#
# 建置（首次需要網路下載模型）：
#   docker build --build-arg MODEL=llama3.2 -t claw-local .
#
# 執行（之後完全離線）：
#   docker run -it --rm claw-local
#
# 若要保留已下載的模型（加速重建）：
#   docker run -it --rm -v ollama_data:/root/.ollama claw-local

# ── Stage 1：建置 Rust claw 二進位 ───────────────────────────────────────────
FROM rust:1.78-slim AS builder

WORKDIR /build
COPY rust/ rust/

RUN cd rust && cargo build --workspace --release 2>&1

# ── Stage 2：最終映像 ──────────────────────────────────────────────────────────
FROM ubuntu:22.04

ARG MODEL=llama3.2
ENV MODEL=${MODEL}
ENV PROXY_PORT=8082
ENV OLLAMA_URL=http://localhost:11434
ENV ANTHROPIC_BASE_URL=http://localhost:8082
ENV ANTHROPIC_API_KEY=local-ollama
ENV DEBIAN_FRONTEND=noninteractive

# 安裝基本工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安裝 Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# 複製 claw 二進位
COPY --from=builder /build/rust/target/release/claw /usr/local/bin/claw
RUN chmod +x /usr/local/bin/claw

# 複製 proxy
WORKDIR /app
COPY local_ai/proxy.py local_ai/proxy.py

# 複製啟動腳本
COPY local_ai/docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 預先拉取模型（建置時下載，映像內含模型，之後完全離線）
# 注意：這會讓映像變大（Llama3.2 約 2 GB），但確保完全離線
RUN ollama serve & \
    sleep 5 && \
    ollama pull ${MODEL} && \
    pkill ollama || true

VOLUME ["/root/.ollama"]

ENTRYPOINT ["/entrypoint.sh"]
