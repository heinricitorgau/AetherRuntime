from __future__ import annotations

import unittest

from local_ai.benchmark import run_baseline


class StrictPromptingTests(unittest.TestCase):
    def test_pattern_triangle_does_not_receive_geometry_seed(self):
        task = {
            "topic": "Pattern Generation",
            "instruction": "Print a triangle pattern.",
        }
        self.assertFalse(run_baseline._geometry_seed_applies(task))

    def test_geometry_task_still_receives_geometry_seed(self):
        task = {
            "topic": "Geometry - Triangle Enumeration",
            "instruction": "Compute triangle area.",
        }
        self.assertTrue(run_baseline._geometry_seed_applies(task))

    def test_geometry_seed_declares_area_inside_main(self):
        self.assertIn("double area = 0.0;", run_baseline._GEOMETRY_SEED)

    def test_series_task_receives_divide_by_zero_hint(self):
        task = {
            "topic": "Series Calculation",
            "instruction": "Compute a series.",
        }
        self.assertTrue(run_baseline._series_seed_applies(task))
        prompt, _ = run_baseline._build_strict_user_prompt(task)
        self.assertIn("Do not divide by zero at i = 1.", prompt)
