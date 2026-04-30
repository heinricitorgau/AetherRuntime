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

# 呼叫本地模型回答並評估
bash local_ai/run_eval.sh --use-ai

# 使用已準備好的 C 答案檔；檔名需為 <case_id>.c
bash local_ai/run_eval.sh --answers-dir /path/to/answers

# 篩選年份、題號或 topic
bash local_ai/run_eval.sh --filter 2024
bash local_ai/run_eval.sh --filter series
```

預設報告輸出到 `local_ai/eval_cases/eval_report.json`，可用 `--output FILE` 指定位置。

## Report 指標

每個 result 會包含：

- `compile_pass`: 是否能用本機 `cc/gcc/clang` 編譯
- `run_pass`: 是否能用 `sample_input` 執行
- `keyword_pass`: 輸出是否包含 expected output keywords
- `structure_pass`: C code 是否包含必要結構關鍵字
- `score`: 依上述 smoke checks 估算的分數

目前目標是 smoke test，不追求完美評分，也不取代人工閱卷。
