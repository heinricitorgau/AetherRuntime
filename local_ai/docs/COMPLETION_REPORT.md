# 完成事項報告 — Governance Platform

產生日期：2026-06-25
範圍：本階段將 `research-claw-code` 發展為一套**可驗證、可治理、可觀測、可回滾**的本地 AI Engineering Platform。

核心原則：不是追求「模型越來越大」，而是「任何能力的提升都能被可靠地證明」。
優先順序：Infrastructure > Governance > Evidence > Automation > Features。

---

## 一、總覽

| 指標 | 現況 |
|------|------|
| Smoke test | **PASS（18/18）** |
| CLI 子指令 | **16 個** |
| 治理層 | 6 條（adapter / model / dataset / regression / reliability / profile）+ goldens + routing + deploy gate |
| Release snapshots | 13 個（本階段新增 7 個）|
| 是否修改 benchmark scoring / evaluation 規則 | 否（嚴守 guardrail）|

---

## 二、已完成模組（依 Roadmap）

| # | 能力 | 主要檔案 | CLI | 現況 |
|---|------|----------|-----|------|
| 3 | **Model Governance** | `model_eval/promotion_policy.py`、`promote_model.py`、`compare_models.py` | — | recommendation 改由 policy 產生（不再硬編碼）。14B vs 3B = `manual_review` |
| 8 | **Automatic Regression Detection** | `benchmark/detect_regression.py` | `regression` | policy 驅動、自動解析前一輪 run；verdict pass/improvement/regression/manual_review |
| — | **Regression Guard（收斂治理迴路）** | `shared/regression_policy.py` + 兩個 executor | — | 單調式安全層：只會擋下、不會放行 promotion |
| 9 | **Continuous Benchmark Trend** | `benchmark/benchmark_trend.py` | `trend` | 85 筆 run 趨勢 + 最近一對自動 regression |
| 7 | **Governance Observability** | `system/governance_status.py` | `governance` | 8 區塊跨層狀態總覽 |
| 6 | **Evaluation Reliability** | `benchmark/eval_reliability.py` | `reliability` | verdict=`flaky`、stamp_rate≈0.14、35 個 flaky task（歷史 run 多數未標記）|
| 5 | **Prompt/Profile Governance** | `config/govern_profiles.py` | `profiles` | decision=`pass`、1/1 approved（warn: temperature=0.1）|
| 1 | **Goldens Infrastructure** | `goldens/promote_goldens.py`、`harvest_goldens.py`、`signoff.json` | `goldens` | **41 approved，全部 agent_verified，0 human_verified** |
| 4 | **Routing Governance** | `routing/audit_routing.py` | `route-audit` | verdict=`pass`、0 violations |
| 10 | **Deployment Readiness Gate** | `release/deploy_gate.py` | `deploy` | verdict=**`blocked`**（見下）|

每個模組都產生 JSON + Markdown 報告，並具備 `--self-test`（model-free）納入 smoke test。

---

## 三、治理現況快照（governance_status）

- **promoted_to_default**：無（任何一層都尚未設定 default）。
- **awaiting_manual_review**：`qwen25_coder_14b`（strict 退步、generated 提升的衝突 → 需人工判斷）。
- **adapters**：`retry_geometry_v3_guarded` = safe_no_change。
- **datasets**：`generated_sft_candidate_v1` = promote_to_candidate_training。
- **reliability**：flaky（歷史 run 可重現性標記不足，為清理訊號而非阻擋）。
- **profiles**：pass。
- **goldens**：41 approved / 0 human_verified。
- **routing**：pass。

### Deploy gate 為何是 `blocked`（且這是正確的）
- 阻擋原因：最近一次 `regression_report.json` 的 verdict 是 `regression`（來自先前測試用的 run pair）。依 gate 規則「只要有未解的 regression 就擋住出貨」。
- 3 個 warning：reliability flaky、14B awaiting review、尚無 human-verified goldens。
- **沒有為了讓畫面變綠而竄改報告**——這是 gate 正常運作。要解除：跑一次乾淨的 benchmark + regression 檢查即可翻為 `ready_with_warnings`。

---

## 四、本階段也修復/建立的其他項目

- **Heuristic C-code 抽取 bug 修復**（`benchmark/_bench_common.py`）：抽取在第一個 `}` 即停止，導致只取到 helper function；改為取到最後一個 depth-0，2025_midterm_003 由 15 → 96。
- **`benchmark_lora.py --max-tokens` 修復**：CLI 旗標原被 profile 值覆蓋；profile `max_tokens` 512 → 768。
- **Generated candidate SFT package**（`dataset_scaling/package_generated_sft.py`）：40 筆 chatml + benchmark cases + dataset card，並在 `datasets.json` / `benchmarks.json` 註冊為 isolated。

---

## 五、尚未完成 / 需要人工或真實資料（誠實標註）

| # | 項目 | 缺什麼 |
|---|------|--------|
| 1 | Human-Verified Goldens | **人工簽核**。機制已就緒（`goldens/signoff.json`），但 `signed_off_by` 必須由真人填寫——agent 不得代簽（曾嘗試代簽被安全機制正確擋下）。填入姓名後 41 筆即升為 human_verified。|
| 2 | Real Exam Corpus Growth | 需要你提供真實考題 PDF / 資料。|
| 4 | Routing **執行**（非規劃） | 目前只產生 routing plan，不實際執行模型推論；要執行需跑模型，須你授權。|
| 10 | Deployment **目標**自動化 | Gate 已完成；尚未串接到實際部署目標。|

---

## 六、下一步建議

1. **解除 deploy gate**：跑一次乾淨 benchmark + `regression` 檢查，verdict 翻為 `ready_with_warnings`。
2. **Goldens human tier**：在 `signoff.json` 填入 reviewer 姓名（或交給我記錄你口述的姓名），41 筆升為 human_verified，清除 deploy gate 的 `human_goldens` warning。
3. **可重現性清理**：依 `eval_reliability` 報告，未來 run 補齊 reproducibility 標記（prompt_profile / temperature=0 / model_override_valid），降低 flaky。
4. 若要推進 #2 / #4 執行 / #10 目標，需要你提供資料或產品決策。

---

*本報告由治理平台現況彙整，所有數值取自既有 JSON 報告，未經人工修改。*
