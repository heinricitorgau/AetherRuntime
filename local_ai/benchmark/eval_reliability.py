#!/usr/bin/env python3
"""Evaluation reliability analyzer (roadmap #6).

Trustworthy regression/governance evidence requires trustworthy evaluation. This
read-only tool audits run history for reproducibility, without running models:

  1. Reproducibility stamps — every run should record a deterministic config
     (temperature == 0), a valid model override, and a prompt profile/version.
  2. Determinism / flakiness — runs sharing the same reproducibility key
     (model, prompt_profile, max_tokens, temperature) should produce identical
     per-task scores; score spread within a group flags a flaky task.

Outputs:
  reports/reliability/eval_reliability.json
  reports/reliability/eval_reliability.md

Usage:
  python local_ai/benchmark/eval_reliability.py
  python local_ai/benchmark/eval_reliability.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_HERE))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from _bench_common import REPORTS_DIR, load_jsonl, now_iso, write_json  # noqa: E402

_RUNS_DIR = REPORTS_DIR / "runs"
_OUT_DIR = REPORTS_DIR / "reliability"
_OUT_JSON = _OUT_DIR / "eval_reliability.json"
_OUT_MD = _OUT_DIR / "eval_reliability.md"

# Policy (data, not code).
DEFAULT_RELIABILITY_POLICY: dict[str, Any] = {
    "score_range_tolerance": 0.0,        # identical-config runs may differ by at most this per task
    "min_runs_for_determinism": 2,       # need >= this many runs in a group to judge determinism
    "deterministic_temperature": 0.0,    # the only temperature considered deterministic
    "min_stamp_completeness": 1.0,       # fraction of required stamps present to call a run "stamped"
}

_REQUIRED_STAMPS = ("prompt_profile", "temperature", "model_override_valid")


def _load_runs() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    if not _RUNS_DIR.exists():
        return runs
    for d in sorted(_RUNS_DIR.iterdir()):
        report = d / "report.json"
        if not d.is_dir() or not report.exists():
            continue
        try:
            rep = json.loads(report.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        meta = rep.get("meta") or {}
        results = []
        rp = d / "results.jsonl"
        if rp.exists():
            results = [{"id": r.get("id"), "score": r.get("score", 0)} for r in load_jsonl(rp)]
        runs.append(
            {
                "run_id": d.name,
                "model": meta.get("model") or rep.get("model") or "unknown",
                "prompt_profile": meta.get("prompt_profile"),
                "max_tokens": meta.get("max_tokens"),
                "temperature": meta.get("temperature"),
                "model_override_valid": meta.get("model_override_valid"),
                "results": results,
                "meta": meta,
            }
        )
    return runs


def _stamp_completeness(run: dict[str, Any]) -> float:
    present = sum(1 for k in _REQUIRED_STAMPS if run["meta"].get(k) is not None)
    return present / len(_REQUIRED_STAMPS)


def _repro_key(run: dict[str, Any]) -> tuple:
    return (run["model"], run["prompt_profile"], run["max_tokens"], run["temperature"])


def analyze(policy: dict[str, Any] | None = None) -> dict[str, Any]:
    pol = {**DEFAULT_RELIABILITY_POLICY, **(policy or {})}
    runs = _load_runs()

    # ── Stamp audit ───────────────────────────────────────────────────────────
    unstamped = []
    nondeterministic = []
    invalid_override = []
    for r in runs:
        if _stamp_completeness(r) < float(pol["min_stamp_completeness"]):
            unstamped.append(r["run_id"])
        temp = r.get("temperature")
        if temp is not None and float(temp) != float(pol["deterministic_temperature"]):
            nondeterministic.append(r["run_id"])
        if r.get("model_override_valid") is False:
            invalid_override.append(r["run_id"])

    # ── Determinism / flakiness within identical-config groups ────────────────
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for r in runs:
        if r["results"]:
            groups[_repro_key(r)].append(r)

    flaky_tasks: list[dict[str, Any]] = []
    groups_checked = 0
    for key, members in groups.items():
        if len(members) < int(pol["min_runs_for_determinism"]):
            continue
        groups_checked += 1
        per_task: dict[str, list[float]] = defaultdict(list)
        for m in members:
            for row in m["results"]:
                if row["id"] is not None:
                    per_task[row["id"]].append(float(row["score"] or 0))
        for task_id, scores in per_task.items():
            if len(scores) < 2:
                continue
            spread = max(scores) - min(scores)
            if spread > float(pol["score_range_tolerance"]):
                flaky_tasks.append(
                    {
                        "task_id": task_id,
                        "model": key[0],
                        "prompt_profile": key[1],
                        "score_range": round(spread, 1),
                        "scores": scores,
                        "runs": len(members),
                    }
                )

    stamped_count = sum(1 for r in runs if _stamp_completeness(r) >= float(pol["min_stamp_completeness"]))
    stamp_rate = round(stamped_count / len(runs), 3) if runs else 0.0

    # ── Verdict (policy-derived) ──────────────────────────────────────────────
    if flaky_tasks:
        verdict = "flaky"
    elif unstamped or nondeterministic or invalid_override:
        verdict = "unstamped"
    else:
        verdict = "reliable"

    return {
        "timestamp": now_iso(),
        "policy": pol,
        "verdict": verdict,
        "total_runs": len(runs),
        "stamp_rate": stamp_rate,
        "groups_checked_for_determinism": groups_checked,
        "flaky_task_count": len(flaky_tasks),
        "flaky_tasks": flaky_tasks,
        "unstamped_runs": unstamped,
        "nondeterministic_runs": nondeterministic,
        "invalid_override_runs": invalid_override,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append
    a("# Evaluation Reliability Report")
    a("")
    a(f"Generated: `{report['timestamp']}`  ")
    a(f"Verdict: **{report['verdict']}**  ")
    a(f"Total runs: {report['total_runs']}  ")
    a(f"Stamp rate: {report['stamp_rate']}  ")
    a(f"Determinism groups checked: {report['groups_checked_for_determinism']}")
    a("")
    a("## Flaky Tasks (score spread within identical config)")
    a("")
    if report["flaky_tasks"]:
        a("| Task | Model | Profile | Range | Runs |")
        a("|------|-------|---------|------:|-----:|")
        for t in report["flaky_tasks"]:
            a(f"| `{t['task_id']}` | {t['model']} | {t['prompt_profile']} | {t['score_range']} | {t['runs']} |")
    else:
        a("None — identical-config runs produced identical per-task scores.")
    a("")
    a("## Reproducibility Stamp Audit")
    a("")
    a(f"- Unstamped runs: {len(report['unstamped_runs'])}")
    a(f"- Non-deterministic runs (temperature != 0): {len(report['nondeterministic_runs'])}")
    a(f"- Invalid model override: {len(report['invalid_override_runs'])}")
    a("")
    a("## Guardrails")
    a("")
    a("- Read-only over existing run reports; runs no models, changes no scoring.")
    a("- Verdict derived from the reliability policy; nothing hard-coded.")
    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any]) -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(report, _OUT_JSON)
    _OUT_MD.write_text(_markdown(report), encoding="utf-8")


def _self_test() -> bool:
    """Validate the determinism + verdict logic on synthetic groups (model-free)."""
    ok = True
    pol = dict(DEFAULT_RELIABILITY_POLICY)

    # Unit check of the spread/flaky logic on synthetic identical-config scores.
    synthetic = [
        {"id": "t1", "scores": [80.0, 80.0], "expect_flaky": False},
        {"id": "t2", "scores": [80.0, 60.0], "expect_flaky": True},
    ]
    for case in synthetic:
        spread = max(case["scores"]) - min(case["scores"])
        is_flaky = spread > float(pol["score_range_tolerance"])
        status = "ok" if is_flaky == case["expect_flaky"] else "FAIL"
        if is_flaky != case["expect_flaky"]:
            ok = False
        print(f"[eval-reliability] self-test {status}: {case['id']} spread={spread} flaky={is_flaky}")

    # Shape check: analyze() returns required keys.
    report = analyze()
    required = {"verdict", "flaky_tasks", "stamp_rate", "unstamped_runs"}
    if required - set(report):
        ok = False
        print(f"[eval-reliability] self-test FAIL: missing {required - set(report)}")
    else:
        print(f"[eval-reliability] self-test ok: analyze() verdict={report['verdict']}")
    return ok


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluation reliability analyzer")
    parser.add_argument("--self-test", action="store_true", help="Model-free reliability-logic self-test")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.self_test:
        ok = _self_test()
        print(f"[eval-reliability] self-test {'PASS' if ok else 'FAIL'}")
        sys.exit(0 if ok else 1)

    report = analyze()
    write_reports(report)
    print(f"[eval-reliability] verdict={report['verdict']} runs={report['total_runs']} "
          f"stamp_rate={report['stamp_rate']} flaky={report['flaky_task_count']}")
    print(f"[eval-reliability] report >> {_OUT_MD}")


if __name__ == "__main__":
    main()
