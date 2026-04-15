#!/usr/bin/env bash
# local_ai/prepare_bundle.sh
# 在有網路的機器上把本地 AI 執行環境打包進 repo，供之後離線直接跑。

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
RUST_DIR="$PROJECT_DIR/rust"
RUNTIME_DIR="$SCRIPT_DIR/runtime"
BIN_DIR="$RUNTIME_DIR/bin"
MODEL="${1:-${CLAW_MODEL:-llama3.2}}"
SOURCE_OLLAMA_HOME="${OLLAMA_HOME_OVERRIDE:-$HOME/.ollama}"
MANIFEST_ROOT="$SOURCE_OLLAMA_HOME/models/manifests/registry.ollama.ai/library"
BLOB_ROOT="$SOURCE_OLLAMA_HOME/models/blobs"

copy_tree() {
    local src="$1"
    local dst="$2"
    mkdir -p "$dst"
    if command -v rsync >/dev/null 2>&1; then
        rsync -a --delete "$src/" "$dst/"
    else
        rm -rf "$dst"
        mkdir -p "$dst"
        cp -R "$src/." "$dst/"
    fi
}

bundle_single_model() {
    local model="$1"
    local source_manifest="$MANIFEST_ROOT/$model/latest"
    local target_root="$RUNTIME_DIR/ollama-home/models"
    local target_manifest_dir="$target_root/manifests/registry.ollama.ai/library/$model"
    local target_blob_dir="$target_root/blobs"
    local digest
    local blob_name

    [[ -f "$source_manifest" ]] || fail "cannot find manifest for model ${model}: ${source_manifest}"

    rm -rf "$RUNTIME_DIR/ollama-home"
    mkdir -p "$target_manifest_dir" "$target_blob_dir"
    cp "$source_manifest" "$target_manifest_dir/latest"

    while read -r digest; do
        blob_name="${digest/:/-}"
        [[ -f "$BLOB_ROOT/$blob_name" ]] || fail "missing blob for digest ${digest}"
        cp "$BLOB_ROOT/$blob_name" "$target_blob_dir/$blob_name"
    done < <(grep -o 'sha256:[0-9a-f]\{64\}' "$source_manifest")
}

header "bundle target"
mkdir -p "$BIN_DIR"
ok "runtime dir: ${RUNTIME_DIR}"

header "tooling"
command -v cargo >/dev/null 2>&1 || fail "cargo not found; install Rust first"
command -v ollama >/dev/null 2>&1 || fail "ollama not found; install Ollama first"
ok "cargo: $(cargo --version)"
ok "ollama: $(ollama --version 2>/dev/null || echo installed)"

header "build claw"
(
    cd "$RUST_DIR"
    cargo build --workspace --release
)
install -m 755 "$RUST_DIR/target/release/claw" "$BIN_DIR/claw"
ok "bundled claw binary"

header "prepare model"
if ! ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -Fxq "$MODEL"; then
    info "model not cached yet, pulling ${MODEL}"
    ollama pull "$MODEL"
fi
ok "model available locally: ${MODEL}"

header "bundle ollama"
cp -fL "$(command -v ollama)" "$BIN_DIR/ollama"
chmod +x "$BIN_DIR/ollama"
ok "bundled ollama executable"

if [[ ! -d "$SOURCE_OLLAMA_HOME" ]]; then
    fail "cannot find Ollama home at ${SOURCE_OLLAMA_HOME}"
fi

bundle_single_model "$MODEL"
ok "bundled only the selected model: ${MODEL}"

header "write manifest"
cat > "$RUNTIME_DIR/bundle-manifest.txt" <<EOF
prepared_at=$(date '+%Y-%m-%d %H:%M:%S %z')
bundle_os=$(uname -s)
bundle_arch=$(uname -m)
model=${MODEL}
claw_binary=${BIN_DIR}/claw
ollama_binary=${BIN_DIR}/ollama
ollama_home=${RUNTIME_DIR}/ollama-home
launch_command=bash local_ai/run.sh
EOF
ok "bundle manifest written"

header "summary"
if command -v du >/dev/null 2>&1; then
    info "bundle size: $(du -sh "$RUNTIME_DIR" | awk '{print $1}')"
fi

cat <<EOF

離線 bundle 已完成。

之後只要把整個 repo 複製到目標機器，就可以直接執行：
  bash local_ai/run.sh

若想改模型：
  bash local_ai/prepare_bundle.sh codellama
EOF
