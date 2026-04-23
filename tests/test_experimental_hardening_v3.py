"""
實驗性加固測試 v3（第三輪）

覆蓋範圍：
  - session_store  — 保存/讀取回路、缺少檔案、損壞 JSON、欄位缺失
  - parity_audit   — to_markdown 行為（archive 不存在 / 存在）
  - remote_runtime — RuntimeModeReport 格式與不可變性
  - query_engine   — 預算耗盡（max_budget_reached）不再累積訊息（Bug 4 修復）、
                     compaction 觸發、persist + restore 回路、render_summary

新發現 Bug：
  Bug 4 — QueryEnginePort.submit_message 在 max_budget_reached 後仍累積訊息
  Bug 5 — session_store.load_session 對缺少/損壞的 JSON 無有意義的錯誤訊息
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# 確保 src/ 在搜尋路徑
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.session_store import StoredSession, load_session, save_session
from src.parity_audit import ParityAuditResult, run_parity_audit
from src.remote_runtime import RuntimeModeReport, run_remote_mode, run_ssh_mode, run_teleport_mode
from src.query_engine import QueryEngineConfig, QueryEnginePort
from src.port_manifest import build_port_manifest


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_engine(max_turns: int = 8, max_budget_tokens: int = 2000,
                 compact_after_turns: int = 12) -> QueryEnginePort:
    config = QueryEngineConfig(
        max_turns=max_turns,
        max_budget_tokens=max_budget_tokens,
        compact_after_turns=compact_after_turns,
    )
    return QueryEnginePort(manifest=build_port_manifest(), config=config)


# ---------------------------------------------------------------------------
# session_store — 正常 save / load 回路
# ---------------------------------------------------------------------------

class TestSessionStoreRoundtrip(unittest.TestCase):
    """儲存後讀取必須完整還原所有欄位。"""

    def test_roundtrip_preserves_session_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            s = StoredSession('abc123', ('hello', 'world'), 10, 5)
            save_session(s, d)
            loaded = load_session('abc123', d)
            self.assertEqual(loaded.session_id, 'abc123')

    def test_roundtrip_preserves_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            s = StoredSession('sess1', ('msg_a', 'msg_b', 'msg_c'), 30, 15)
            save_session(s, d)
            loaded = load_session('sess1', d)
            self.assertEqual(loaded.messages, ('msg_a', 'msg_b', 'msg_c'))

    def test_roundtrip_preserves_token_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            s = StoredSession('tok_test', (), 999, 42)
            save_session(s, d)
            loaded = load_session('tok_test', d)
            self.assertEqual(loaded.input_tokens, 999)
            self.assertEqual(loaded.output_tokens, 42)

    def test_roundtrip_empty_messages(self):
        """空 messages tuple 回路不應失敗。"""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            s = StoredSession('empty_sess', (), 0, 0)
            save_session(s, d)
            loaded = load_session('empty_sess', d)
            self.assertEqual(loaded.messages, ())

    def test_messages_restored_as_tuple(self):
        """JSON 儲存為 list，load 後必須轉回 tuple。"""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            s = StoredSession('tup', ('x', 'y'), 1, 1)
            save_session(s, d)
            loaded = load_session('tup', d)
            self.assertIsInstance(loaded.messages, tuple)

    def test_save_returns_path_that_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            s = StoredSession('path_test', ('a',), 1, 1)
            p = save_session(s, d)
            self.assertTrue(Path(p).exists())


# ---------------------------------------------------------------------------
# session_store — Bug 5：缺少 / 損壞 / 欄位不足的錯誤處理
# ---------------------------------------------------------------------------

class TestSessionStoreErrorHandling(unittest.TestCase):
    """Bug 5 — load_session 對缺少或損壞的 JSON 無有意義的錯誤訊息（已修復）。"""

    def test_missing_file_raises_file_not_found(self):
        """H22-a：不存在的 session_id 應拋出 FileNotFoundError，且訊息含 session_id。"""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError) as ctx:
                load_session('nonexistent_session', Path(tmp))
            self.assertIn('nonexistent_session', str(ctx.exception))

    def test_missing_file_error_mentions_path(self):
        """H22-b：錯誤訊息應提及檔案路徑，方便除錯。"""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError) as ctx:
                load_session('ghost', Path(tmp))
            self.assertIn('ghost', str(ctx.exception))

    def test_corrupted_json_raises_value_error(self):
        """H22-c：損壞的 JSON 應拋出 ValueError，且訊息含 session_id。"""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / 'bad_json.json').write_text('{NOT VALID JSON')
            with self.assertRaises(ValueError) as ctx:
                load_session('bad_json', d)
            self.assertIn('bad_json', str(ctx.exception))

    def test_missing_fields_raises_value_error(self):
        """H22-d：缺欄位的 JSON 應拋出 ValueError，且訊息列出缺少的欄位。"""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / 'partial.json').write_text(json.dumps({'session_id': 'partial'}))
            with self.assertRaises(ValueError) as ctx:
                load_session('partial', d)
            err = str(ctx.exception)
            self.assertIn('messages', err)


# ---------------------------------------------------------------------------
# parity_audit — to_markdown 行為
# ---------------------------------------------------------------------------

class TestParityAuditMarkdown(unittest.TestCase):
    """ParityAuditResult.to_markdown() 在各種狀態下的輸出格式。"""

    def test_no_archive_returns_unavailable_message(self):
        """H23-a：archive_present=False 時，markdown 說明無法比較。"""
        result = ParityAuditResult(
            archive_present=False,
            root_file_coverage=(0, 10),
            directory_coverage=(0, 10),
            total_file_ratio=(0, 100),
            command_entry_ratio=(0, 50),
            tool_entry_ratio=(0, 30),
            missing_root_targets=(),
            missing_directory_targets=(),
        )
        md = result.to_markdown()
        self.assertIn('unavailable', md.lower())
        self.assertNotIn('Root file coverage', md)

    def test_archive_present_shows_coverage(self):
        """H23-b：archive_present=True 時，markdown 含 Root file coverage。"""
        result = ParityAuditResult(
            archive_present=True,
            root_file_coverage=(15, 18),
            directory_coverage=(20, 25),
            total_file_ratio=(80, 100),
            command_entry_ratio=(40, 50),
            tool_entry_ratio=(25, 30),
            missing_root_targets=(),
            missing_directory_targets=(),
        )
        md = result.to_markdown()
        self.assertIn('15/18', md)
        self.assertIn('20/25', md)

    def test_no_missing_targets_shows_none(self):
        """H23-c：無缺少目標時，markdown 顯示 'none'。"""
        result = ParityAuditResult(
            archive_present=True,
            root_file_coverage=(18, 18),
            directory_coverage=(25, 25),
            total_file_ratio=(100, 100),
            command_entry_ratio=(50, 50),
            tool_entry_ratio=(30, 30),
            missing_root_targets=(),
            missing_directory_targets=(),
        )
        md = result.to_markdown()
        self.assertIn('none', md)

    def test_missing_targets_listed(self):
        """H23-d：有缺少目標時，markdown 列出各目標名稱。"""
        result = ParityAuditResult(
            archive_present=True,
            root_file_coverage=(10, 12),
            directory_coverage=(8, 10),
            total_file_ratio=(50, 100),
            command_entry_ratio=(30, 50),
            tool_entry_ratio=(20, 30),
            missing_root_targets=('foo.py', 'bar.py'),
            missing_directory_targets=('baz',),
        )
        md = result.to_markdown()
        self.assertIn('foo.py', md)
        self.assertIn('bar.py', md)
        self.assertIn('baz', md)

    def test_run_parity_audit_returns_result(self):
        """H23-e：run_parity_audit() 不拋出例外，回傳 ParityAuditResult。"""
        result = run_parity_audit()
        self.assertIsInstance(result, ParityAuditResult)

    def test_run_parity_audit_coverage_nonnegative(self):
        """H23-f：覆蓋率分子不超過分母（合理性檢查）。"""
        result = run_parity_audit()
        self.assertLessEqual(result.root_file_coverage[0], result.root_file_coverage[1])
        self.assertLessEqual(result.directory_coverage[0], result.directory_coverage[1])


# ---------------------------------------------------------------------------
# remote_runtime — RuntimeModeReport 格式與不可變性
# ---------------------------------------------------------------------------

class TestRemoteRuntimeReports(unittest.TestCase):
    """RuntimeModeReport.as_text() 格式與各模式行為。"""

    def test_remote_mode_connected(self):
        """H24-a：run_remote_mode 回傳 connected=True。"""
        report = run_remote_mode('prod-server')
        self.assertTrue(report.connected)

    def test_remote_mode_detail_contains_target(self):
        """H24-b：detail 含 target 字串。"""
        report = run_remote_mode('prod-server')
        self.assertIn('prod-server', report.detail)

    def test_ssh_mode_report_mode_field(self):
        """H24-c：SSH 模式 mode 欄位為 'ssh'。"""
        report = run_ssh_mode('192.168.1.1')
        self.assertEqual(report.mode, 'ssh')

    def test_ssh_mode_detail_contains_target(self):
        """H24-d：SSH mode detail 含 target。"""
        report = run_ssh_mode('my-host')
        self.assertIn('my-host', report.detail)

    def test_teleport_mode_report_mode_field(self):
        """H24-e：Teleport 模式 mode 欄位為 'teleport'。"""
        report = run_teleport_mode('cluster-node-1')
        self.assertEqual(report.mode, 'teleport')

    def test_as_text_contains_all_fields(self):
        """H24-f：as_text() 輸出含 mode=, connected=, detail=。"""
        report = RuntimeModeReport(mode='remote', connected=True, detail='test detail')
        text = report.as_text()
        self.assertIn('mode=remote', text)
        self.assertIn('connected=True', text)
        self.assertIn('detail=test detail', text)

    def test_runtime_mode_report_immutable(self):
        """H24-g：RuntimeModeReport 為 frozen dataclass，不可修改欄位。"""
        report = RuntimeModeReport(mode='ssh', connected=True, detail='some detail')
        with self.assertRaises((AttributeError, TypeError)):
            report.mode = 'altered'  # type: ignore[misc]

    def test_empty_target_produces_report(self):
        """H24-h：空 target 字串不拋出例外（Edge case）。"""
        report = run_remote_mode('')
        self.assertIsInstance(report, RuntimeModeReport)


# ---------------------------------------------------------------------------
# query_engine — Bug 4：max_budget_reached 後不再累積訊息（已修復）
# ---------------------------------------------------------------------------

class TestQueryEngineBudgetExhaustion(unittest.TestCase):
    """
    Bug 4 — submit_message 在 max_budget_reached 後仍累積訊息（已修復）。
    修復後：budget 超出時訊息不再加入 mutable_messages / transcript_store。
    """

    def test_budget_reached_does_not_grow_messages(self):
        """H25-a：budget 耗盡後，mutable_messages 長度不再增加。"""
        # max_budget_tokens=1 確保第一則真正的訊息就會耗盡預算
        engine = _make_engine(max_budget_tokens=1)
        result = engine.submit_message('hello')
        count_after = len(engine.mutable_messages)
        # 繼續送訊息
        engine.submit_message('more messages')
        engine.submit_message('even more')
        self.assertEqual(len(engine.mutable_messages), count_after,
                         "After budget exhaustion, mutable_messages must not grow")

    def test_budget_reached_stop_reason(self):
        """H25-b：budget 超出時 stop_reason 為 'max_budget_reached'。"""
        engine = _make_engine(max_budget_tokens=1)
        result = engine.submit_message('overflow')
        self.assertEqual(result.stop_reason, 'max_budget_reached')

    def test_budget_not_reached_appends_normally(self):
        """H25-c：budget 未耗盡時，每次 submit_message 都會增加 mutable_messages。"""
        engine = _make_engine(max_budget_tokens=100_000)
        engine.submit_message('first')
        engine.submit_message('second')
        self.assertEqual(len(engine.mutable_messages), 2)

    def test_transcript_not_grown_after_budget_reached(self):
        """H25-d：budget 耗盡後，transcript_store.entries 也不再增加。"""
        engine = _make_engine(max_budget_tokens=1)
        engine.submit_message('initial')
        transcript_len = len(engine.transcript_store.entries)
        engine.submit_message('should_not_append')
        self.assertEqual(len(engine.transcript_store.entries), transcript_len)

    def test_budget_exhaustion_still_returns_turn_result(self):
        """H25-e：即使 budget 耗盡，仍回傳有效的 TurnResult。"""
        engine = _make_engine(max_budget_tokens=1)
        result = engine.submit_message('overflow again')
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.output)


# ---------------------------------------------------------------------------
# query_engine — 自動 compaction 觸發
# ---------------------------------------------------------------------------

class TestQueryEngineCompaction(unittest.TestCase):
    """compact_messages_if_needed 在超過閾值時正確觸發。"""

    def test_compaction_triggers_when_exceeding_threshold(self):
        """H26-a：訊息數超過 compact_after_turns 時，mutable_messages 被截斷。"""
        engine = _make_engine(max_turns=20, max_budget_tokens=1_000_000, compact_after_turns=3)
        for i in range(5):
            engine.submit_message(f'msg{i}')
        # 5 > 3，觸發 compaction，只保留最後 3 筆
        self.assertLessEqual(len(engine.mutable_messages), 3)

    def test_compaction_does_not_trigger_below_threshold(self):
        """H26-b：訊息數未超過閾值時，不觸發 compaction。"""
        engine = _make_engine(max_turns=20, max_budget_tokens=1_000_000, compact_after_turns=10)
        for i in range(3):
            engine.submit_message(f'msg{i}')
        self.assertEqual(len(engine.mutable_messages), 3)

    def test_transcript_compacted_in_sync(self):
        """H26-c：transcript_store 與 mutable_messages 一起被壓縮。"""
        engine = _make_engine(max_turns=20, max_budget_tokens=1_000_000, compact_after_turns=3)
        for i in range(6):
            engine.submit_message(f'msg{i}')
        self.assertLessEqual(len(engine.transcript_store.entries), 3)

    def test_replay_after_compaction_returns_remaining(self):
        """H26-d：compaction 後 replay_user_messages 只回傳保留的訊息。"""
        engine = _make_engine(max_turns=20, max_budget_tokens=1_000_000, compact_after_turns=2)
        for i in range(5):
            engine.submit_message(f'turn{i}')
        replayed = engine.replay_user_messages()
        self.assertLessEqual(len(replayed), 2)


# ---------------------------------------------------------------------------
# query_engine — persist + restore 回路
# ---------------------------------------------------------------------------

class TestQueryEngineSessionPersistence(unittest.TestCase):
    """persist_session 後 from_saved_session 可正確還原對話狀態。"""

    def test_persist_and_restore_messages(self):
        """H27-a：persist 後 restore，mutable_messages 內容一致。"""
        engine = _make_engine()
        engine.submit_message('hello')
        engine.submit_message('world')
        path_str = engine.persist_session()
        # 解析 session_id（路徑格式為 .port_sessions/{id}.json）
        saved_path = Path(path_str)
        session_id = saved_path.stem
        restored = QueryEnginePort.from_saved_session(session_id)
        self.assertEqual(restored.mutable_messages, engine.mutable_messages)

    def test_persist_and_restore_session_id(self):
        """H27-b：restore 後 session_id 與原始一致。"""
        engine = _make_engine()
        engine.submit_message('test')
        engine.persist_session()
        restored = QueryEnginePort.from_saved_session(engine.session_id)
        self.assertEqual(restored.session_id, engine.session_id)

    def test_persist_and_restore_token_usage(self):
        """H27-c：restore 後 input_tokens / output_tokens 數值一致。"""
        engine = _make_engine()
        engine.submit_message('alpha beta gamma')
        engine.persist_session()
        restored = QueryEnginePort.from_saved_session(engine.session_id)
        self.assertEqual(restored.total_usage.input_tokens, engine.total_usage.input_tokens)
        self.assertEqual(restored.total_usage.output_tokens, engine.total_usage.output_tokens)

    def test_persist_empty_session(self):
        """H27-d：空 session（無訊息）也可成功 persist 與 restore。"""
        engine = _make_engine()
        engine.persist_session()
        restored = QueryEnginePort.from_saved_session(engine.session_id)
        self.assertEqual(restored.mutable_messages, [])

    def tearDown(self):
        # 清理 .port_sessions 目錄中的測試殘留
        import shutil
        port_dir = Path('.port_sessions')
        if port_dir.exists():
            shutil.rmtree(port_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# query_engine — render_summary 完整性
# ---------------------------------------------------------------------------

class TestQueryEngineRenderSummary(unittest.TestCase):
    """render_summary() 輸出包含必要的段落標題與數值。"""

    def test_render_summary_contains_session_id(self):
        """H28-a：render_summary 含 session_id。"""
        engine = _make_engine()
        summary = engine.render_summary()
        self.assertIn(engine.session_id, summary)

    def test_render_summary_contains_max_turns(self):
        """H28-b：render_summary 顯示 max_turns 設定值。"""
        engine = _make_engine(max_turns=5)
        summary = engine.render_summary()
        self.assertIn('5', summary)

    def test_render_summary_mentions_workspace(self):
        """H28-c：render_summary 含 workspace 字樣（來自 manifest）。"""
        engine = _make_engine()
        summary = engine.render_summary()
        self.assertIn('Python Porting Workspace', summary)

    def test_render_summary_turn_count_reflects_submissions(self):
        """H28-d：submit_message 後 render_summary 顯示正確的 turn 數量。"""
        engine = _make_engine()
        engine.submit_message('one')
        engine.submit_message('two')
        summary = engine.render_summary()
        self.assertIn('2', summary)


# ---------------------------------------------------------------------------
# 回歸：Bug 4 與 Bug 5
# ---------------------------------------------------------------------------

class TestRegressionBug4And5(unittest.TestCase):
    """回歸測試，確保 Bug 4 和 Bug 5 的修復不被還原。"""

    def test_bug4_budget_exhaustion_does_not_append(self):
        """回歸：Bug 4 — max_budget_reached 後 mutable_messages 不得成長。"""
        engine = _make_engine(max_budget_tokens=1)
        engine.submit_message('trigger budget')
        baseline = len(engine.mutable_messages)
        for _ in range(3):
            engine.submit_message('should not append')
        self.assertEqual(len(engine.mutable_messages), baseline)

    def test_bug5_missing_session_raises_file_not_found(self):
        """回歸：Bug 5 — 缺少 session 檔案應拋出 FileNotFoundError，而非通用例外。"""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                load_session('phantom_session', Path(tmp))

    def test_bug5_corrupted_json_raises_value_error(self):
        """回歸：Bug 5 — 損壞 JSON 應拋出 ValueError（而非 json.JSONDecodeError 直接外漏）。"""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / 'corrupt.json').write_text('{{{{')
            with self.assertRaises(ValueError):
                load_session('corrupt', d)

    def test_bug5_missing_fields_raises_value_error_with_field_names(self):
        """回歸：Bug 5 — 欄位缺失應拋出 ValueError 且錯誤訊息列出缺少的欄位名稱。"""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / 'incomplete.json').write_text(json.dumps({'session_id': 'x', 'messages': []}))
            with self.assertRaises(ValueError) as ctx:
                load_session('incomplete', d)
            err = str(ctx.exception)
            # 應包含至少一個缺少的欄位名稱
            self.assertTrue('input_tokens' in err or 'output_tokens' in err)


if __name__ == '__main__':
    unittest.main(verbosity=2)
