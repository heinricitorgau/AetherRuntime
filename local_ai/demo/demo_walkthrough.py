#!/usr/bin/env python3
"""Print a step-by-step portfolio demo walkthrough.

This script does not run models. It only prints the recommended demo workflow.
"""
from __future__ import annotations


def build_walkthrough() -> str:
    return """# V8 Demo Walkthrough

This walkthrough is a no-model portfolio demo path.

1. Run smoke test
   Command: python local_ai/cli.py smoke
   Report:  local_ai/system/reports/smoke_test_report.md

2. Inspect adapters
   Command: python local_ai/cli.py adapters
   Report:  local_ai/sft/reports/adapter_registry_summary.md

3. Inspect routing
   Command: python local_ai/cli.py routing --benchmark c_exam_2025_strict_seeded
   Report:  local_ai/routing/reports/c_exam_2025_strict_seeded_routing_plan.md

4. Inspect snapshots
   Open: local_ai/release/snapshots/local_ai_cli_v7/snapshot.md

5. Inspect architecture map
   Open: local_ai/system/reports/architecture_map.md

6. Inspect benchmark reports
   Open: local_ai/system/reports/report_index.md
   Look for benchmark, sft, routing, release, and dataset_scaling reports.

7. Explain current stable status
   - Base model is default.
   - No default adapter is selected.
   - retry_geometry_v3_guarded is safe_no_change and geometry-only routable.
   - Synthetic LoRA training is frozen after regression findings.
   - Generated datasets are retained as isolated stress-test assets.
"""


def main() -> None:
    print(build_walkthrough())


if __name__ == "__main__":
    main()
