#!/usr/bin/env bash
# 對外的部署入口：把 repo 準備成可離線直接執行的本地 AI bundle。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec bash "$SCRIPT_DIR/local_ai/prepare_bundle.sh" "$@"
