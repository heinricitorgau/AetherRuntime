# C Exam Offline Eval Pack

已建立離線 C 考題 smoke-test eval pack。這個 pack 不訓練模型、不增加模型大小，只把 PDF 題目整理成本機 JSON cases，並用本地模型輸出、C 編譯器與 sample input 做初步檢查。

## 檔案

- `local_ai/eval_cases/c_exam/`: 19 個 eval case JSON，總分 362 分
- `local_ai/eval_runner.py`: Python 標準庫 eval runner
- `local_ai/run_eval.sh`: Bash launcher
- `README.md`、`local_ai/README.md`: 使用說明

## 題目來源

- `c-exam1-programming-2021.pdf`: 4 cases
- `c-exam1-programming-2022.pdf`: 4 cases
- `c-exam1-programming-2023.pdf`: 4 cases
- `c-exam1-programming-2024.pdf`: 3 cases
- `c-midterm-programming-2025.pdf`: 4 cases

工作區內檔名帶有 `拷貝` 後綴，但內容已對應上述來源。

## 使用

```bash
# 產生報告骨架；沒有答案時會標示 no answer
bash local_ai/run_eval.sh
powershell -ExecutionPolicy Bypass -File .\local_ai\run_eval.ps1

# ── proxy sync AI 模式（Windows 推薦；自動啟動 Ollama + proxy）──
bash local_ai/run_eval.sh --use-proxy-ai
powershell -ExecutionPolicy Bypass -File .\local_ai\run_eval.ps1 --use-proxy-ai

# 篩選年份（Windows 推薦用法）
powershell -ExecutionPolicy Bypass -File .\local_ai\run_eval.ps1 --use-proxy-ai --filter 2025

# ── claw 串流 AI 模式（Linux/Mac；Windows 串流相容性不穩定）──
bash local_ai/run_eval.sh --use-ai
powershell -ExecutionPolicy Bypass -File .\local_ai\run_eval.ps1 --use-ai

# 使用已準備好的 C 答案檔；檔名需為 <case_id>.c
bash local_ai/run_eval.sh --answers-dir /path/to/answers
powershell -ExecutionPolicy Bypass -File .\local_ai\run_eval.ps1 --answers-dir C:\path\to\answers

# 篩選年份、題號或 topic
bash local_ai/run_eval.sh --filter 2024
powershell -ExecutionPolicy Bypass -File .\local_ai\run_eval.ps1 --filter 2024
bash local_ai/run_eval.sh --filter series
powershell -ExecutionPolicy Bypass -File .\local_ai\run_eval.ps1 --filter series
```

## AI 模式比較

| 模式 | 指令 | 依賴 | Windows 推薦 |
|------|------|------|-------------|
| `--use-proxy-ai` | proxy sync API (stream=false) | Ollama + Python proxy（自動啟動）| ✅ 推薦 |
| `--use-ai` | claw 串流 | claw binary + run.sh | ❌ 串流相容性不穩定 |

`--use-proxy-ai` 預設模型為 `qwen2.5-coder:1.5b`（可用 `CLAW_MODEL` 環境變數覆蓋）。  
`--use-ai` 使用 claw 的串流輸出，在 Windows 上目前可能因 crossterm TTY 問題導致回應不顯示。

預設報告輸出到 `local_ai/eval_cases/eval_report.json`，可用 `--output FILE` 指定位置。

## Report 指標

每個 result 會包含：

- `answer_source`: `model`、`repaired_model`、`fallback_scaffold` 或 `no_answer`
- `used_fallback`: final answer 是否使用 fallback scaffold
- `compile_pass`: 是否能用本機 `cc/gcc/clang` 編譯
- `model_compile_pass`: fallback 前，模型答案若有可抽出的 C code，是否能編譯
- `run_pass`: 是否能用 `sample_input` 執行
- `keyword_pass`: 輸出是否包含 expected output keywords
- `structure_pass`: C code 是否包含必要結構關鍵字
- `model_score`: fallback 前，只用模型實際 C code 估算的分數
- `pipeline_score`: 允許 fallback scaffold 後的完整 pipeline 分數
- `score`: 兼容舊欄位，目前等同 `pipeline_score`

Top-level report 也會包含：

- `summary.total_cases`
- `summary.total_points`
- `summary.model_points`
- `summary.pipeline_points`
- `summary.fallback_cases`
- `summary.no_answer_cases`
- `summary.compile_pass_cases`
- `summary.run_pass_cases`
- `cases`: 每一題的完整 result

目前目標是 smoke test，不追求完美評分，也不取代人工閱卷。

`model_score` 衡量本地 AI 實際解 C 考題的能力；`pipeline_score` 衡量完整離線 assistant 在 fallback scaffold 允許下的穩定性。`fallback_scaffold` 不是正式考題解答，也不能代表模型會解題；它存在的目的只是讓模型 timeout、輸出格式失敗或無法抽出 C code 時，仍能穩定測試 checker、reporting、編譯與執行流程。

終端機摘要會分開顯示：

```text
Model Score: 14.9/65 points (22.9%)
Pipeline Score: 65/65 points (100.0%)
Fallback Used: 2 cases
```
