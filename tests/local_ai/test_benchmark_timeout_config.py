from __future__ import annotations

import unittest
from unittest.mock import patch

from local_ai import proxy
from local_ai.benchmark import run_baseline


class BenchmarkTimeoutConfigTests(unittest.TestCase):
    def test_qwen_3b_uses_benchmark_safe_proxy_defaults(self):
        self.assertEqual(proxy._default_timeouts_for_model("qwen2.5-coder:3b"), (300, 90))

    def test_warns_but_allows_benchmark_safe_floor(self):
        with patch.object(
            run_baseline,
            "_read_proxy_config",
            return_value={"full_timeout": 180, "first_token_timeout": 45},
        ):
            with patch("builtins.print") as mock_print:
                config = run_baseline._check_proxy_timeout_config("http://proxy")

        self.assertEqual(config["full_timeout"], 180)
        printed = "\n".join(" ".join(map(str, call.args)) for call in mock_print.call_args_list)
        self.assertIn("WARNING: proxy timeout too short.", printed)

    def test_fails_fast_when_full_timeout_is_below_180(self):
        with patch.object(
            run_baseline,
            "_read_proxy_config",
            return_value={"full_timeout": 60, "first_token_timeout": 15},
        ):
            with self.assertRaisesRegex(RuntimeError, "below fail-fast threshold 180s"):
                run_baseline._check_proxy_timeout_config("http://proxy")

    def test_fails_fast_when_proxy_config_is_unavailable(self):
        with patch.object(run_baseline, "_read_proxy_config", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "could not read proxy /config"):
                run_baseline._check_proxy_timeout_config("http://proxy")

    def test_default_client_timeout_exceeds_proxy_full_timeout(self):
        self.assertGreater(
            run_baseline._DEFAULT_TIMEOUT,
            run_baseline._BENCHMARK_REQUIRED_FULL_TIMEOUT
            * run_baseline._BENCHMARK_REPAIR_ATTEMPTS,
        )

    def test_evaluate_case_can_request_skip_repair(self):
        task = {
            "id": "case",
            "instruction": "write c",
            "sample_input": "",
            "expected_tokens": [],
            "expected_keywords": [],
            "topic": "topic",
            "difficulty": "easy",
            "points": 1,
            "year": 2026,
            "exam": "x",
        }
        with patch.object(run_baseline, "call_proxy", return_value=("", None, 1)) as mock_call:
            run_baseline.evaluate_case(
                task=task,
                proxy_url="http://proxy",
                model="m",
                system_prompt="s",
                max_tokens=1,
                timeout=1,
                run_timeout=1,
                compiler=None,
                work_dir=run_baseline.Path("."),
                skip_repair=True,
            )
        self.assertTrue(mock_call.call_args.kwargs["skip_repair"])
