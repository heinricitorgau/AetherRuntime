#!/usr/bin/env python3
"""Human-verified goldens governance pipeline (roadmap #1 — infrastructure).

This is the scaffolding for expanding human-verified golden cases. It validates
candidate goldens and promotes the passing ones into an approved registry. The
golden *content* must be provided by a human (or, at a lower provenance tier, an
agent that compile/runtime-verified the answer) — this tool never fabricates a
golden and never claims a model output is a golden.

Candidate goldens live in `goldens/candidates/*.json`, each with:
  id, prompt, verified_solution, expected_output_contains, verified_by, source

Validation (policy-as-data):
  - required fields present
  - `verified_by` provenance present (human review is the highest tier)
  - optional: compile the verified_solution with gcc and check the sample output
    contains the expected tokens (best-effort; skipped if no compiler)

Outputs:
  goldens/approved_goldens.json                  (registry)
  goldens/reports/goldens_promotion_report.json
  goldens/reports/goldens_promotion_report.md

Usage:
  python local_ai/goldens/promote_goldens.py
  python local_ai/goldens/promote_goldens.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_REPO_ROOT = _LOCAL_AI.parent
sys.path.insert(0, str(_LOCAL_AI / "benchmark"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_CANDIDATES_DIR = _HERE / "candidates"
_APPROVED = _HERE / "approved_goldens.json"
_SIGNOFF = _HERE / "signoff.json"

# A signoff is only honoured when a real reviewer name is present. These
# placeholder values mean "not yet signed" and never elevate the tier.
_UNSIGNED_PLACEHOLDERS = {"", "null", "none", "unsigned", "fill_in", "fill-in", "todo"}
_REPORT_DIR = _HERE / "reports"
_REPORT_JSON = _REPORT_DIR / "goldens_promotion_report.json"
_REPORT_MD = _REPORT_DIR / "goldens_promotion_report.md"

_REQUIRED_FIELDS = ("id", "prompt", "verified_solution", "expected_output_contains", "verified_by")

DEFAULT_GOLDENS_POLICY: dict[str, Any] = {
    "require_verified_by": True,
    "require_compile": True,       # best-effort; skipped if no compiler
    "require_runtime_match": True,  # best-effort; skipped if no compiler
    "human_verified_tokens": ["human", "reviewer", "instructor"],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _compile_and_run(code: str, sample_input: str, expected: list[str]) -> dict[str, Any]:
    """Best-effort compile+run using the benchmark helpers. Skips if no compiler."""
    try:
        from _bench_common import compile_code, find_compiler, run_exe  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "reason": f"helpers unavailable: {exc}"}
    compiler = find_compiler()
    if not compiler:
        return {"checked": False, "reason": "no compiler found"}
    with tempfile.TemporaryDirectory() as tmp:
        comp = compile_code(code, "golden", Path(tmp), compiler)
        if not comp.get("ok"):
            return {"checked": True, "compile_ok": False, "runtime_ok": False,
                    "reason": comp.get("message", "compile failed")}
        exe = comp.get("exe")
        run = run_exe(str(exe), sample_input, timeout=5)
        out = run.get("output", "") or ""
        matched = [t for t in expected if t in out]
        runtime_ok = len(matched) == len(expected)
        return {"checked": True, "compile_ok": True, "runtime_ok": runtime_ok,
                "found": matched, "missing": [t for t in expected if t not in out]}


def _validate(candidate: dict[str, Any], policy: dict[str, Any], do_exec: bool) -> dict[str, Any]:
    reasons: list[str] = []
    missing = [f for f in _REQUIRED_FIELDS if not candidate.get(f)]
    if missing:
        reasons.append(f"missing fields: {', '.join(missing)}")

    verified_by = str(candidate.get("verified_by") or "")
    if policy["require_verified_by"] and not verified_by:
        reasons.append("no verified_by provenance")
    human_verified = any(tok in verified_by.lower() for tok in policy["human_verified_tokens"])

    exec_result: dict[str, Any] = {"checked": False}
    if do_exec and not missing:
        exec_result = _compile_and_run(
            candidate["verified_solution"],
            candidate.get("sample_input", ""),
            candidate.get("expected_output_contains", []),
        )
        if exec_result.get("checked"):
            if policy["require_compile"] and not exec_result.get("compile_ok"):
                reasons.append("verified_solution did not compile")
            if policy["require_runtime_match"] and exec_result.get("compile_ok") and not exec_result.get("runtime_ok"):
                reasons.append(f"runtime output missing {exec_result.get('missing')}")

    status = "approved" if not reasons else "rejected"
    return {
        "id": candidate.get("id"),
        "status": status,
        "provenance_tier": "human_verified" if human_verified else "agent_verified",
        "verified_by": verified_by,
        "exec": exec_result,
        "reasons": reasons,
    }


def _apply_signoff(results: list[dict[str, Any]]) -> None:
    """Elevate approved goldens to the human_verified tier IFF a real human sign-off
    exists in signoff.json. A real sign-off requires a non-placeholder reviewer
    name. This tool never writes that name itself — it must come from a human.
    """
    signoff = _load(_SIGNOFF)
    signer = str(signoff.get("signed_off_by") or "").strip()
    if not signer or signer.lower() in _UNSIGNED_PLACEHOLDERS:
        return  # unsigned template — no elevation
    scope = signoff.get("scope")
    scope_ids = set(signoff.get("scope_ids") or [])
    for r in results:
        if r["status"] != "approved":
            continue
        if scope == "all" or r["id"] in scope_ids:
            r["provenance_tier"] = "human_verified"
            r["human_signoff"] = {
                "by": signer,
                "at": signoff.get("signed_off_at"),
                "nature": signoff.get("nature"),
            }


def evaluate(policy: dict[str, Any] | None = None, do_exec: bool = True) -> dict[str, Any]:
    pol = {**DEFAULT_GOLDENS_POLICY, **(policy or {})}
    candidates = []
    if _CANDIDATES_DIR.exists():
        for p in sorted(_CANDIDATES_DIR.glob("*.json")):
            data = _load(p)
            if data:
                candidates.append(data)
        for p in sorted(_CANDIDATES_DIR.glob("*.jsonl")):  # bulk candidates, one per line
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    candidates.append(json.loads(line))
                except Exception:  # noqa: BLE001
                    pass

    results = [_validate(c, pol, do_exec) for c in candidates]
    _apply_signoff(results)
    approved = [r for r in results if r["status"] == "approved"]
    human_tier = [r for r in approved if r["provenance_tier"] == "human_verified"]

    return {
        "timestamp": _now(),
        "policy": pol,
        "candidates_total": len(candidates),
        "approved_count": len(approved),
        "human_verified_count": len(human_tier),
        "decision": "pass" if candidates and len(approved) == len(candidates) else (
            "empty" if not candidates else "partial"),
        "results": results,
    }


def _write_registry(report: dict[str, Any]) -> None:
    registry = {
        "updated_at": report["timestamp"],
        "approved_count": report["approved_count"],
        "human_verified_count": report["human_verified_count"],
        "goldens": [
            {
                "id": r["id"],
                "provenance_tier": r["provenance_tier"],
                "verified_by": r["verified_by"],
                **({"human_signoff": r["human_signoff"]} if r.get("human_signoff") else {}),
            }
            for r in report["results"] if r["status"] == "approved"
        ],
    }
    _APPROVED.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append
    a("# Goldens Promotion Report")
    a("")
    a(f"Generated: `{report['timestamp']}`  ")
    a(f"Decision: **{report['decision']}**  ")
    a(f"Approved: {report['approved_count']}/{report['candidates_total']} "
      f"(human-verified: {report['human_verified_count']})")
    a("")
    a("| Golden | Status | Provenance | Reasons |")
    a("|--------|--------|------------|---------|")
    for r in report["results"]:
        reasons = "; ".join(r["reasons"]) or "—"
        a(f"| `{r['id']}` | {r['status']} | {r['provenance_tier']} | {reasons} |")
    a("")
    a("## Guardrails")
    a("")
    a("- Golden content must be provided (human or agent compile/runtime verified); never fabricated here.")
    a("- Human review is the highest provenance tier; agent-verified goldens await human sign-off.")
    a("- Compile/runtime checks are best-effort and skipped when no compiler is available.")
    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any]) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _REPORT_MD.write_text(_markdown(report), encoding="utf-8")
    _write_registry(report)


def _self_test() -> bool:
    pol = dict(DEFAULT_GOLDENS_POLICY)
    good = _validate(
        {"id": "x", "prompt": "p", "verified_solution": "int main(){}",
         "expected_output_contains": ["a"], "verified_by": "human_reviewer"},
        pol, do_exec=False,
    )
    bad = _validate({"id": "y", "prompt": "p"}, pol, do_exec=False)
    ok = good["status"] == "approved" and good["provenance_tier"] == "human_verified" and bad["status"] == "rejected"
    print(f"[promote-goldens] self-test good={good['status']}/{good['provenance_tier']} bad={bad['status']}")
    return ok


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and promote human-verified goldens")
    parser.add_argument("--self-test", action="store_true", help="Field-validation self-test (no compile)")
    parser.add_argument("--no-exec", action="store_true", help="Skip compile/runtime verification")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.self_test:
        ok = _self_test()
        print(f"[promote-goldens] self-test {'PASS' if ok else 'FAIL'}")
        sys.exit(0 if ok else 1)

    report = evaluate(do_exec=not args.no_exec)
    write_reports(report)
    print(f"[promote-goldens] decision={report['decision']} "
          f"approved={report['approved_count']}/{report['candidates_total']} "
          f"human_verified={report['human_verified_count']}")
    print(f"[promote-goldens] report >> {_REPORT_MD}")


if __name__ == "__main__":
    main()
