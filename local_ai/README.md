# claw 本地離線 AI

這套流程的目標不是「在目標機器上現場安裝一堆東西」，而是做出真正可搬運的 bundle：

1. 在有網路的機器上先把 `claw`、`ollama`、模型快取打包進 repo
2. 之後把整個 `research-claw-code` 資料夾複製到另一台機器
3. 在離線環境直接執行 `bash local_ai/run.sh`

這樣才符合「下載資料夾後，下個指令就能直接跑，而且不需要網路」。

## Level 1 Windows Air-Gap

本目錄的離線 bundle 目標包含 **Level 1 air-gap**：

- 目標 Windows 電腦從出廠/空機開始就不連網。
- 可以透過 USB、外接硬碟、光碟或預載映像檔帶入完整 bundle。
- 目標機只執行 `local_ai/run.ps1`，不執行下載、安裝、編譯或 `ollama pull`。
- bundle 應在另一台有網路的 Windows 準備機完成，且準備機與目標機需盡量保持相同 OS 與 CPU 架構。

目前 Windows bundle 會帶入 `claw.exe`、`ollama.exe` 與模型快取。`run.ps1` 會優先尋找 `local_ai/runtime/python/python.exe`，再 fallback 到系統 `python`、`python3` 或 `py` 執行 `proxy.py`。若目標 Windows 空機沒有 Python，完整 Level 1 部署還需要額外帶入 portable Python，或未來改成 bundled `proxy.exe`。

Windows launcher 已支援 `CLAW_STRICT_OFFLINE=1`。開啟後只接受 `local_ai/runtime/` 內的 bundled `claw.exe`、`ollama.exe`、模型快取、manifest 與 Python；缺少任何一項都會直接失敗，不會 fallback 到系統安裝。

目前離線流程會用到的入口腳本也都集中在 `local_ai/` 目錄下。

現在的 launcher 不依賴系統安裝的 `ollama`。它會直接使用 `local_ai/runtime/` 內打包好的執行檔與模型，並優先透過 bundled Python 跑一層很薄的本地 proxy；若沒有 bundled Python，普通模式才會 fallback 到系統 Python。離線模式下，proxy 會預設附加繁體中文 system prompt，因此一般提問會直接用中文回覆；如果要它寫程式而你沒有指定語言，預設會輸出 `C` 語言。啟動時也會預設使用 `read-only` 權限，所以它會直接輸出答案，而不是主動改檔或寫檔。

新增的離線增強層都只使用本機檔案與 Python 標準庫：

- Prompt profiles：`local_ai/prompts/default_zh_tw.md`、`c_programming.md`、`project_assistant.md`
- Local checkers：`local_ai/checkers/` 會輸出 structured JSON
- RAG 文件庫：`local_ai/rag/docs/`、`local_ai/rag/index/`
- Automatic correction loop：C 題 checker 失敗時自動要求模型修正，預設最多 2 次

## 你要用的兩個指令

### 第一次準備 bundle

```bash
cd ~/Desktop/research-claw-code
bash local_ai/deploy_local.sh
```

Windows PowerShell：

```powershell
Set-Location ~/Desktop/research-claw-code
powershell -ExecutionPolicy Bypass -File .\local_ai\deploy_local.ps1
```

等價於：

```bash
bash local_ai/prepare_bundle.sh
```

預設模型是 `qwen2.5-coder:14b`。若想指定別的模型：

```bash
bash local_ai/prepare_bundle.sh qwen2.5-coder:14b
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\prepare_bundle.ps1 qwen2.5-coder:14b
```

Windows Level 1 air-gap 若目標機沒有 Python，請在準備機加入 portable Python：

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\prepare_bundle.ps1 --python-zip C:\path\python-embed-amd64.zip
powershell -ExecutionPolicy Bypass -File .\local_ai\prepare_bundle.ps1 --python-dir C:\path\python-portable
```

`--python-zip` 會解壓 Windows embeddable / portable Python zip 到 `local_ai/runtime/python/`，zip 根目錄必須包含 `python.exe`。`--python-dir` 會複製一個已解壓且含 `python.exe` 的 portable Python 目錄。

### 之後離線啟動

```bash
cd ~/Desktop/research-claw-code
bash local_ai/run.sh
```

Windows PowerShell：

```powershell
Set-Location ~/Desktop/research-claw-code
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
```

若要驗收 Level 1 strict 模式：

```powershell
$env:CLAW_STRICT_OFFLINE="1"
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
```

也可以直接丟 prompt：

```bash
bash local_ai/run.sh "幫我解釋這個 repo 的架構"
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 "幫我解釋這個 repo 的架構"
```

### Prompt profiles

預設載入 `local_ai/prompts/default_zh_tw.md`。可用環境變數切換：

```bash
CLAW_PROMPT_PROFILE=c_programming bash local_ai/run.sh
CLAW_PROMPT_DIR=local_ai/prompts bash local_ai/run.sh
```

Windows PowerShell：

```powershell
$env:CLAW_PROMPT_PROFILE="project_assistant"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
```

`CLAW_SYSTEM_PROMPT` 仍可使用；設定後會覆蓋 profile 內容。

### Local checker 與自動修正

C 程式回答會通過 `local_ai/checkers/check_c_answer.py`，檢查 `#include <stdio.h>`、`int main`、括號平衡、明顯非 C 語法、本機 gcc/clang/cc 編譯、測試輸入/輸出、離線安全與危險指令。checker 回傳 JSON，例如：

```json
{
  "ok": false,
  "score": 0.55,
  "issues": ["Missing test input/output"],
  "suggestions": ["Add at least one sample run"]
}
```

若 checker 失敗，proxy 會建立 repair prompt，包含原始問題、上一版回答、checker JSON，並要求只修正列出的問題。重試次數可調：

```bash
CLAW_MAX_REPAIR_RETRIES=2 bash local_ai/run.sh
```

### RAG 文件庫

USB 帶入的 `.md`、`.txt`、`.c`、`.h`、`.py`、`.json`、`.csv` 可放進 `local_ai/rag/docs/`，再建立本機索引：

```bash
bash local_ai/run.sh --import-docs /Volumes/USB/my_notes
bash local_ai/run.sh --reindex-rag
bash local_ai/run.sh --rag "請根據我的 C 語言筆記解釋 pointer"
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 --import-docs E:\my_notes
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 --reindex-rag
powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1 --rag "請根據我的 C 語言筆記解釋 pointer"
```

搜尋採用 dependency-light 的 keyword / BM25-like scoring，並加權檔名與 Markdown heading。回答 prompt 會包含來源，例如：

```text
參考本地文件：
- local_ai/rag/docs/c_pointer_notes.md
```

## Offline USB Workflow

1. Prepare the bundle on an online machine.
2. Copy the repository to a USB drive formatted as exFAT.
3. On the offline target machine, copy the repository locally.
4. Put extra notes or documents into `local_ai/rag/docs/`.
5. Run `bash local_ai/run.sh --reindex-rag`.
6. Ask questions with `--rag`.

### 用完後清理 bundle

```bash
bash local_ai/cleanup_local.sh
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\local_ai\cleanup_local.ps1
```

這會刪除 `local_ai/runtime/` 內的 bundled `claw`、bundled `ollama`、模型快取與 manifest。

## 產物會放哪裡

執行 `prepare_bundle.sh` 後，會產生：

```text
local_ai/runtime/
├── bin/
│   ├── claw
│   └── ollama
├── python/        # Windows Level 1 air-gap 建議放 portable Python
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
- 如果你用完後想回收 repo 內空間，可以執行 `bash local_ai/cleanup_local.sh`。
- 如果你要把它分發給別人，直接壓縮整個 `research-claw-code` 資料夾即可。
- Windows Level 1 air-gap 部署時，請在有網路的 Windows 準備機製作 bundle，再用 USB/外接硬碟/光碟/映像檔搬到無網路 Windows 目標機；目標機只跑 `run.ps1`。
- 目前這個 bundle 是針對「相同作業系統 + 相同 CPU 架構」攜帶。例：這次打的是 `macOS arm64`，所以最穩是搬到另一台 `macOS arm64` 機器。`run.sh` 會檢查這個條件。
- 也就是說：不需要安裝第三方軟體，但不能保證同一份 bundle 同時跨 `macOS / Linux / Windows` 或 `arm64 / x86_64` 全部通用。
- 在 macOS 上，launcher 會優先使用系統自帶的 `/usr/bin/python3`，所以目標機器不需要另外安裝 Python。
- 在 Windows 上，PowerShell launcher 會優先尋找 `local_ai/runtime/python/python.exe`，再 fallback 到 `python`、`python3` 或 `py`；設定 `CLAW_STRICT_OFFLINE=1` 時不允許 fallback。
- `bash local_ai/cleanup_local.sh` 不會動到 `~/.ollama` 的全域模型快取，避免誤刪你原本就有的模型。
- `powershell -ExecutionPolicy Bypass -File .\local_ai\cleanup_local.ps1` 也只會清 repo 內的 bundle。

## 常用環境變數

```bash
CLAW_MODEL=qwen2.5-coder:14b bash local_ai/run.sh
CLAW_OLLAMA_PORT=11435 bash local_ai/run.sh
CLAW_PERMISSION_MODE=read-only bash local_ai/run.sh
CLAW_SYSTEM_PROMPT="請全程使用繁體中文，並用條列整理答案。" bash local_ai/run.sh
CLAW_PROMPT_PROFILE=c_programming bash local_ai/run.sh
CLAW_MAX_REPAIR_RETRIES=2 bash local_ai/run.sh
```

Windows PowerShell：

```powershell
$env:CLAW_MODEL="qwen2.5-coder:14b"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_OLLAMA_PORT="11435"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_PERMISSION_MODE="read-only"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_STRICT_OFFLINE="1"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_SYSTEM_PROMPT="請全程使用繁體中文，並用條列整理答案。"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_PROMPT_PROFILE="c_programming"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
$env:CLAW_MAX_REPAIR_RETRIES="2"; powershell -ExecutionPolicy Bypass -File .\local_ai\run.ps1
```

## 疑難排解

### 找不到 bundle

代表還沒先執行：

```bash
bash local_ai/deploy_local.sh
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

### RAG 找不到文件

先確認檔案副檔名是否為支援格式，並重新建立索引：

```bash
bash local_ai/run.sh --reindex-rag
```

### checker 一直警告

如果本機沒有 C compiler，checker 會跳過編譯檢查，但仍會做靜態檢查。若答案在重試後仍未通過，系統會輸出目前最佳答案並附上「本地檢查警告」。

---

## C Exam Offline Eval Pack

在離線環境中自動評估本地 AI 對 C 考題的回答品質。不需要網路、不增加模型大小。

### 評估案例

包含 19 個代表性考題，整理自這些 PDF：

- **2021 Exam1**: Series, Pattern, Geometry, Game (4 cases)
- **2022 Exam1**: Series, Diamond, Geometry, Tug War (4 cases)
- **2023 Exam1**: Series, Diamond, Geometry, Tug War (4 cases)
- **2024 Exam1**: Series, Arrow, Guessing Game (3 cases)
- **2025 Midterm**: Series, Triangle, Triangles, Even/Odd Game (4 cases)

每題包含：
- 詳細問題描述
- 樣本輸入/輸出
- 必要功能清單
- 編譯和執行要求
- 評分標準

### 快速開始

```bash
# 查看可用評估案例
ls -la local_ai/eval_cases/c_exam/

# 產生報告骨架；若沒有答案，case 會標示 no answer
bash local_ai/run_eval.sh

# 使用本地 AI 生成程式碼並評估
bash local_ai/run_eval.sh --use-ai

# 使用已準備好的答案檔測試；檔名格式為 <case_id>.c
bash local_ai/run_eval.sh --answers-dir /path/to/answers

# 篩選特定年份或主題
bash local_ai/run_eval.sh --filter 2025
bash local_ai/run_eval.sh --filter series
bash local_ai/run_eval.sh --filter geometry
```

### 評估流程

評估器執行以下 smoke tests：

1. **Compile**: 檢查代碼是否能編譯（需要 cc/gcc/clang）
2. **Run**: 執行編譯後的程式，提供樣本輸入
3. **Keyword**: 檢查輸出是否包含必要關鍵字
4. **Structure**: 檢查 C 程式碼是否包含 main、scanf、printf、loop 等必要結構
5. **Score**: 根據上述結果計算得分

### 評估報告

執行後會生成 `eval_report.json`，包含：

```json
{
  "timestamp": 1234567890,
  "total_cases": 19,
  "cases_tested": 19,
  "total_points": 362,
  "total_earned": 145,
  "pass_rate": 72.5,
  "results": [
    {
      "case_id": "2021_exam1_001",
      "compile_pass": true,
      "run_pass": true,
      "keyword_pass": true,
      "structure_pass": true,
      "score": 12,
      "output": "270944.7015728441",
      "messages": ["Compile: OK", "Runtime: OK", "All keywords found"]
    }
  ]
}
```

### 評估指標

每個案例得分基於：

- **Compile Pass** (必需)：程式是否能編譯
- **Run Pass** (必需)：程式是否能執行
- **Keyword Pass** (重要)：輸出是否包含 `expected_behavior.output_contains` 或 `checker_rules.output_keywords`
- **Structure Pass** (重要)：程式碼是否包含 `checker_rules.required_code_keywords`

得分計算：

```
if compile_pass and run_pass:
    if keyword_pass and structure_pass:
        score = points × 1.0
    elif keyword_pass or structure_pass:
        score = points × 0.7
    else:
        score = points × 0.5
else:
    score = points × 0.0 if not compile_pass else 0.25
```

### 生成 AI 回答

使用 `--use-ai` 時，評估器會：

1. 呼叫本地 AI（via `local_ai/run.sh`）
2. 提示生成完整 C 程式
3. 提取 C 代碼區塊
4. 編譯並測試
5. 記錄結果

要求：
- 本地 AI bundle 已準備好（`bash local_ai/deploy_local.sh`）
- 本機需要 C compiler（gcc/clang）

### 無 AI 評估

若要測試已寫好的 C 代碼，建立一個答案目錄，檔名使用 case id：

```bash
# 例：只測 2021_exam1_001
mkdir -p /tmp/c_exam_answers
cat > /tmp/c_exam_answers/2021_exam1_001.c << 'EOF'
#include <stdio.h>
int main() {
    int n;
    scanf("%d", &n);
    printf("Result: %d\n", n * 2);
    return 0;
}
EOF

bash local_ai/run_eval.sh --answers-dir /tmp/c_exam_answers --filter 2021_exam1_001
```

### 評估案例結構

每個 JSON 案例包含：

```json
{
  "id": "2021_exam1_001",
  "year": 2021,
  "exam": "exam1",
  "points": 12,
  "topic": "Series Calculation",
  "difficulty": "medium",
  "prompt": "Complete problem statement",
  "required_features": ["List of key features"],
  "sample_input": "11",
  "expected_behavior": {
    "output_contains": ["270944"],
    "min_value": 270000,
    "max_value": 271000
  },
  "checker_rules": {
    "compile_required": true,
    "runtime_required": true,
    "timeout_seconds": 5,
    "required_code_keywords": ["main", "scanf", "printf", "for"]
  }
}
```

### 整合到教學工作流

```bash
# 1. 準備 bundle
bash local_ai/deploy_local.sh

# 2. 提問模型
bash local_ai/run.sh "寫一個 C 程式計算級數"

# 3. 評估所有案例
bash local_ai/run_eval.sh --use-ai

# 4. 查看報告
cat eval_report.json | jq '.pass_rate'
```

### 已知限制

- 編譯檢查需要本機 C compiler（cc/gcc/clang）
- 若無編譯器，只執行靜態檢查和輸出驗證
- 遊戲模擬題需要手動提供輸入序列
- 評估不檢查演算法複雜度或優化
- 不支援多檔案程式或 header file
- 目前是 smoke test，不是精準人工閱卷替代品
