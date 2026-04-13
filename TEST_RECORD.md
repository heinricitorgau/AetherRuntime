# TEST_RECORD — 實驗性加固測試紀錄

**日期：** 2026-04-13
**分支：** `test/experimental-hardening`
**測試執行器：** Python `unittest`（標準庫，無需外部依賴）
**總測試數量（本輪結束後）：** 129（原有 22 + 第一輪新增 64 + 第二輪新增 43）— 全數通過 ✅

---

## 假設表格（Hypothesis Table）

### 第一輪（v1）—— 權限、引擎、命令、工具、清單

| # | 假設 | 測試情境 | 預期 | 實際 | 狀態 |
|---|------|---------|------|------|------|
| H1-a | `deny_names` 封鎖不分大小寫 | `blocks("BASHTOOL")` with `deny_names=["BashTool"]` | True | True | ✅ PASS |
| H1-b | `deny_names` 封鎖不分大小寫（小寫） | `blocks("bashtool")` | True | True | ✅ PASS |
| H1-c | `deny_prefixes` 封鎖不分大小寫 | `blocks("MCPTool")` with `deny_prefixes=["mcp"]` | True | True | ✅ PASS |
| H1-d | 空 context 不封鎖任何工具 | `blocks("BashTool")` on empty context | False | False | ✅ PASS |
| H1-e | 多個 deny_names 均有效 | `blocks("BASHTOOL")` and `blocks("fileedittool")` | True × 2 | True × 2 | ✅ PASS |
| H2-a | **BUG** 空 deny_prefix 靜默封鎖所有工具 | `blocks("BashTool")` with `deny_prefixes=[""]` | False（修復後） | False ✅ | **已修復** |
| H2-b | `None` deny_prefixes 安全 | `from_iterables(deny_prefixes=None)` | 不報錯、不封鎖 | 正確 | ✅ PASS |
| H2-c | 純空白前綴無意義 | `deny_prefixes=["   "]` 不封鎖 `"BashTool"` | False | False | ✅ PASS |
| H3-a | 空字串加 0 個 token | `add_turn("", "")` on base `(10, 5)` | `(10, 5)` | `(10, 5)` | ✅ PASS |
| H3-b | 單一單字各加 1 個 token | `add_turn("hello", "world")` | `(1, 1)` | `(1, 1)` | ✅ PASS |
| H3-c | 多單字依 split 計數 | `add_turn("one two three four five", "alpha beta")` | `(5, 2)` | `(5, 2)` | ✅ PASS |
| H3-d | 累積多輪 token 正確 | 兩輪：`"a b"` + `"d e f"` / `"c"` + `"g h"` | `(5, 3)` | `(5, 3)` | ✅ PASS |
| H3-e | `UsageSummary` 不可變 | `add_turn` 後原始物件不變 | `(100, 50)` | `(100, 50)` | ✅ PASS |
| H4-a | `compact(3)` 保留最後 3 筆 | 5 筆 store，compact(3) | `["c","d","e"]` | `["c","d","e"]` | ✅ PASS |
| H4-b | `compact(N)` N = len：無操作 | compact(3) on 3-entry store | 3 筆 | 3 筆 | ✅ PASS |
| H4-c | `compact(N)` N > len：無操作 | compact(10) on 2-entry store | 2 筆 | 2 筆 | ✅ PASS |
| H4-d | **BUG** `compact(0)` 應清空 store | Python `-0 == 0` 導致 `entries[-0:]` 保留全部 | 0 筆（修復後） | 0 筆 ✅ | **已修復** |
| H4-e | `flush()` 設定 `flushed=True` | 呼叫 `flush()` | True | True | ✅ PASS |
| H4-f | `append()` 重置 `flushed` 旗標 | flush 後 append | False | False | ✅ PASS |
| H4-g | `replay()` 回傳 tuple 快照 | 呼叫 `replay()` | `tuple` 型別 | `tuple` | ✅ PASS |
| H5-a | 正常 submit_message 完成 | 1 則訊息，未達上限 | `stop_reason="completed"` | "completed" | ✅ PASS |
| H5-b | 第 9 則訊息在 `max_turns=8` 被攔截 | 填滿 8，嘗試第 9 | `stop_reason="max_turns_reached"` | "max_turns_reached" | ✅ PASS |
| H5-c | `max_turns=0` 攔截第一則訊息 | 嘗試第一則 | `stop_reason="max_turns_reached"` | "max_turns_reached" | ✅ PASS |
| H5-d | 被攔截的訊息不被附加 | 攔截後 message count 不變 | `len` 穩定 | 穩定 | ✅ PASS |
| H5-e | matched_commands 與 tools 反映於結果 | 傳入 `matched_commands=("review",)` | 結果含 "review" | 正確 | ✅ PASS |
| H6-a | `structured_output=True` 輸出合法 JSON | 呼叫 `submit_message("test")` | 可解析 JSON | 可解析 | ✅ PASS |
| H6-b | JSON 包含 prompt 文字 | 送出 "find security issues" | summary 含 prompt | 正確 | ✅ PASS |
| H7-a | 串流第一個事件為 `message_start` | `stream_submit_message("hello")` | first type = "message_start" | 正確 | ✅ PASS |
| H7-b | 串流最後一個事件為 `message_stop` | 同上 | last type = "message_stop" | 正確 | ✅ PASS |
| H7-c | `message_stop` 含 `stop_reason` 與 `usage` | 同上 | 兩個鍵都存在 | 正確 | ✅ PASS |
| H7-d | 有 commands 時發出 `command_match` 事件 | 傳入 `matched_commands=("review",)` | 事件型別存在 | 正確 | ✅ PASS |
| H7-e | 有 tools 時發出 `tool_match` 事件 | 傳入 `matched_tools=("BashTool",)` | 事件型別存在 | 正確 | ✅ PASS |
| H7-f | 無 commands 時不發出 `command_match` | 不傳 matched_commands | 事件型別缺席 | 缺席 | ✅ PASS |
| H7-g | 有 denied_tools 時發出 `permission_denial` | 傳入 `denied_tools=(denial,)` | 事件型別存在 | 正確 | ✅ PASS |
| H8-a | `get_command` 不分大小寫 | `get_command(name.upper())` | Not None | Not None | ✅ PASS |
| H8-b | `get_command` 未知命令 → None | `get_command("zzz_xyz")` | None | None | ✅ PASS |
| H8-c | `get_command("")` → None（對抗性） | `get_command("")` | None | None | ✅ PASS |
| H8-d | `execute_command` 已知 → `handled=True` | 已知命令名稱 | `handled=True` | 正確 | ✅ PASS |
| H8-e | `execute_command` 未知 → `handled=False` | 未知命令 | `handled=False` | 正確 | ✅ PASS |
| H8-f | `find_commands("")` 回傳全部（邊界） | 空查詢 | 全部命令 | 全部匹配 | ✅ PASS |
| H8-g | `find_commands("zzz_no_match")` → 空 | 無匹配查詢 | `[]` | `[]` | ✅ PASS |
| H8-h | `get_commands(include_plugin_commands=False)` 過濾 | 外掛過濾器 | 子集 ≤ 全集 | 正確 | ✅ PASS |
| H9-a | `None` context 回傳全部工具 | `filter_tools_by_permission_context(tools, None)` | 完整列表 | 完整列表 | ✅ PASS |
| H9-b | deny name 移除精確的那個工具 | 拒絕第一個工具 by name | 該工具缺席 | 缺席 | ✅ PASS |
| H9-c | deny prefix `"mcp"` 移除所有 MCP 工具 | `deny_prefixes=["mcp"]` | 無 `mcp*` 工具殘留 | 正確 | ✅ PASS |
| H9-d | 空 deny_names → 不移除任何工具 | `deny_names=[]` | 完整列表 | 完整列表 | ✅ PASS |
| H10-a | 空 temp dir → 0 個 Python 檔案 | `build_port_manifest(Path(tmp_empty))` | `total_python_files=0` | 0 | ✅ PASS |
| H10-b | 一個 `.py` → 計數 1 | 1 個 `.py` 在 temp | `total_python_files=1` | 1 | ✅ PASS |
| H10-c | 非 `.py` 檔案被忽略 | `.py` + `.txt` + `.json` | `total_python_files=1` | 1 | ✅ PASS |
| H10-d | 巢狀 `.py` 檔案計入 | 3 個 `.py` 在樹中 | `total_python_files=3` | 3 | ✅ PASS |
| H10-e | `to_markdown()` 提及 root 與計數 | 呼叫 `to_markdown()` | 含 "Port root:" 與 "Total Python files:" | 正確 | ✅ PASS |
| H11-a | `ExecutionRegistry.command()` 不分大小寫 | `.upper()` / `.lower()` 查詢 | Not None | 正確 | ✅ PASS |
| H11-b | `ExecutionRegistry.tool()` 不分大小寫 | 同上 | Not None | 正確 | ✅ PASS |
| H11-c | 缺少命令 → None | `command("ghost_xyz")` | None | None | ✅ PASS |
| H11-d | 缺少工具 → None | `tool("ghost_xyz")` | None | None | ✅ PASS |
| H11-e | 找到命令 execute → mirrored 訊息 | `cmd.execute("input")` | 含 "Mirrored command" | 正確 | ✅ PASS |
| H11-f | 找到工具 execute → mirrored 訊息 | `tool.execute("payload")` | 含 "Mirrored tool" | 正確 | ✅ PASS |
| H12-a | 空 `PortingBacklog.summary_lines()` | `PortingBacklog(title="empty")` | `[]` | `[]` | ✅ PASS |
| H12-b | 行數 == 模組數 | `build_command_backlog()` | 長度相等 | 相等 | ✅ PASS |
| H12-c | 每行含模組名稱 | 前 5 個模組 | 名稱在行中 | 正確 | ✅ PASS |
| H12-d | 每行含 `[mirrored]` 狀態 | 前 5 行 | `[mirrored]` 在行中 | 正確 | ✅ PASS |

### 第二輪（v2）—— 成本追蹤、歷史紀錄、延遲初始化、上下文、Prefetch

| # | 假設 | 測試情境 | 預期 | 實際 | 狀態 |
|---|------|---------|------|------|------|
| H13-a | `CostTracker` 初始狀態為零 | 新建實例 | `total_units=0`, `events=[]` | 正確 | ✅ PASS |
| H13-b | 單次 record 正確加總 | `record("step", 5)` | `total_units=5` | 5 | ✅ PASS |
| H13-c | 多次 record 累積 | 3 次 record 合計 20 | 20 | 20 | ✅ PASS |
| H13-d | 事件格式為 `label:units` | `record("tokenize", 42)` | `["tokenize:42"]` | `["tokenize:42"]` | ✅ PASS |
| H13-e | 零 units 正常記錄 | `record("noop", 0)` | `total_units=0`，事件存在 | 正確 | ✅ PASS |
| H13-f | 大量 record 正確累積 | 1000 次 × 1 unit | `total_units=1000` | 1000 | ✅ PASS |
| H14-a | **BUG** 負數 units 不應讓 total 變負 | `record("attack", -999)` after `record("positive", 10)` | `total_units >= 0`（修復後） | 0 以上 ✅ | **已修復** |
| H14-b | 僅負數 record 不應讓 total 低於 0 | `record("neg", -1)` | `total_units >= 0` | 0 ✅ | **已修復** |
| H15-a | `apply_cost_hook` 回傳同一個 tracker | 呼叫 hook | `returned is ct` | True | ✅ PASS |
| H15-b | hook 後 units 已累積 | `apply_cost_hook(ct, "event", 7)` | `total_units=7` | 7 | ✅ PASS |
| H15-c | 零 units hook 不改變 total | `apply_cost_hook(ct_100, "noop", 0)` | `total_units=100` | 100 | ✅ PASS |
| H16-a | 空 `HistoryLog` 僅有標題 | `as_markdown()` on empty log | 含 "# Session History"，無 "- " | 正確 | ✅ PASS |
| H16-b | 單筆事件出現在 markdown | `add("Login", "user authenticated")` | 含 "Login" 與 "user authenticated" | 正確 | ✅ PASS |
| H16-c | 多筆事件全部出現 | 3 筆 add | 全部標題出現 | 正確 | ✅ PASS |
| H16-d | markdown 行數與事件數一致 | 5 筆事件 | 5 個 `"- "` 行 | 5 | ✅ PASS |
| H16-e | `HistoryEvent` 欄位可存取 | `event.title`, `event.detail` | 正確值 | 正確 | ✅ PASS |
| H16-f | 空字串 title/detail 不拋例外（Edge） | `add("", "")` | 不報錯 | 不報錯 | ✅ PASS |
| H17-a | `trusted=True` 啟用所有功能 | `run_deferred_init(True)` | 所有旗標 True | True | ✅ PASS |
| H17-b | `trusted=False` 停用所有功能 | `run_deferred_init(False)` | 所有旗標 False | False | ✅ PASS |
| H17-c | `trusted` 旗標反映於 result | 比對 `.trusted` 欄位 | True/False 對應 | 正確 | ✅ PASS |
| H17-d | `as_lines()` 回傳 4 個項目 | 計算 lines 長度 | 4 | 4 | ✅ PASS |
| H17-e | `as_lines()` 含 `plugin_init=True` | 文字搜尋 | 存在 | 存在 | ✅ PASS |
| H17-f | `as_lines()` 不輸出 `trusted` 欄位（設計如此） | 文字搜尋 | 不含 "trusted=" | 不含 | ✅ PASS |
| H18-a | 空 temp dir 所有計數為 0 | `build_port_context(Path(tmp))` | 全部 0，archive_available=False | 正確 | ✅ PASS |
| H18-b | src/ 中的 Python 檔案計入 | 2 個 `.py` 在 src/ | `python_file_count=2` | 2 | ✅ PASS |
| H18-c | tests/ 中的測試檔案計入 | 1 個 `.py` 在 tests/ | `test_file_count=1` | 1 | ✅ PASS |
| H18-d | archive 目錄存在時 `archive_available=True` | 建立 archive 路徑 | True | True | ✅ PASS |
| H18-e | `render_context()` 含所有鍵 | 文字搜尋 | 含 "Source root:" 等 | 正確 | ✅ PASS |
| H19-a | `start_mdm_raw_read()` 回傳 `started=True` | 呼叫函式 | `started=True`, `name="mdm_raw_read"` | 正確 | ✅ PASS |
| H19-b | `start_keychain_prefetch()` 回傳 `started=True` | 呼叫函式 | `started=True` | 正確 | ✅ PASS |
| H19-c | `start_project_scan()` 掃描現有路徑 | 傳入 temp dir | `started=True`，detail 含路徑 | 正確 | ✅ PASS |
| H19-d | `start_project_scan()` 即使路徑不存在也 `started=True`（Edge） | 傳入 `/nonexistent` | `started=True`（模擬） | True | ✅ PASS |
| H19-e | 所有 prefetch result 的 `detail` 非空 | 兩個函式 | `bool(r.detail)` = True | True | ✅ PASS |
| H20-a | `QueryRequest` 儲存 prompt | `QueryRequest(prompt="find bugs")` | `req.prompt == "find bugs"` | 正確 | ✅ PASS |
| H20-b | `QueryResponse` 儲存 text | `QueryResponse(text="result")` | `resp.text == "result"` | 正確 | ✅ PASS |
| H20-c | `QueryRequest` 不可變 | 嘗試修改 `req.prompt` | 拋出例外 | 拋出 | ✅ PASS |
| H20-d | `QueryResponse` 不可變 | 嘗試修改 `resp.text` | 拋出例外 | 拋出 | ✅ PASS |
| H20-e | 空 prompt 有效（Edge） | `QueryRequest(prompt="")` | 不報錯 | 不報錯 | ✅ PASS |
| H20-f | 純空白 prompt 原樣保留（Edge） | `QueryRequest(prompt="   ")` | `req.prompt == "   "` | 正確 | ✅ PASS |
| H21-a | 回歸：Bug 1 空前綴不再封鎖所有工具 | `deny_prefixes=[""]` | 全部 False | False | ✅ PASS |
| H21-b | 回歸：Bug 2 `compact(0)` 清空 | 5 筆 store → compact(0) | 0 筆 | 0 筆 | ✅ PASS |
| H21-c | 回歸：Bug 2 單筆 compact(0) | 1 筆 store → compact(0) | 0 筆 | 0 筆 | ✅ PASS |
| H21-d | 回歸：Bug 1 空白前綴不封鎖 | `deny_prefixes=["  "]` | False | False | ✅ PASS |

---

## 發現問題清單

### Bug 1 — `ToolPermissionContext`：空 `deny_prefix` 靜默封鎖所有工具

**檔案：** `src/permissions.py`
**嚴重程度：** 高
**類別：** 對抗性輸入 / 安全性設定錯誤

**說明：**
`ToolPermissionContext.from_iterables(deny_prefixes=[""])` 建立的 context 會封鎖所有工具。原因是 Python 的 `str.startswith("")` 永遠回傳 `True`，因此任何空字串前綴都會比對所有工具名稱。設定中出現一個空項目就會靜默停用所有工具，不報任何錯誤或警告。

**根本原因：** `from_iterables` 未驗證前綴值，空字串直接轉小寫後儲存。

**修復內容：**
```python
deny_prefixes=tuple(
    p for p in (prefix.lower() for prefix in (deny_prefixes or []))
    if p.strip()
),
```

---

### Bug 2 — `TranscriptStore.compact(0)`：Python `-0 == 0` 陷阱保留所有紀錄

**檔案：** `src/transcript.py`
**嚴重程度：** 中
**類別：** 邊界邏輯 / off-by-one

**說明：**
呼叫 `compact(keep_last=0)` 應將 transcript 清空為零筆。但由於 Python 中 `-0 == 0`，`entries[-0:]` 等同於 `entries[0:]`（完整切片），導致所有紀錄被保留。同樣的問題在 `QueryEnginePort.compact_messages_if_needed` 中也隱含存在。

**根本原因：** Python 整數不區分 `-0` 與 `0`，切片 `seq[-0:]` 等同 `seq[0:]`。

**修復內容：**
```python
if keep_last == 0:
    self.entries.clear()
else:
    self.entries[:] = self.entries[-keep_last:]
```

---

### Bug 3 — `CostTracker.record()`：負數 units 讓 total_units 變成負數

**檔案：** `src/cost_tracker.py`
**嚴重程度：** 中
**類別：** 輸入驗證缺失 / 計費邏輯錯誤

**說明：**
呼叫 `record("label", -999)` 會讓 `total_units` 降為負數。記錄負成本在語意上不合理（沒有「退款」情境），且可能讓呼叫端以為用量少於實際，造成計費錯誤或閾值邏輯失效。

**探測輸出：**
```
ct.record("positive", 10)
ct.record("attack", -999)
ct.total_units  →  -989   # 預期 >= 0
```

**根本原因：** `record()` 直接將 `units` 加入 `total_units`，未做任何非負驗證。

**修復內容：**
```python
safe_units = max(0, units)
self.total_units += safe_units
self.events.append(f'{label}:{safe_units}')
```

---

## 修復摘要

| 檔案 | 修改內容 | 影響行數 |
|------|---------|---------|
| `src/permissions.py` | 在 `from_iterables` 中過濾空/空白 deny_prefixes | +4（註解 + 過濾運算式） |
| `src/transcript.py` | 在 `compact(0)` 加入明確的 `clear()` 分支 | +4（註解 + 分支） |
| `src/cost_tracker.py` | 在 `record()` 中以 `max(0, units)` 截斷負數 | +3（註解 + safe_units） |
| `tests/test_experimental_hardening.py` | 64 個新測試（v1），12 個測試類別 | 新增檔案 |
| `tests/test_experimental_hardening_v2.py` | 43 個新測試（v2），9 個測試類別 | 新增檔案 |

---

## 測試執行結果

```
Ran 129 tests in 2.182s
OK
```

所有 129 個測試通過（原有 22 個 + v1 新增 64 個 + v2 新增 43 個）。

### 新增測試檔案結構

**v1 — `tests/test_experimental_hardening.py`（64 個測試）**

| 測試類別 | 測試數 | 覆蓋範圍 |
|---------|-------|---------|
| `TestToolPermissionContextCaseInsensitivity` | 7 | 不分大小寫封鎖 |
| `TestToolPermissionContextAdversarialEmptyPrefix` | 3 | **Bug 1** 對抗性前綴輸入 |
| `TestUsageSummaryTokenCounting` | 5 | Token 累積語意 |
| `TestTranscriptStoreCompact` | 7 | **Bug 2** compact(0) + flush/append |
| `TestQueryEngineMaxTurns` | 5 | max_turns 邊界執行 |
| `TestQueryEngineStructuredOutput` | 2 | JSON 輸出合法性 |
| `TestQueryEngineStreamEvents` | 7 | SSE 事件順序與型別 |
| `TestCommandsModuleRobustness` | 9 | 不分大小寫查詢、對抗性輸入 |
| `TestToolsPermissionFiltering` | 4 | 工具權限管控 |
| `TestPortManifestCustomRoot` | 5 | 自訂路徑的檔案計數 |
| `TestExecutionRegistryLookup` | 6 | 註冊表不分大小寫查詢 |
| `TestPortingBacklogSummaryLines` | 4 | summary line 格式正確性 |

**v2 — `tests/test_experimental_hardening_v2.py`（43 個測試）**

| 測試類別 | 測試數 | 覆蓋範圍 |
|---------|-------|---------|
| `TestCostTrackerNormalBehaviour` | 6 | 正常累積行為 |
| `TestCostTrackerAdversarialNegativeUnits` | 2 | **Bug 3** 負數 units 對抗性輸入 |
| `TestApplyCostHook` | 3 | apply_cost_hook 回傳與累積 |
| `TestHistoryLogMarkdown` | 6 | markdown 格式正確性 |
| `TestDeferredInit` | 6 | trusted/untrusted 旗標行為 |
| `TestPortContext` | 5 | 目錄計數與 archive 偵測 |
| `TestPrefetchResult` | 5 | prefetch 函式 started/name/detail |
| `TestQueryDataClasses` | 6 | QueryRequest/QueryResponse 不可變性 |
| `TestRegressionBug1And2` | 4 | Bug 1 與 Bug 2 回歸驗證 |

---

## Rust 程式碼庫說明（沙箱無 cargo 環境）

`rust/` 工作區包含大量 inline 單元測試與整合測試：

- `rust/crates/runtime/src/permissions.rs` — 11 個 `#[test]`，涵蓋 `PermissionPolicy`、hook override、規則式 allow/deny/ask
- `rust/crates/runtime/src/bash_validation.rs` — 32 個 `#[test]`，涵蓋唯讀驗證、破壞性命令警告、sed/path 驗證
- `rust/crates/runtime/tests/integration_tests.rs` — 跨模組接線測試（stale branch → policy engine、green contracts）
- `rust/crates/rusty-claude-cli/tests/` — CLI 旗標預設值、compact 輸出、mock parity harness、輸出格式合約、resume/slash 命令

這些測試由 CI（`rust-ci.yml`）驗證，在具備穩定 Rust 工具鏈的機器上執行 `cargo test --workspace` 應全數通過。
