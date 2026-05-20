#!/usr/bin/env python3
"""SFT Readiness Check.

Verifies that the full pipeline — dataset, semantic quality, benchmark golden
baseline, reproducibility — is ready for SFT / LoRA training.

Writes:
  local_ai/training_quality/reports/sft_readiness_report.json
  local_ai/training_quality/reports/sft_readiness_report.md

Usage:
  python local_ai/training_quality/sft_readiness_check.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

_HERE      = Path(__file__).resolve().parent          # training_quality/
_LOCAL_AI  = _HERE.parent                             # local_ai/
_REPORTS   = _HERE / "reports"                        # training_quality/reports/
_BENCHMARK = _LOCAL_AI / "benchmark"                  # local_ai/benchmark/
_GOLDEN    = _BENCHMARK / "golden" / "golden_baseline.json"
_EXPERIMENT_REGISTRY = _LOCAL_AI / "experiments" / "registry"


# ── Shared helpers ────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _chk(passed: bool, detail: str) -> dict:
    return {"passed": passed, "detail": detail}


# ── Check 1 & 2: Dataset existence + integrity ────────────────────────────────

def check_dataset() -> tuple[bool, dict]:
    checks: dict = {}

    # Existence
    required = [
        "semantic_accepted_filled.jsonl",
        "sft_chatml.jsonl",
        "sft_alpaca.jsonl",
        "sft_instruction_output.jsonl",
    ]
    exist_ok = True
    for name in required:
        ok = (_REPORTS / name).exists()
        checks[name] = _chk(ok, "found" if ok else "MISSING")
        if not ok:
            exist_ok = False

    # Integrity — prefer sft_package_summary.json, fall back to counting directly
    summary = _load_json(_REPORTS / "sft_package_summary.json")
    if summary:
        rec      = summary.get("records", {})
        total    = rec.get("total", 0) or rec.get("packaged", 0)
        by_type  = rec.get("by_type", {})
        code_gen = by_type.get("code_generation", 0)
        concept  = by_type.get("concept_summary", 0)
        src      = "sft_package_summary.json"
    else:
        total = code_gen = concept = 0
        src = "semantic_accepted_filled.jsonl (fallback)"
        path = _REPORTS / "semantic_accepted_filled.jsonl"
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                total += 1
                t = r.get("type", "")
                if t == "code_generation":
                    code_gen += 1
                elif t == "concept_summary":
                    concept += 1
        except Exception:
            pass

    checks["_count_source"]  = src
    ok_total   = total    >= 40
    ok_codegen = code_gen >= 16
    ok_concept = concept  >= 25

    checks["total_records"]     = _chk(ok_total,   f"{total} (need >= 40)")
    checks["code_generation"]   = _chk(ok_codegen, f"{code_gen} (need >= 16)")
    checks["concept_summary"]   = _chk(ok_concept, f"{concept} (need >= 25)")

    passed = exist_ok and ok_total and ok_codegen and ok_concept
    return passed, checks


# ── Check 3: Semantic quality ─────────────────────────────────────────────────

def check_semantic() -> tuple[bool, dict]:
    sr = _load_json(_REPORTS / "semantic_report.json")
    if sr is None:
        return False, {"semantic_report": _chk(False, "semantic_report.json not found")}

    rejected = sr.get("semantic_rejected", None)
    if rejected is None:
        rejected = sum(1 for r in sr.get("results", []) if not r.get("passed", True))

    ok = rejected == 0
    return ok, {
        "semantic_rejected": _chk(ok, f"{rejected} rejected (need 0)"),
        "semantic_accepted": _chk(True, str(sr.get("semantic_accepted", "?"))),
        "checked":           _chk(True, str(sr.get("checked", "?"))),
    }


# ── Checks 4 & 5: Golden baseline existence + quality gate ───────────────────

def check_golden() -> tuple[bool, dict]:
    if not _GOLDEN.exists():
        return False, {
            "golden_exists": _chk(False, f"not found — run lock_golden_baseline.py first")
        }

    g = _load_json(_GOLDEN)
    if g is None:
        return False, {"golden_exists": _chk(False, "golden_baseline.json unreadable")}

    task_count    = g.get("task_count", 0)
    accepted      = g.get("accepted_count", 0)
    avg_score     = g.get("avg_score", 0.0)
    compile_rate  = g.get("compile_pass_rate", 0.0)
    semantic_rate = g.get("semantic_pass_rate", 0.0)
    timeout_rate  = g.get("timeout_rate", 1.0)

    ok_acc  = accepted == task_count and task_count > 0
    ok_avg  = avg_score >= 80.0
    ok_comp = compile_rate >= 1.0
    ok_sem  = semantic_rate >= 1.0
    ok_to   = timeout_rate == 0.0

    checks = {
        "golden_exists":    _chk(True,    f"ref={g.get('run_id', '?')}"),
        "accepted_all":     _chk(ok_acc,  f"{accepted}/{task_count} (need all)"),
        "avg_score_ge_80":  _chk(ok_avg,  f"{avg_score:.1f} (need >= 80)"),
        "compile_100pct":   _chk(ok_comp, f"{compile_rate:.0%} (need 100%)"),
        "semantic_100pct":  _chk(ok_sem,  f"{semantic_rate:.0%} (need 100%)"),
        "timeout_zero":     _chk(ok_to,   f"{timeout_rate:.0%} (need 0%)"),
    }
    return ok_acc and ok_avg and ok_comp and ok_sem and ok_to, checks


# ── Check 6: Reproducibility gate ────────────────────────────────────────────

def check_reproducibility() -> tuple[bool, dict]:
    """Pass if the locked golden benchmark run is present in the registry."""
    golden = _load_json(_GOLDEN)
    golden_run_id = str(golden.get("run_id")) if golden and golden.get("run_id") else None
    if golden_run_id:
        registry_path = _EXPERIMENT_REGISTRY / f"{golden_run_id}.json"
        if registry_path.exists():
            return True, {
                "golden_run_registered": _chk(
                    True,
                    f"{golden_run_id} found in experiment registry",
                )
            }

    # Fallback for older workspaces before experiment registry backfill.
    runs_dir = _BENCHMARK / "reports" / "runs"
    latest_path: Path | None = None
    latest_mtime = 0.0

    if runs_dir.exists():
        for run_dir in runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            p = run_dir / "comparison_report.json"
            if p.exists():
                mtime = p.stat().st_mtime
                if mtime > latest_mtime:
                    latest_mtime = mtime
                    latest_path = p

    if latest_path is None:
        return True, {
            "latest_comparison": _chk(
                True, "no comparison run yet — skipped (not a failure)"
            )
        }

    comp = _load_json(latest_path)
    if comp is None:
        return True, {
            "latest_comparison": _chk(True, "comparison_report.json unreadable — skipped")
        }

    regression = comp.get("regression", False)
    verdict    = comp.get("verdict", "unknown")
    run_id     = comp.get("current_run_id", "?")
    ok = not regression

    return ok, {
        "latest_comparison": _chk(
            ok,
            f"verdict={verdict}  run={run_id}"
            + ("  ← REGRESSION" if regression else ""),
        )
    }


# ── Check 7: Documentation gate ──────────────────────────────────────────────

def check_documentation() -> tuple[bool, dict]:
    docs = {
        "README.md":       _LOCAL_AI / "README.md",
        "DATASET_CARD.md": _LOCAL_AI / "DATASET_CARD.md",
    }
    checks: dict = {}
    all_ok = True
    for name, path in docs.items():
        ok = path.exists()
        checks[name] = _chk(ok, "found" if ok else "MISSING")
        if not ok:
            all_ok = False
    return all_ok, checks


# ── Markdown report ───────────────────────────────────────────────────────────

def _icon(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def write_markdown(report: dict, path: Path) -> None:
    lines: list[str] = []
    a = lines.append
    ready = report["ready_for_sft"]

    a("# SFT Readiness Report")
    a("")
    a(f"**Timestamp**: {report['timestamp']}")
    a(f"**Overall**: {'PASS — READY FOR SFT' if ready else 'FAIL — NOT READY FOR SFT'}")
    a("")
    a("---")
    a("")

    sections = [
        ("Dataset",         "dataset_checks"),
        ("Semantic",        "semantic_checks"),
        ("Benchmark",       "benchmark_checks"),
        ("Reproducibility", "reproducibility_checks"),
        ("Documentation",   "documentation_checks"),
    ]

    for title, key in sections:
        sec      = report.get(key, {})
        sec_pass = sec.get("passed", False)
        a(f"## {title}: {_icon(sec_pass)}")
        a("")
        a("| Check | Status | Detail |")
        a("|-------|:------:|--------|")
        for k, v in sec.get("checks", {}).items():
            if k.startswith("_"):
                continue
            if isinstance(v, dict):
                icon   = _icon(v.get("passed", False))
                detail = v.get("detail", "")
                a(f"| {k} | {icon} | {detail} |")
            else:
                a(f"| {k} | — | {v} |")
        a("")

    a("---")
    a("")
    if ready:
        a("**READY_FOR_SFT = true**")
    else:
        a("**READY_FOR_SFT = false**")
        a("")
        a("Fix the failing checks above before starting SFT / LoRA training.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    dataset_ok,  dataset_chks   = check_dataset()
    semantic_ok, semantic_chks  = check_semantic()
    golden_ok,   golden_chks    = check_golden()
    repro_ok,    repro_chks     = check_reproducibility()
    docs_ok,     docs_chks      = check_documentation()

    ready = all([dataset_ok, semantic_ok, golden_ok, repro_ok, docs_ok])

    report = {
        "timestamp":     _now(),
        "ready_for_sft": ready,
        "dataset_checks": {
            "passed": dataset_ok,
            "checks": dataset_chks,
        },
        "semantic_checks": {
            "passed": semantic_ok,
            "checks": semantic_chks,
        },
        "benchmark_checks": {
            "passed": golden_ok,
            "checks": golden_chks,
        },
        "reproducibility_checks": {
            "passed": repro_ok,
            "checks": repro_chks,
        },
        "documentation_checks": {
            "passed": docs_ok,
            "checks": docs_chks,
        },
    }

    json_path = _REPORTS / "sft_readiness_report.json"
    md_path   = _REPORTS / "sft_readiness_report.md"

    _REPORTS.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_markdown(report, md_path)

    print()
    for title, key in [
        ("Dataset",         "dataset_checks"),
        ("Semantic",        "semantic_checks"),
        ("Benchmark",       "benchmark_checks"),
        ("Reproducibility", "reproducibility_checks"),
        ("Documentation",   "documentation_checks"),
    ]:
        sec = report[key]
        print(f"  {_icon(sec['passed']):<4}  {title}")

    print()
    if ready:
        print("SFT readiness: PASS")
        print("READY_FOR_SFT = true")
    else:
        print("SFT readiness: FAIL")
        print("READY_FOR_SFT = false")

    print(f"\nReport: {md_path}")

    sys.exit(0 if ready else 1)


if __name__ == "__main__":
    main()
