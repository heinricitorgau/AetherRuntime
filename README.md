# research-claw-code

這個 repository 的定位是：

**在有網路的電腦上，只用終端機下載與打包執行環境；到了無網路環境，直接啟動 agent 並提問，就能離線作答，而且預設全程用繁體中文回覆。**

它不是雲端服務，也不是一定要現場安裝一堆依賴的開發環境。比較接近一個可搬運的本地 AI bundle。

## 核心使用情境

### 有網路時

只做一次準備工作：

```bash
cd ~/Desktop/research-claw-code
bash deploy_local.sh
```

Windows PowerShell：

```powershell
Set-Location ~/Desktop/research-claw-code
powershell -ExecutionPolicy Bypass -File .\deploy_local.ps1
```

這一步會在終端機裡完成：

- 建置 `claw` CLI
- 準備 bundled `ollama` 執行檔
- 下載並打包指定模型
- 產生 `local_ai/runtime/` 離線執行環境

### 無網路時

直接啟動：

```bash
cd ~/Desktop/research-claw-code
bash local_ai/run.sh
```

直接丟題目：

```bash
bash local_ai/run.sh --output-format text prompt "幫我整理這份會議紀錄"
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 --output-format text prompt "幫我整理這份會議紀錄"
```

離線模式下，代理層會預設附加中文 system prompt，因此回覆會以繁體中文為主，適合終端機直接閱讀。
另外，若你要求「寫程式」但沒有明確指定語言，系統預設會輸出 `C` 語言程式。
另外，離線模式預設會以 `read-only` 權限啟動，所以它會直接把答案顯示在對話中，不會主動寫入檔案。

## Agent 行為

- 預設用繁體中文回覆
- 若要求寫程式但未指定語言，預設輸出 `C` 語言程式
- 預設以 `read-only` 權限啟動，所以會直接輸出答案，不會主動寫檔
- 若要多行輸入，優先建議用 `/multiline`
- `Shift+Enter` 與 `Ctrl+J` 有綁定換行，但 `Shift+Enter` 是否真的可用，仍取決於終端機本身

## 專案承諾

- 有網路時，下載與打包流程只需要透過終端機完成
- 無網路時，不依賴外部 API
- 不需要另外安裝系統層的 `ollama`
- 在 macOS 上不需要另外安裝 Python，launcher 會優先使用系統自帶的 `/usr/bin/python3`
- 在 Windows 上使用 PowerShell 啟動鏈，會優先尋找 `python` / `python3` / `py`
- 預設以繁體中文回覆

## 快速流程

### 1. 準備離線 bundle

```bash
cd ~/Desktop/research-claw-code
bash deploy_local.sh
```

Windows PowerShell：

```powershell
Set-Location ~/Desktop/research-claw-code
powershell -ExecutionPolicy Bypass -File .\deploy_local.ps1
```

如果想換模型：

```bash
bash local_ai/prepare_bundle.sh codellama
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\prepare_bundle.ps1 codellama
```

### 2. 搬到目標機器

把整個 `research-claw-code` 資料夾連同 `local_ai/runtime/` 一起複製過去即可。

### 3. 離線使用

```bash
bash local_ai/run.sh
```

或：

```bash
bash local_ai/run.sh --output-format text prompt "請用中文解釋這個錯誤訊息"
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
```

進入 agent 後可以直接提問，例如：

```text
請用中文解釋這個錯誤訊息
```

或：

```text
請寫一個程式輸出 1
```

如果你要輸入多行內容，建議這樣用：

```text
/multiline
第一行
第二行
/submit
```

Windows 上尤其建議把 `/multiline` 當主要方案；`Shift+Enter` 不保證每個終端都會正確傳遞。

### 4. 用完後清掉下載產物

```bash
bash cleanup_local.sh
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\cleanup_local.ps1
```

這個指令會刪除 `local_ai/runtime/`，也就是 `deploy_local.sh` 在 repo 內打包出來的 bundle。

## 目錄角色

```text
.
├── local_ai/   # 離線 bundle、proxy、啟動腳本
├── rust/       # claw CLI 主實作
├── src/        # 早期 Python port / 研究與對照工具
├── tests/      # Python 端測試與加固驗證
└── docs/       # 補充研究文件
```

## 常用環境變數

```bash
CLAW_MODEL=llama3.2 bash local_ai/run.sh
CLAW_OLLAMA_PORT=11435 bash local_ai/run.sh
CLAW_PERMISSION_MODE=read-only bash local_ai/run.sh
CLAW_SYSTEM_PROMPT="請全程使用繁體中文，回答時盡量精簡。" bash local_ai/run.sh
```

Windows PowerShell：

```powershell
$env:CLAW_MODEL="llama3.2"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_OLLAMA_PORT="11435"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_PERMISSION_MODE="read-only"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_SYSTEM_PROMPT="請全程使用繁體中文，回答時盡量精簡。"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
```

## 限制

- bundle 目前是「相同作業系統 + 相同 CPU 架構」可攜，例如 `macOS arm64 -> macOS arm64`
- `prepare_bundle.sh` / `prepare_bundle.ps1` 需要先在有網路的環境執行
- `local_ai/runtime/` 可能很大，因為模型會一起打包
- `bash cleanup_local.sh` / `powershell -ExecutionPolicy Bypass -File .\cleanup_local.ps1` 只會刪除 repo 內的 bundle，不會清掉全域模型快取
- `Shift+Enter` 是否可用會受終端機影響，尤其在 Windows 上不保證穩定；請優先使用 `/multiline`

## 參考文件

- [local_ai/README.md](./local_ai/README.md)
- [USAGE.md](./USAGE.md)
- [rust/README.md](./rust/README.md)
- [AGENT_USAGE.txt](./AGENT_USAGE.txt)
