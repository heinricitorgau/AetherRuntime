#!/usr/bin/env bash
# local_ai/run_eval.sh
# Run C exam offline evaluation pack

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
EVAL_DIR="$SCRIPT_DIR/eval_cases/c_exam"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()  { printf "${CYAN}  ->${RESET} %s\n" "$1"; }
ok()    { printf "${GREEN}  ok${RESET} %s\n" "$1"; }
warn()  { printf "${YELLOW}  !!${RESET} %s\n" "$1"; }
fail()  { printf "${RED}  xx${RESET} %s\n" "$1"; exit 1; }
header(){ printf "\n${BOLD}== %s ==${RESET}\n" "$1"; }

# Check if eval cases exist
if [[ ! -d "$EVAL_DIR" ]]; then
    fail "Eval cases not found at $EVAL_DIR"
fi

# Find Python
find_python() {
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

if ! PYTHON_BIN="$(find_python)"; then
    fail "python3 not found"
fi

header "C Exam Offline Evaluation Pack"

# Parse arguments
USE_AI=0
USE_PROXY_AI=0
FILTER=""
OUTPUT=""
ANSWERS_DIR=""

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --use-ai)
            USE_AI=1
            info "Will generate code using local AI (claw-based)"
            shift
            ;;
        --use-proxy-ai)
            USE_PROXY_AI=1
            info "Will generate code via proxy sync API"
            shift
            ;;
        --filter)
            FILTER="$2"
            info "Filtering cases: $FILTER"
            shift 2
            ;;
        --output)
            OUTPUT="$2"
            info "Output file: $OUTPUT"
            shift 2
            ;;
        --answers-dir)
            ANSWERS_DIR="$2"
            info "Using answer files from: $ANSWERS_DIR"
            shift 2
            ;;
        --help|-h)
            cat <<EOF
Usage: bash local_ai/run_eval.sh [options]

Options:
  --use-proxy-ai        Generate code via proxy sync API (stream=false). Starts Ollama + proxy
                        automatically. Recommended on Linux/Mac. (default model: qwen2.5-coder:1.5b)
  --use-ai              Generate code via claw/run.sh (may require claw streaming).
  --answers-dir DIR     Use DIR/<case_id>.c answers instead of the model.
  --filter TEXT         Run cases whose id, filename, year, or topic matches TEXT.
  --output FILE         Write eval_report.json to FILE.

Example:
  bash local_ai/run_eval.sh --use-proxy-ai --filter 2025
EOF
            exit 0
            ;;
        *)
            warn "Unknown argument: $1"
            shift
            ;;
    esac
done

# Build eval runner command
eval_cmd=("$PYTHON_BIN" "$SCRIPT_DIR/eval_runner.py")
eval_cmd+=(--eval-dir "$EVAL_DIR")

if [[ "$USE_AI" -eq 1 ]]; then
    eval_cmd+=(--use-ai)
fi

if [[ -n "$FILTER" ]]; then
    eval_cmd+=(--filter "$FILTER")
fi

if [[ -n "$OUTPUT" ]]; then
    eval_cmd+=(--output "$OUTPUT")
fi

if [[ -n "$ANSWERS_DIR" ]]; then
    eval_cmd+=(--answers-dir "$ANSWERS_DIR")
fi

# Proxy AI service startup + cleanup
PROXY_PID=""
OLLAMA_PID=""

cleanup_proxy_ai() {
    if [[ -n "$PROXY_PID" ]]; then
        kill "$PROXY_PID" 2>/dev/null || true
        info "proxy stopped"
    fi
    if [[ -n "$OLLAMA_PID" ]]; then
        kill "$OLLAMA_PID" 2>/dev/null || true
        info "ollama stopped"
    fi
}

if [[ "$USE_PROXY_AI" -eq 1 ]]; then
    PROXY_PORT="${CLAW_PROXY_PORT:-8082}"
    OLLAMA_PORT="${CLAW_OLLAMA_PORT:-11435}"
    OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:${OLLAMA_PORT}}"
    PROXY_URL="http://127.0.0.1:${PROXY_PORT}"
    PROXY_MODEL="${CLAW_MODEL:-qwen2.5-coder:1.5b}"
    BIN_DIR="$SCRIPT_DIR/runtime/bin"
    BUNDLED_OLLAMA_HOME="$SCRIPT_DIR/runtime/ollama-home"

    if [[ -x "$BIN_DIR/ollama" ]]; then
        OLLAMA_BIN="$BIN_DIR/ollama"
    elif command -v ollama >/dev/null 2>&1; then
        OLLAMA_BIN="$(command -v ollama)"
    else
        fail "cannot find ollama binary (looked in $BIN_DIR and PATH)"
    fi

    if [[ -d "$BUNDLED_OLLAMA_HOME" ]]; then
        export OLLAMA_MODELS="$BUNDLED_OLLAMA_HOME/models"
        ok "using bundled models: $OLLAMA_MODELS"
    else
        warn "bundled model cache not found; using system ollama cache"
    fi
    export OLLAMA_HOST="127.0.0.1:${OLLAMA_PORT}"

    if curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
        ok "ollama already running on port $OLLAMA_PORT"
    else
        info "starting ollama on port $OLLAMA_PORT"
        "$OLLAMA_BIN" serve >/tmp/claw-eval-ollama.log 2>&1 &
        OLLAMA_PID=$!
        for i in $(seq 1 30); do
            if curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
                ok "ollama ready in ${i}s"
                break
            fi
            sleep 1
            if [[ "$i" -eq 30 ]]; then
                fail "ollama failed to start within 30s"
            fi
        done
    fi

    if curl -sf "http://127.0.0.1:${PROXY_PORT}/health" >/dev/null 2>&1; then
        ok "proxy already running on port $PROXY_PORT"
    else
        PROMPT_PROFILE="${CLAW_PROMPT_PROFILE:-c_programming}"
        PROMPT_DIR="${CLAW_PROMPT_DIR:-$SCRIPT_DIR/prompts}"
        info "starting proxy on port $PROXY_PORT"
        "$PYTHON_BIN" "$SCRIPT_DIR/proxy.py" \
            --model "$PROXY_MODEL" --ollama-model "$PROXY_MODEL" \
            --port "$PROXY_PORT" --ollama-url "$OLLAMA_URL" \
            --prompt-profile "$PROMPT_PROFILE" --prompt-dir "$PROMPT_DIR" \
            >/tmp/claw-eval-proxy.log 2>&1 &
        PROXY_PID=$!
        for i in $(seq 1 15); do
            if curl -sf "http://127.0.0.1:${PROXY_PORT}/health" >/dev/null 2>&1; then
                ok "proxy ready in ${i}s"
                break
            fi
            sleep 1
            if [[ "$i" -eq 15 ]]; then
                fail "proxy failed to start within 15s; check /tmp/claw-eval-proxy.log"
            fi
        done
    fi

    trap cleanup_proxy_ai EXIT INT TERM

    info "Using proxy sync AI mode"
    info "Proxy URL: $PROXY_URL"
    info "Model: $PROXY_MODEL"

    export CLAW_MODEL="$PROXY_MODEL"
    eval_cmd+=(--use-proxy-ai)
    eval_cmd+=(--proxy-url "$PROXY_URL")
    eval_cmd+=(--proxy-model "$PROXY_MODEL")
fi

# Run evaluation
header "Running Evaluation"
"${eval_cmd[@]}"

ok "Evaluation complete"
