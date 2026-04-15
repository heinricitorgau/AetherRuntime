# claw 本地離線 AI

這套流程的目標不是「在目標機器上現場安裝一堆東西」，而是做出真正可搬運的 bundle：

1. 在有網路的機器上先把 `claw`、`ollama`、模型快取打包進 repo
2. 之後把整個 `research-claw-code` 資料夾複製到另一台機器
3. 在離線環境直接執行 `bash local_ai/run.sh`

這樣才符合「下載資料夾後，下個指令就能直接跑，而且不需要網路」。

現在的 launcher 不依賴系統安裝的 `ollama`。它會直接使用 `local_ai/runtime/` 內打包好的執行檔與模型，並透過系統自帶的 Python 3 跑一層很薄的本地 proxy。

## 你要用的兩個指令

### 第一次準備 bundle

```bash
cd ~/Desktop/research-claw-code
bash deploy_local.sh
```

等價於：

```bash
bash local_ai/prepare_bundle.sh
```

預設模型是 `llama3.2`。若想指定別的模型：

```bash
bash local_ai/prepare_bundle.sh codellama
```

### 之後離線啟動

```bash
cd ~/Desktop/research-claw-code
bash local_ai/run.sh
```

也可以直接丟 prompt：

```bash
bash local_ai/run.sh "幫我解釋這個 repo 的架構"
```

## 產物會放哪裡

執行 `prepare_bundle.sh` 後，會產生：

```text
local_ai/runtime/
├── bin/
│   ├── claw
│   └── ollama
├── ollama-home/
└── bundle-manifest.txt
```

其中：

- `bin/claw` 是可直接執行的 CLI
- `bin/ollama` 是直接打包進 repo 的本地模型引擎
- `ollama-home/` 是模型與 manifest 快取

## 目前架構

```text
你
  ↓
claw
  ↓ Anthropic Messages API
local_ai/proxy.py
  ↓ OpenAI Chat Completions
bundled Ollama
  ↓
bundled local model
```

## 注意事項

- `prepare_bundle.sh` 需要網路，因為它可能要拉模型與做 release build。
- `run.sh` 是離線優先，不會主動幫你下載任何東西。
- `local_ai/runtime/` 可能很大，因為模型本身會一起被打包。
- 如果你要把它分發給別人，直接壓縮整個 `research-claw-code` 資料夾即可。
- 目前這個 bundle 是針對「相同作業系統 + 相同 CPU 架構」攜帶。例：這次打的是 `macOS arm64`，所以最穩是搬到另一台 `macOS arm64` 機器。`run.sh` 會檢查這個條件。
- 也就是說：不需要安裝第三方軟體，但不能保證同一份 bundle 同時跨 `macOS / Linux / Windows` 或 `arm64 / x86_64` 全部通用。
- 在 macOS 上，launcher 會優先使用系統自帶的 `/usr/bin/python3`，所以目標機器不需要另外安裝 Python。

## 常用環境變數

```bash
CLAW_MODEL=llama3.2 bash local_ai/run.sh
CLAW_OLLAMA_PORT=11435 bash local_ai/run.sh
```

## 疑難排解

### 找不到 bundle

代表還沒先執行：

```bash
bash deploy_local.sh
```

### 想確認 bundle 內容

```bash
cat local_ai/runtime/bundle-manifest.txt
```

### 查看執行日誌

```bash
tail -f /tmp/claw-local-ollama.log
tail -f /tmp/claw-local-proxy.log
```
