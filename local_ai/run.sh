#!/usr/bin/env bash
# local_ai/run.sh
# 離線優先啟動器：
# 1. 優先使用 repo 內已打包好的 runtime
# 2. 啟動 bundled Ollama / model
# 3. 啟動 Anthropic↔OpenAI proxy（使用系統自帶 Python）
# 4. 啟動 claw CLI

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()  { printf "${CYAN}  ->${RESET} %s\n" "$1"; }
ok()    { printf "${GREEN}  ok${RESET} %s\n" "$1"; }
warn()  { printf "${YELLOW}  !!${RESET} %s\n" "$1"; }
fail()  { printf "${RED}  xx${RESET} %s\n" "$1"; exit 1; }
header(){ printf "\n${BOLD}== %s ==${RESET}\n" "$1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RUNTIME_DIR="$SCRIPT_DIR/runtime"
BIN_DIR="$RUNTIME_DIR/bin"
BUNDLED_OLLAMA_HOME="$RUNTIME_DIR/ollama-home"

MODEL="${CLAW_MODEL:-llama3.2}"
PROXY_PORT="${CLAW_PROXY_PORT:-8082}"
OLLAMA_PORT="${CLAW_OLLAMA_PORT:-11435}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:${OLLAMA_PORT}}"

PROXY_PID=""
OLLAMA_PID=""

cleanup() {
    printf "\n${BOLD}[claw-local]${RESET} shutting down...\n"
    if [[ -n "$PROXY_PID" ]]; then
        kill "$PROXY_PID" 2>/dev/null || true
        info "proxy stopped"
    fi
    if [[ -n "$OLLAMA_PID" ]]; then
        kill "$OLLAMA_PID" 2>/dev/null || true
        info "ollama stopped"
    fi
}
trap cleanup EXIT INT TERM

print_banner() {
    printf "${BOLD}"
    cat <<'BANNER'
   _____ _                    _       ___  ___
  / ____| |                  | |     / _ \|_ _|
 | |    | | __ ___      __   | |    | | | || |
 | |    | |/ _` \ \ /\ / /   | |    | |_| || |
 | |____| | (_| |\ V  V /    | |___ \___/|___|
  \_____|_|\__,_| \_/\_/     |_____| offline
BANNER
    printf "${RESET}\n"
    printf "  model: ${CYAN}%s${RESET}\n" "$MODEL"
    printf "  proxy: ${CYAN}http://127.0.0.1:%s${RESET}\n" "$PROXY_PORT"
    printf "  ollama: ${CYAN}%s${RESET}\n\n" "$OLLAMA_URL"
}

find_claw_binary() {
    if [[ -x "$BIN_DIR/claw" ]]; then
        printf "%s" "$BIN_DIR/claw"
        return 0
    fi
    if [[ -x "$PROJECT_DIR/rust/target/release/claw" ]]; then
        printf "%s" "$PROJECT_DIR/rust/target/release/claw"
        return 0
    fi
    if [[ -x "$PROJECT_DIR/rust/target/debug/claw" ]]; then
        printf "%s" "$PROJECT_DIR/rust/target/debug/claw"
        return 0
    fi
    if command -v claw >/dev/null 2>&1; then
        command -v claw
        return 0
    fi
    return 1
}

find_ollama_binary() {
    if [[ -x "$BIN_DIR/ollama" ]]; then
        printf "%s" "$BIN_DIR/ollama"
        return 0
    fi
    if command -v ollama >/dev/null 2>&1; then
        command -v ollama
        return 0
    fi
    return 1
}

ollama_is_running() {
    curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1
}

model_exists_locally() {
    local ollama_bin="$1"
    if "$ollama_bin" list 2>/dev/null | awk 'NR>1 {print $1}' | grep -Fxq "$MODEL"; then
        return 0
    fi
    return 1
}

require_runtime_hint() {
    printf "\n"
    printf "需要先準備離線 bundle，才能保證「下載資料夾後直接跑」。\n\n"
    printf "先在有網路的機器上執行：\n"
    printf "  bash deploy_local.sh\n\n"
    printf "完成後會把 claw、ollama 與模型快取打包進：\n"
    printf "  %s\n\n" "$RUNTIME_DIR"
    printf "之後把整個 research-claw-code 資料夾搬到離線機器，就能直接：\n"
    printf "  bash local_ai/run.sh\n"
}

find_python_binary() {
    if [[ -x "/usr/bin/python3" ]]; then
        printf "%s" "/usr/bin/python3"
        return 0
    fi
    if command -v python3 >/dev/null 2>&1; then
        command -v python3
        return 0
    fi
    return 1
}

bundle_os="$(uname -s)"
bundle_arch="$(uname -m)"

print_banner

header "preflight"

if ! PYTHON_BIN="$(find_python_binary)"; then
    fail "python3 not found; this bundle expects the OS built-in Python runtime"
fi
ok "python: ${PYTHON_BIN}"

if ! CLAW_BIN="$(find_claw_binary)"; then
    require_runtime_hint
    fail "cannot find claw binary"
fi
ok "claw: ${CLAW_BIN}"

if ! OLLAMA_BIN="$(find_ollama_binary)"; then
    require_runtime_hint
    fail "cannot find ollama binary"
fi
ok "ollama: ${OLLAMA_BIN}"

USE_BUNDLED_OLLAMA=0
if [[ -d "$BUNDLED_OLLAMA_HOME" ]]; then
    export OLLAMA_MODELS="${BUNDLED_OLLAMA_HOME}/models"
    USE_BUNDLED_OLLAMA=1
    ok "using bundled models: ${OLLAMA_MODELS}"
else
    warn "bundled model cache not found; falling back to system ollama cache"
fi

if [[ -f "$RUNTIME_DIR/bundle-manifest.txt" ]]; then
    expected_os="$(awk -F= '/^bundle_os=/{print $2}' "$RUNTIME_DIR/bundle-manifest.txt" | tail -n 1)"
    expected_arch="$(awk -F= '/^bundle_arch=/{print $2}' "$RUNTIME_DIR/bundle-manifest.txt" | tail -n 1)"
    if [[ -n "$expected_os" && "$bundle_os" != "$expected_os" ]]; then
        fail "bundle targets ${expected_os}, but this machine is ${bundle_os}"
    fi
    if [[ -n "$expected_arch" && "$bundle_arch" != "$expected_arch" ]]; then
        fail "bundle targets ${expected_arch}, but this machine is ${bundle_arch}"
    fi
    ok "bundle target matches this machine: ${bundle_os}/${bundle_arch}"
fi

export OLLAMA_HOST="127.0.0.1:${OLLAMA_PORT}"
BUNDLED_MODEL_MANIFEST="${BUNDLED_OLLAMA_HOME}/models/manifests/registry.ollama.ai/library/${MODEL}/latest"

header "ollama"

if [[ "$USE_BUNDLED_OLLAMA" -eq 1 ]]; then
    if ollama_is_running; then
        ok "bundled service already running at ${OLLAMA_URL}"
    else
        info "starting bundled ollama service on ${OLLAMA_URL}"
        "$OLLAMA_BIN" serve >/tmp/claw-local-ollama.log 2>&1 &
        OLLAMA_PID=$!
        for i in $(seq 1 30); do
            if ollama_is_running; then
                ok "bundled service ready in ${i}s"
                break
            fi
            sleep 1
            if [[ "$i" -eq 30 ]]; then
                fail "bundled ollama failed to start; check /tmp/claw-local-ollama.log"
            fi
        done
    fi
elif ollama_is_running; then
    ok "service already running at ${OLLAMA_URL}"
else
    info "starting ollama service"
    "$OLLAMA_BIN" serve >/tmp/claw-local-ollama.log 2>&1 &
    OLLAMA_PID=$!
    for i in $(seq 1 30); do
        if ollama_is_running; then
            ok "service ready in ${i}s"
            break
        fi
        sleep 1
        if [[ "$i" -eq 30 ]]; then
            fail "ollama failed to start; check /tmp/claw-local-ollama.log"
        fi
    done
fi

if [[ "$USE_BUNDLED_OLLAMA" -eq 1 && -f "$BUNDLED_MODEL_MANIFEST" ]]; then
    ok "bundled manifest found for model: ${MODEL}"
elif ! model_exists_locally "$OLLAMA_BIN"; then
    require_runtime_hint
    fail "model '${MODEL}' is not available locally"
fi
ok "model cached locally: ${MODEL}"

header "proxy"

if lsof -i ":${PROXY_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
    warn "port ${PROXY_PORT} already in use; assuming proxy is already running"
else
    "$PYTHON_BIN" "$SCRIPT_DIR/proxy.py" \
        --model "$MODEL" \
        --port "$PROXY_PORT" \
        --ollama-url "$OLLAMA_URL" \
        >/tmp/claw-local-proxy.log 2>&1 &
    PROXY_PID=$!
    for i in $(seq 1 10); do
        if curl -sf "http://127.0.0.1:${PROXY_PORT}/health" >/dev/null 2>&1; then
            ok "proxy ready in ${i}s"
            break
        fi
        sleep 1
        if [[ "$i" -eq 10 ]]; then
            fail "proxy failed to start; check /tmp/claw-local-proxy.log"
        fi
    done
fi

header "launch"
printf "${GREEN}ready${RESET} local AI is up. Press Ctrl+C to exit.\n\n"

export ANTHROPIC_BASE_URL="http://127.0.0.1:${PROXY_PORT}"
export ANTHROPIC_API_KEY="local-ollama"

args=("$@")
has_model_flag=0
for arg in "${args[@]}"; do
    if [[ "$arg" == "--model" ]]; then
        has_model_flag=1
        break
    fi
done

if [[ "$has_model_flag" -eq 1 ]]; then
    exec "$CLAW_BIN" "${args[@]}"
else
    exec "$CLAW_BIN" --model "$MODEL" "${args[@]}"
fi
