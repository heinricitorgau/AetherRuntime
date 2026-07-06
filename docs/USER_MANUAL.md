# 使用手冊（User Manual）

`research-claw-code` 的完整使用說明。本手冊涵蓋離線 bundle 的準備與部署、日常使用、
題目資料匯入（含中翻英）、評測流程與開發入口。專案定位與治理架構請看
[`README.md`](../README.md)。

## 目錄

- [1. 兩條使用路線](#1-兩條使用路線)
- [2. 離線部署](#2-離線部署)
  - [2.1 支援目標：Level 1 Windows Air-Gap](#21-支援目標level-1-windows-air-gap)
  - [2.2 快速開始：準備 bundle](#22-快速開始準備-bundle)
  - [2.3 複製到目標機器](#23-複製到目標機器)
  - [2.4 在離線環境啟動](#24-在離線環境啟動)
  - [2.5 Offline USB Workflow](#25-offline-usb-workflow)
  - [2.6 清理 bundle](#26-清理-bundle)
- [3. 日常使用](#3-日常使用)
  - [3.1 離線模式行為](#31-離線模式行為)
  - [3.2 多行輸入](#32-多行輸入)
  - [3.3 硬體與模型推薦](#33-硬體與模型推薦)
  - [3.4 常用環境變數](#34-常用環境變數)
  - [3.5 除錯與 Smoke Test](#35-除錯與-smoke-test)
- [4. RAG 與題目資料](#4-rag-與題目資料)
  - [4.1 RAG 本地文件庫](#41-rag-本地文件庫)
  - [4.2 題目匯入：中翻英](#42-題目匯入中翻英)
  - [4.3 題目 RAG 檔案（.md）](#43-題目-rag-檔案md)
- [5. 評測](#5-評測)
  - [5.1 C Exam Offline Eval Pack](#51-c-exam-offline-eval-pack)
  - [5.2 重新開始一輪 Benchmark 實驗](#52-重新開始一輪-benchmark-實驗)
- [6. Rust CLI 開發](#6-rust-cli-開發)
- [7. 注意事項](#7-注意事項)

---

## 1. 兩條使用路線

`research-claw-code` 是 `claw` CLI 的研究與本地化專案，主要有兩條使用路線：

- **離線 bundle**：先在有網路的機器打包 `claw + Ollama + 模型`，再把整個資料夾搬到
  離線環境直接使用。目標是「下載資料夾後，離線直接問問題」→ 看 [第 2 章](#2-離線部署)。
- **Rust CLI 開發**：在 `rust/` workspace 內開發、建置與測試 `claw` CLI
  → 看 [第 6 章](#6-rust-cli-開發)。

---

## 2. 離線部署

### 2.1 支援目標：Level 1 Windows Air-Gap

本專案要挑戰的無網路場景是 **Level 1 air-gap**：

- 目標 Windows 電腦可以是出廠/空機狀態，從頭到尾不連網。
- 允許用 USB、外接硬碟、光碟或預載映像檔把完整 bundle 帶進目標機。
- 目標機不應現場下載模型、安裝 Ollama、安裝 Rust 或編譯 `claw`。
- 準備 bundle 的工作必須在另一台有網路、同作業系統與同 CPU 架構的準備機完成。

也就是說，這不是「完全沒有外部媒介的空機自生成 AI」，而是「先製作完整可攜 bundle，
再部署到全程無網路的 Windows 目標機」。

目前 Windows bundle 已打包 `claw.exe`、`ollama.exe` 與模型快取；`local_ai/run.ps1`
會優先尋找 `local_ai/runtime/python/python.exe`，再 fallback 到系統 `python`、
`python3` 或 `py` 來啟動 `local_ai/proxy.py`。若目標 Windows 空機沒有 Python，
還需要把 portable Python 打包進 `local_ai/runtime/`（見 2.2），或之後把 proxy
做成獨立 `proxy.exe`，才算完整通過 Level 1。

Windows launcher 已支援 `CLAW_STRICT_OFFLINE=1`。開啟後只允許使用
`local_ai/runtime/` 內的 bundled `claw.exe`、`ollama.exe`、模型快取、manifest 與
Python；缺任一項會直接失敗，不會 fallback 到系統安裝。

### 2.2 快速開始：準備 bundle

在**有網路**的機器上執行：

macOS / Linux:

```bash
cd ~/Desktop/research-claw-code
bash local_ai/deploy_local.sh
```

Windows PowerShell:

```powershell
Set-Location ~/Desktop/research-claw-code
powershell -ExecutionPolicy Bypass -File .\local_ai\deploy_local.ps1
```

這一步會建置 `claw` CLI、打包 bundled `ollama`、下載指定模型，並產生
`local_ai/runtime/` 離線執行環境。

預設模型是 `qwen2.5-coder:14b`。如需指定模型：

```bash
bash local_ai/prepare_bundle.sh qwen2.5-coder:14b
```

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\prepare_bundle.ps1 qwen2.5-coder:14b
```

常用準備選項：

```bash
# 優先重用既有 binary 與已打包模型，減少重建與重拷貝
bash local_ai/prepare_bundle.sh --fast

# 只允許使用本機已快取模型，不接受現場下載
bash local_ai/prepare_bundle.sh --cached-only
```

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\prepare_bundle.ps1 --fast
powershell -ExecutionPolicy Bypass -File .\local_ai\prepare_bundle.ps1 --cached-only
```

Windows Level 1 air-gap 若目標機沒有 Python，請在準備機把 portable Python 一起打包：

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\prepare_bundle.ps1 --python-zip C:\path\python-embed-amd64.zip
powershell -ExecutionPolicy Bypass -File .\local_ai\prepare_bundle.ps1 --python-dir C:\path\python-portable
```

`--python-zip` 適合 Windows embeddable / portable Python zip，解壓後必須在根目錄有
`python.exe`。`--python-dir` 適合已解壓、且目錄內已有 `python.exe` 的 portable
Python。

### 2.3 複製到目標機器

把整個 `research-claw-code/` 資料夾連同 `local_ai/runtime/` 一起複製到目標機器。

目前 bundle 以「相同作業系統 + 相同 CPU 架構」可攜為主，例如 macOS arm64 打出的
bundle 最適合搬到另一台 macOS arm64。

Windows Level 1 air-gap 測試時，建議在有網路的 Windows x64 準備機打包，再用
USB/外接硬碟/光碟/映像檔搬到無網路的 Windows x64 目標機。目標機啟動前不要再執行
`prepare_bundle.ps1`，只執行 `run.ps1`。

若要驗收目標機完全不依賴系統安裝，請啟動前設定：

```powershell
$env:CLAW_STRICT_OFFLINE="1"
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
```

### 2.4 在離線環境啟動

macOS / Linux:

```bash
cd ~/Desktop/research-claw-code
bash local_ai/run.sh
```

Windows PowerShell:

```powershell
Set-Location ~/Desktop/research-claw-code
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
```

也可以直接丟一次性問句：

```bash
bash local_ai/run.sh --output-format text prompt "幫我整理這份會議紀錄"
bash local_ai/run.sh "請用中文解釋這個錯誤訊息"
```

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 --output-format text prompt "幫我整理這份會議紀錄"
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 "請用中文解釋這個錯誤訊息"
```

### 2.5 Offline USB Workflow

1. 在有網路的機器準備 bundle（見 2.2）。
2. 把整個 repository 複製到 exFAT 格式的 USB 隨身碟。
3. 在離線目標機上，把 repository 複製到本機。
4. 把額外的筆記或文件放進 `local_ai/rag/docs/`。
5. 執行 `bash local_ai/run.sh --reindex-rag`。
6. 用 `--rag` 問問題（見 4.1）。

### 2.6 清理 bundle

macOS / Linux:

```bash
bash local_ai/cleanup_local.sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\cleanup_local.ps1
```

這只會刪除 repo 內的 `local_ai/runtime/`，不會動到 `~/.ollama` 的全域模型快取。

---

## 3. 日常使用

### 3.1 離線模式行為

- 預設以繁體中文回覆，錯誤訊息會以繁中 UTF-8 直接回傳。
- 若要求寫程式但未指定語言，預設輸出 C 語言程式。
- 預設以 `read-only` 權限啟動，所以會直接輸出答案，不會主動寫檔。
- Prompt policy 會從 `local_ai/prompts/` 載入；預設 profile 是 `default_zh_tw`。
- 一般問題使用 SSE 串流，token 會逐步顯示。
- C 程式題會先做本地 JSON checker，檢查 `#include <stdio.h>`、`int main`、
  括號平衡、明顯非 C 語法、可用時的本機 gcc/clang 編譯、測試輸入/輸出、離線安全與
  危險指令；若失敗，會要求模型重寫，預設最多重試兩次。
- C 題修復流程需要完整文字才能檢查，因此會等模型產生完畢後一次輸出。
- RAG 文件庫位於 `local_ai/rag/docs/`，支援 `.md`、`.txt`、`.c`、`.h`、`.py`、
  `.json`、`.csv`，使用本機 keyword / BM25-like search，不需要向量資料庫或網路
  embeddings。

### 3.2 多行輸入

多行輸入建議使用 `/multiline`：

```text
/multiline
第一行
第二行
/submit
```

`Shift+Enter` 與 `Ctrl+J` 可用於插入換行，但 `Shift+Enter` 是否生效取決於終端機；
Windows 上尤其建議使用 `/multiline`。

### 3.3 硬體與模型推薦

| 模型名稱 | Size Class | RAM 需求 | 啟動速度 | 預設 Timeout | 建議用途 |
|---|---|---|---|---|---|
| `qwen2.5-coder:1.5b` (預設) | small | ~2 GB | 快 | 60s / 15s | 基礎測試、除錯 (Smoke Tests) |
| `qwen2.5-coder:7b` | medium | ~5 GB | 中等 | 180s / 30s | 平衡效能與品質 (無 GPU 亦可) |
| `qwen2.5-coder:14b` | large | ~10 GB | 慢 (CPU) | 300s / 60s | 高品質程式碼生成 (建議有 GPU) |

若主要用途是解 C 題，建議優先用 `qwen2.5-coder:14b`；機器較吃緊時再考慮
`qwen2.5-coder:7b`。

### 3.4 常用環境變數

macOS / Linux:

```bash
CLAW_MODEL=qwen2.5-coder:1.5b bash local_ai/run.sh
CLAW_OLLAMA_PORT=11435 bash local_ai/run.sh
CLAW_PROXY_PORT=8082 bash local_ai/run.sh
CLAW_PERMISSION_MODE=read-only bash local_ai/run.sh
CLAW_SYSTEM_PROMPT="請全程使用繁體中文，回答精簡一點" bash local_ai/run.sh
CLAW_PROMPT_PROFILE=c_programming bash local_ai/run.sh
CLAW_PROMPT_DIR=local_ai/prompts bash local_ai/run.sh
CLAW_MAX_REPAIR_RETRIES=2 bash local_ai/run.sh
```

Windows PowerShell:

```powershell
$env:CLAW_MODEL="qwen2.5-coder:1.5b"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_OLLAMA_PORT="11435"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_PROXY_PORT="8082"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_PERMISSION_MODE="read-only"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_STRICT_OFFLINE="1"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_SYSTEM_PROMPT="請全程使用繁體中文，回答精簡一點"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_PROMPT_PROFILE="c_programming"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_MAX_REPAIR_RETRIES="2"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
```

翻譯相關環境變數（見 4.2）：`CLAW_TRANSLATE_MODEL`、`CLAW_OLLAMA_URL`。

### 3.5 除錯與 Smoke Test

當環境啟動後沒有回應、或是卡住時，請使用 `--smoke-test` 參數快速驗證基礎建設是否打通：

macOS / Linux:

```bash
bash local_ai/run.sh --smoke-test
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 --smoke-test
```

`--smoke-test` 會強制使用最小的 `1.5b` 模型、極短的 Timeout、關閉修復流程，並固定
送出一個簡單的英文 prompt。此模式**主要驗證 Ollama + Proxy 的同步 API 是否運作正常**，
會直接對 proxy 送出 HTTP POST。如果能成功回傳助理回應文字，代表本地端基礎設施已準備
就緒。

若 Proxy 的 smoke-test 成功，但正常使用時 `claw` 仍然失敗或卡住，則問題通常出在
`claw` 終端機與 Proxy 之間的**串流協定（SSE）相容性**。若你想強制使用 `claw` 來跑
smoke-test 以測試串流相容性，可以加上：

```powershell
$env:CLAW_SMOKE_USE_CLAW="1"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 --smoke-test
```

若要看更詳細的串流與 Timeout 日誌，可以開啟 `CLAW_DEBUG=1`：

```bash
CLAW_DEBUG=1 bash local_ai/run.sh
```

---

## 4. RAG 與題目資料

### 4.1 RAG 本地文件庫

把 USB 帶入的筆記放進 `local_ai/rag/docs/`，或直接匯入：

```bash
bash local_ai/run.sh --import-docs /Volumes/USB/my_notes
bash local_ai/run.sh --reindex-rag
bash local_ai/run.sh --rag "請根據我的 C 語言筆記解釋 pointer"
```

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 --import-docs E:\my_notes
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 --reindex-rag
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 --rag "請根據我的 C 語言筆記解釋 pointer"
```

回答會把檢索到的來源放進 prompt，例如：

```text
參考本地文件：
- local_ai/rag/docs/c_pointer_notes.md
- local_ai/rag/docs/week03_array.md
```

### 4.2 題目匯入：中翻英

中文題目在進入系統時可以先翻成英文再交給解題模型。翻譯接在兩條資料匯入路徑上，
由 `--translate` 旗標啟用（預設關閉），使用獨立的本地翻譯模型
`qwen2.5:7b-instruct`（可用 `--translate-model` 或環境變數
`CLAW_TRANSLATE_MODEL` 更換），直接呼叫本機 Ollama，不需先啟動 proxy：

```powershell
# corpus 匯入：翻譯後落入 raw/，之後照 V10 流程人工策展與審核
python local_ai/corpus/import_exam.py --file exam.json --translate

# ingest 訓練資料準備：翻譯後寫入 training 輸出
python local_ai/ingest/prepare_training.py --translate
```

治理與稽核行為：

- 只有偵測到中文的題目才會送翻譯，英文題目原樣通過。
- 原文永遠保留：corpus 紀錄存於 `prompt_original`，ingest 紀錄存於
  `instruction_original`；翻譯模型與時間也寫入紀錄與 audit log。
- 每次匯入輸出翻譯報告（`translation_report.json` / `.md`；corpus 在
  `local_ai/corpus/reports/`，ingest 在 training 輸出目錄）。
- 翻譯失敗不會弄丟或改壞資料：保留原文並在報告中標記錯誤。
- 離線自我測試（不需模型）：`python local_ai/shared/translator.py --self-test`。

### 4.3 題目 RAG 檔案（.md）

匯入的題目（原生英文或翻譯後的英文）預設會同時輸出純題目 `.md` 到
`local_ai/rag/docs/problems/` 並自動重建 RAG 索引，讓模型解題時可以用
`--rag` 檢索到題目內容；不需要時加 `--no-rag-md` 關閉。

```powershell
# 匯入後，解題時讓模型讀題目
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 --rag "solve the poker match problem"
```

- 檔名以題目 ID 命名，重複匯入會冪等覆寫，不會堆出重複檔案。
- 檔案內容只有英文題目本文，沒有 metadata 區塊。
- 離線自我測試：`python local_ai/shared/rag_export.py --self-test`。

---

## 5. 評測

### 5.1 C Exam Offline Eval Pack

`local_ai/eval_cases/c_exam/` 已整理 2021-2025 C programming PDF 題目為離線 eval
cases。這不訓練模型、不增加模型大小；只用本地模型產生答案，再用 Python 標準庫和本機
`cc/gcc/clang` 做 smoke test。

```bash
# 產生報告骨架；沒有答案時 case 會標示 no answer
bash local_ai/run_eval.sh
powershell -ExecutionPolicy Bypass -File .\local_ai\run_eval.ps1

# ── proxy sync AI 模式（Windows 推薦；自動啟動 Ollama + proxy）──
bash local_ai/run_eval.sh --use-proxy-ai --filter 2025
powershell -ExecutionPolicy Bypass -File .\local_ai\run_eval.ps1 --use-proxy-ai --filter 2025

# ── claw 串流 AI 模式（Linux/Mac）──
bash local_ai/run_eval.sh --use-ai
powershell -ExecutionPolicy Bypass -File .\local_ai\run_eval.ps1 --use-ai

# 用已準備好的答案檔測試，檔名格式為 <case_id>.c
bash local_ai/run_eval.sh --answers-dir /path/to/answers --filter 2024
powershell -ExecutionPolicy Bypass -File .\local_ai\run_eval.ps1 --answers-dir C:\path\to\answers --filter 2024
```

`--use-proxy-ai` 直接呼叫 proxy `/v1/messages`（stream=false），不依賴 claw 串流，
Windows 下更穩定。`--use-ai` 透過 `run.sh` 呼叫 claw，Windows 上串流輸出相容性目前
不穩定。

報告包含 `answer_source`、`used_fallback`、`model_score`、`pipeline_score`、
`compile_pass`、`model_compile_pass`、`run_pass`、`keyword_pass`、
`structure_pass`。`model_score` 只衡量模型實際輸出的 C code；`pipeline_score` 則包含
fallback scaffold 後的 pipeline 韌性，目前定位是 smoke test，不取代人工閱卷。

### 5.2 重新開始一輪 Benchmark 實驗

每次要對模型跑新一輪評測時，依序執行以下步驟。

若要使用 SFT / benchmark Python 環境，先在 PowerShell 啟用虛擬環境：

```powershell
Set-Location C:\Users\User\OneDrive\Desktop\research-claw-code
.\.venv-sft\Scripts\Activate.ps1
```

成功後命令列前面會出現 `(.venv-sft)`。

**第 1 步 — 確認 Ollama 與模型已載入**

```powershell
ollama list
```

若模型不在清單內，先拉取：

```powershell
ollama pull qwen2.5-coder:3b
```

**第 2 步 — 啟動 proxy（開新 terminal，保持運行）**

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
```

**第 3 步 — 驗證 proxy 有回應**

```powershell
python local_ai/proxy.py --smoke-test
```

**第 4 步 — 跑 baseline（給一個可追蹤的 run ID）**

```powershell
python local_ai/benchmark/run_baseline.py --strict-code-only --run-id baseline_qwen3b_v1
```

**第 5 步 — 分析 token 浪費情況**

```powershell
python local_ai/benchmark/report_analysis.py --run-id baseline_qwen3b_v1
```

**第 6 步 — 查看報告**

```text
local_ai/benchmark/reports/runs/baseline_qwen3b_v1/report.md
local_ai/benchmark/reports/runs/baseline_qwen3b_v1/analysis_report.md
```

Fine-tune 之後，用新 run ID 重跑第 4–5 步，再比較兩輪結果：

```powershell
python local_ai/benchmark/scoring.py --compare baseline_qwen3b_v1 lora_v1
python local_ai/benchmark/report_analysis.py --compare baseline_qwen3b_v1 lora_v1
```

完整 benchmark 說明請看 [`local_ai/benchmark/README.md`](../local_ai/benchmark/README.md)。

---

## 6. Rust CLI 開發

如果你要開發或測試 `claw` CLI 本體，請進入 `rust/` workspace：

```bash
cd rust
cargo build --workspace
cargo run -p rusty-claude-cli -- --help
cargo run -p rusty-claude-cli -- prompt "explain this codebase"
```

更多 CLI 用法請看 [`USAGE.md`](../USAGE.md)，Rust workspace 與 crate 分工請看
[`rust/README.md`](../rust/README.md)。

---

## 7. 注意事項

- `prepare_bundle.sh` / `prepare_bundle.ps1` 需要在有網路的環境執行。
- `local_ai/runtime/` 可能很大，因為模型本身會一起打包。
- `--fast` 會優先重用既有 binary 與已打包模型，減少重建與重拷貝。
- `--cached-only` 不會下載模型；若本機沒有快取指定模型就會直接失敗。
- bundle manifest 在 Windows 上也是以 BOM-less UTF-8 寫入，搬到 macOS / Linux 的
  `run.sh` 讀取不會卡在 BOM。
- 重新啟動時若舊 proxy / Ollama 還占著 port，Windows 與 macOS / Linux 都會等最多
  10 秒嘗試釋放 port 再接手。
- macOS launcher 會優先使用系統自帶的 `/usr/bin/python3`。
- Windows launcher 會優先尋找 `local_ai/runtime/python/python.exe`，再 fallback 到
  `python`、`python3` 或 `py`；若設定 `CLAW_STRICT_OFFLINE=1`，則不允許 fallback。
- `local_ai/deploy_local.sh` 與 `local_ai/deploy_local.ps1` 都會在結束時印出總耗時。
- 翻譯功能（4.2）用的 `qwen2.5:7b-instruct` 不在預設 bundle 內；要在離線目標機使用
  `--translate`，準備 bundle 時需要一併打包該模型。
