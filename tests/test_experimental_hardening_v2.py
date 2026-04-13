"""實驗性加固測試套件 v2（繁體中文標注）

涵蓋先前未覆蓋的模組：CostTracker、HistoryLog、DeferredInitResult、
PortContext、PrefetchResult、QueryRequest/QueryResponse，以及舊 Bug 的回歸驗證。
每個測試類別均明確記錄 Hypothesis（假設）、happy-path、edge-case 及 adversarial 情境。
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# H13 — CostTracker：正常累積行為
# 假設：record() 每次呼叫都正確累加 units，並記錄 label:units 事件。
# ─────────────────────────────────────────────────────────────────────────────
class TestCostTrackerNormalBehaviour(unittest.TestCase):
    """H13：CostTracker 正確累積 units 與 events。"""

    def setUp(self) -> None:
        from src.cost_tracker import CostTracker
        self.CostTracker = CostTracker

    def test_initial_state_is_zero(self) -> None:
        ct = self.CostTracker()
        self.assertEqual(ct.total_units, 0)
        self.assertEqual(ct.events, [])

    def test_single_record_adds_units(self) -> None:
        ct = self.CostTracker()
        ct.record("step", 5)
        self.assertEqual(ct.total_units, 5)

    def test_multiple_records_accumulate(self) -> None:
        ct = self.CostTracker()
        ct.record("a", 3)
        ct.record("b", 7)
        ct.record("c", 10)
        self.assertEqual(ct.total_units, 20)

    def test_event_format_is_label_colon_units(self) -> None:
        ct = self.CostTracker()
        ct.record("tokenize", 42)
        self.assertEqual(ct.events, ["tokenize:42"])

    def test_zero_units_recorded_without_error(self) -> None:
        ct = self.CostTracker()
        ct.record("noop", 0)
        self.assertEqual(ct.total_units, 0)
        self.assertIn("noop:0", ct.events)

    def test_large_units_accumulate_correctly(self) -> None:
        ct = self.CostTracker()
        for i in range(1000):
            ct.record(f"step_{i}", 1)
        self.assertEqual(ct.total_units, 1000)
        self.assertEqual(len(ct.events), 1000)


# ─────────────────────────────────────────────────────────────────────────────
# H14 — CostTracker：負數 units（對抗性輸入）
# 假設：傳入負數 units 應被拒絕或忽略，不應讓 total_units 變成負數。
# ─────────────────────────────────────────────────────────────────────────────
class TestCostTrackerAdversarialNegativeUnits(unittest.TestCase):
    """H14：負數 units 是對抗性輸入，total_units 不應為負。"""

    def setUp(self) -> None:
        from src.cost_tracker import CostTracker
        self.CostTracker = CostTracker

    def test_negative_units_must_not_make_total_negative(self) -> None:
        """BUG：record(-999) 會讓 total_units 變負數——修復後應拒絕負數。"""
        ct = self.CostTracker()
        ct.record("positive", 10)
        ct.record("attack", -999)
        self.assertGreaterEqual(
            ct.total_units, 0,
            "total_units 不應因負數 units 而變成負數"
        )

    def test_record_negative_only_must_not_go_below_zero(self) -> None:
        """直接傳入負數時 total_units 應維持 >= 0。"""
        ct = self.CostTracker()
        ct.record("neg", -1)
        self.assertGreaterEqual(ct.total_units, 0)


# ─────────────────────────────────────────────────────────────────────────────
# H15 — apply_cost_hook：回傳同一個 tracker，並正確呼叫 record()
# ─────────────────────────────────────────────────────────────────────────────
class TestApplyCostHook(unittest.TestCase):
    """H15：apply_cost_hook 回傳同一 tracker 實例且已累積。"""

    def test_returns_same_tracker_instance(self) -> None:
        from src.cost_tracker import CostTracker
        from src.costHook import apply_cost_hook
        ct = CostTracker()
        returned = apply_cost_hook(ct, "hook_event", 5)
        self.assertIs(returned, ct)

    def test_units_accumulated_after_hook(self) -> None:
        from src.cost_tracker import CostTracker
        from src.costHook import apply_cost_hook
        ct = CostTracker()
        apply_cost_hook(ct, "event", 7)
        self.assertEqual(ct.total_units, 7)

    def test_zero_units_hook_leaves_total_unchanged(self) -> None:
        from src.cost_tracker import CostTracker
        from src.costHook import apply_cost_hook
        ct = CostTracker(total_units=100)
        apply_cost_hook(ct, "noop", 0)
        self.assertEqual(ct.total_units, 100)


# ─────────────────────────────────────────────────────────────────────────────
# H16 — HistoryLog：as_markdown 格式正確性
# 假設：空日誌只有標題；每筆事件以 "- title: detail" 格式出現。
# ─────────────────────────────────────────────────────────────────────────────
class TestHistoryLogMarkdown(unittest.TestCase):
    """H16：HistoryLog.as_markdown() 格式正確。"""

    def test_empty_log_has_header_only(self) -> None:
        from src.history import HistoryLog
        hl = HistoryLog()
        md = hl.as_markdown()
        self.assertIn("# Session History", md)
        self.assertNotIn("- ", md)

    def test_single_event_appears_in_markdown(self) -> None:
        from src.history import HistoryLog
        hl = HistoryLog()
        hl.add("Login", "user authenticated")
        md = hl.as_markdown()
        self.assertIn("Login", md)
        self.assertIn("user authenticated", md)

    def test_multiple_events_all_appear(self) -> None:
        from src.history import HistoryLog
        hl = HistoryLog()
        hl.add("A", "first")
        hl.add("B", "second")
        hl.add("C", "third")
        md = hl.as_markdown()
        for label in ("A", "B", "C"):
            self.assertIn(label, md)

    def test_event_count_matches_lines_in_markdown(self) -> None:
        from src.history import HistoryLog
        hl = HistoryLog()
        for i in range(5):
            hl.add(f"step_{i}", f"detail_{i}")
        bullet_lines = [l for l in hl.as_markdown().splitlines() if l.startswith("- ")]
        self.assertEqual(len(bullet_lines), 5)

    def test_history_event_fields_accessible(self) -> None:
        from src.history import HistoryEvent
        e = HistoryEvent(title="boot", detail="system started")
        self.assertEqual(e.title, "boot")
        self.assertEqual(e.detail, "system started")

    def test_empty_title_and_detail_does_not_raise(self) -> None:
        """Edge case：空字串 title/detail 不應拋出例外。"""
        from src.history import HistoryLog
        hl = HistoryLog()
        try:
            hl.add("", "")
            hl.as_markdown()
        except Exception as exc:
            self.fail(f"空字串輸入導致例外：{exc}")


# ─────────────────────────────────────────────────────────────────────────────
# H17 — DeferredInitResult：trusted/untrusted 行為
# 假設：trusted=True 啟用所有功能；trusted=False 停用全部。
# ─────────────────────────────────────────────────────────────────────────────
class TestDeferredInit(unittest.TestCase):
    """H17：run_deferred_init 根據 trusted 旗標正確設定功能。"""

    def setUp(self) -> None:
        from src.deferred_init import run_deferred_init
        self.run_deferred_init = run_deferred_init

    def test_trusted_enables_all_features(self) -> None:
        result = self.run_deferred_init(True)
        self.assertTrue(result.plugin_init)
        self.assertTrue(result.skill_init)
        self.assertTrue(result.mcp_prefetch)
        self.assertTrue(result.session_hooks)

    def test_untrusted_disables_all_features(self) -> None:
        result = self.run_deferred_init(False)
        self.assertFalse(result.plugin_init)
        self.assertFalse(result.skill_init)
        self.assertFalse(result.mcp_prefetch)
        self.assertFalse(result.session_hooks)

    def test_trusted_flag_reflected_in_result(self) -> None:
        self.assertTrue(self.run_deferred_init(True).trusted)
        self.assertFalse(self.run_deferred_init(False).trusted)

    def test_as_lines_contains_four_items(self) -> None:
        result = self.run_deferred_init(True)
        lines = result.as_lines()
        self.assertEqual(len(lines), 4)

    def test_as_lines_contains_plugin_init_key(self) -> None:
        result = self.run_deferred_init(True)
        lines_text = " ".join(result.as_lines())
        self.assertIn("plugin_init=True", lines_text)

    def test_as_lines_does_not_include_trusted_field(self) -> None:
        """文件：as_lines() 目前不輸出 trusted 欄位（設計如此）。"""
        result = self.run_deferred_init(True)
        lines_text = " ".join(result.as_lines())
        self.assertNotIn("trusted=", lines_text)


# ─────────────────────────────────────────────────────────────────────────────
# H18 — PortContext：build_port_context 路徑與計數正確性
# 假設：以空 temp dir 建立時，所有計數為 0；archive_available=False。
# ─────────────────────────────────────────────────────────────────────────────
class TestPortContext(unittest.TestCase):
    """H18：build_port_context 根據目錄內容正確統計。"""

    def test_empty_root_all_counts_zero(self) -> None:
        from src.context import build_port_context
        with tempfile.TemporaryDirectory() as tmp:
            ctx = build_port_context(Path(tmp))
        self.assertEqual(ctx.python_file_count, 0)
        self.assertEqual(ctx.test_file_count, 0)
        self.assertEqual(ctx.asset_file_count, 0)
        self.assertFalse(ctx.archive_available)

    def test_src_python_files_counted(self) -> None:
        from src.context import build_port_context
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "module.py").write_text("x=1")
            (src / "utils.py").write_text("y=2")
            ctx = build_port_context(Path(tmp))
        self.assertEqual(ctx.python_file_count, 2)

    def test_tests_root_files_counted(self) -> None:
        from src.context import build_port_context
        with tempfile.TemporaryDirectory() as tmp:
            tst = Path(tmp) / "tests"
            tst.mkdir()
            (tst / "test_foo.py").write_text("")
            ctx = build_port_context(Path(tmp))
        self.assertEqual(ctx.test_file_count, 1)

    def test_archive_available_true_when_dir_exists(self) -> None:
        from src.context import build_port_context
        with tempfile.TemporaryDirectory() as tmp:
            arch = Path(tmp) / "archive" / "claude_code_ts_snapshot" / "src"
            arch.mkdir(parents=True)
            ctx = build_port_context(Path(tmp))
        self.assertTrue(ctx.archive_available)

    def test_render_context_includes_all_keys(self) -> None:
        from src.context import build_port_context, render_context
        with tempfile.TemporaryDirectory() as tmp:
            ctx = build_port_context(Path(tmp))
            text = render_context(ctx)
        for key in ("Source root:", "Test root:", "Python files:", "Archive available:"):
            self.assertIn(key, text)


# ─────────────────────────────────────────────────────────────────────────────
# H19 — PrefetchResult：start_* 函式回傳正確的 name 與 started=True
# 假設：所有 prefetch 函式都回傳 started=True（模擬，不管路徑是否存在）。
# ─────────────────────────────────────────────────────────────────────────────
class TestPrefetchResult(unittest.TestCase):
    """H19：prefetch 函式回傳 started=True 且 name 正確。"""

    def test_mdm_raw_read_started(self) -> None:
        from src.prefetch import start_mdm_raw_read
        r = start_mdm_raw_read()
        self.assertTrue(r.started)
        self.assertEqual(r.name, "mdm_raw_read")

    def test_keychain_prefetch_started(self) -> None:
        from src.prefetch import start_keychain_prefetch
        r = start_keychain_prefetch()
        self.assertTrue(r.started)
        self.assertEqual(r.name, "keychain_prefetch")

    def test_project_scan_started_for_existing_path(self) -> None:
        from src.prefetch import start_project_scan
        with tempfile.TemporaryDirectory() as tmp:
            r = start_project_scan(Path(tmp))
        self.assertTrue(r.started)
        self.assertIn(tmp, r.detail)

    def test_project_scan_started_even_for_nonexistent_path(self) -> None:
        """Edge case：模擬 prefetch 不驗證路徑是否存在。"""
        from src.prefetch import start_project_scan
        r = start_project_scan(Path("/totally/nonexistent/path"))
        self.assertTrue(r.started)

    def test_all_results_have_nonempty_detail(self) -> None:
        from src.prefetch import start_keychain_prefetch, start_mdm_raw_read
        for fn in (start_mdm_raw_read, start_keychain_prefetch):
            r = fn()
            self.assertTrue(r.detail, f"{fn.__name__} 的 detail 不應為空")


# ─────────────────────────────────────────────────────────────────────────────
# H20 — QueryRequest / QueryResponse：基本資料類別正確性
# 假設：這兩個 frozen dataclass 欄位可正確存取，且不可變。
# ─────────────────────────────────────────────────────────────────────────────
class TestQueryDataClasses(unittest.TestCase):
    """H20：QueryRequest 與 QueryResponse 欄位正確且不可變。"""

    def test_query_request_stores_prompt(self) -> None:
        from src.query import QueryRequest
        req = QueryRequest(prompt="find bugs")
        self.assertEqual(req.prompt, "find bugs")

    def test_query_response_stores_text(self) -> None:
        from src.query import QueryResponse
        resp = QueryResponse(text="no bugs found")
        self.assertEqual(resp.text, "no bugs found")

    def test_query_request_is_immutable(self) -> None:
        from src.query import QueryRequest
        req = QueryRequest(prompt="hello")
        with self.assertRaises(Exception):
            req.prompt = "modified"  # type: ignore[misc]

    def test_query_response_is_immutable(self) -> None:
        from src.query import QueryResponse
        resp = QueryResponse(text="result")
        with self.assertRaises(Exception):
            resp.text = "altered"  # type: ignore[misc]

    def test_empty_prompt_is_valid(self) -> None:
        """Edge case：空白 prompt 不應拋出例外。"""
        from src.query import QueryRequest
        req = QueryRequest(prompt="")
        self.assertEqual(req.prompt, "")

    def test_whitespace_only_prompt_preserved_as_is(self) -> None:
        """Edge case：純空白 prompt 照原樣儲存（無自動 strip）。"""
        from src.query import QueryRequest
        req = QueryRequest(prompt="   ")
        self.assertEqual(req.prompt, "   ")


# ─────────────────────────────────────────────────────────────────────────────
# H21 — Bug 回歸：Bug 1 與 Bug 2 修復後不可再現
# ─────────────────────────────────────────────────────────────────────────────
class TestRegressionBug1And2(unittest.TestCase):
    """H21：已修復的 Bug 1/2 確認不再重現。"""

    def test_bug1_empty_prefix_does_not_block_all_tools(self) -> None:
        """回歸：Bug 1 — 空 deny_prefix 不應封鎖所有工具。"""
        from src.permissions import ToolPermissionContext
        ctx = ToolPermissionContext.from_iterables(deny_prefixes=[""])
        self.assertFalse(ctx.blocks("BashTool"))
        self.assertFalse(ctx.blocks("FileReadTool"))
        self.assertFalse(ctx.blocks("anything"))

    def test_bug2_compact_zero_clears_entries(self) -> None:
        """回歸：Bug 2 — compact(0) 必須清空所有紀錄。"""
        from src.transcript import TranscriptStore
        ts = TranscriptStore(entries=["a", "b", "c", "d", "e"])
        ts.compact(0)
        self.assertEqual(len(ts.entries), 0)

    def test_bug2_compact_zero_on_single_entry(self) -> None:
        from src.transcript import TranscriptStore
        ts = TranscriptStore(entries=["only_one"])
        ts.compact(0)
        self.assertEqual(ts.entries, [])

    def test_bug1_whitespace_prefix_does_not_block(self) -> None:
        from src.permissions import ToolPermissionContext
        ctx = ToolPermissionContext.from_iterables(deny_prefixes=["  "])
        self.assertFalse(ctx.blocks("BashTool"))


if __name__ == "__main__":
    unittest.main()
