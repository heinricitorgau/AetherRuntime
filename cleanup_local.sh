#!/usr/bin/env bash
# 對外的清理入口：刪除 deploy_local.sh 在 repo 內建立的離線 bundle。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec bash "$SCRIPT_DIR/local_ai/cleanup_bundle.sh" "$@"
