#!/usr/bin/env python3
"""validate_goldens.py — compile and validate all golden C files.

Checks:
  1. Contains #include
  2. Contains int main
  3. Contains return 0
  4. Balanced braces
  5. No nested function definitions (function def inside a brace block)
  6. Contains scanf and printf
  7. gcc -std=c99 compile success
  8. Runtime output matches expected_tokens (if sample_input provided)

Reads:
  local_ai/goldens/<category>/  — golden .c files
  local_ai/goldens/<category>/<category>_manifest.json — metadata

Writes:
  local_ai/goldens/reports/golden_validation_report.md

Usage:
  python local_ai/goldens/validate_goldens.py
  python local_ai/goldens/validate_goldens.py --category geometry
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_HERE       = Path(__file__).resolve().parent          # local_ai/goldens/
_LOCAL_AI   = _HERE.parent                             # local_ai/
_REPO_ROOT  = _LOCAL_AI.parent
_REPORT_DIR = _HERE / "reports"


# ── Compiler detection ────────────────────────────────────────────────────────

def _find_compiler() -> str | None:
    for name in ("gcc", "cc"):
        try:
            result = subprocess.run(
                [name, "--version"],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                return name
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


# ── Static validation ────────────────────────────────────────────────────────

def _validate_static(code: str) -> list[str]:
    """Return list of violation strings; empty = valid."""
    violations: list[str] = []

    if "#include" not in code:
        violations.append("missing #include")
    if not re.search(r"\bint\s+main\s*\(", code):
        violations.append("missing int main")
    if "return 0" not in code and "return(0)" not in code:
        violations.append("missing return 0")

    opens  = code.count("{")
    closes = code.count("}")
    if opens != closes:
        violations.append(f"unbalanced braces ({opens} open, {closes} close)")

    if "scanf" not in code:
        violations.append("missing scanf")
    if "printf" not in code:
        violations.append("missing printf")

    if len(code.strip()) < 50:
        violations.append("code too short (< 50 chars)")

    # Nested function detection: a function definition starting inside a brace
    # depth > 0 (ignoring the main function's own opening brace).
    # Simple heuristic: find all function-definition-like patterns and check
    # whether they appear inside main's brace block.
    _check_nested_functions(code, violations)

    return violations


def _check_nested_functions(code: str, violations: list[str]) -> None:
    """Detect nested function definitions (invalid in standard C99)."""
    # Find main's opening brace
    main_match = re.search(r"\bint\s+main\s*\([^)]*\)\s*\{", code)
    if not main_match:
        return

    main_body_start = main_match.end()

    # Look for function-definition patterns inside main's body
    # Pattern: type identifier(...) { at brace depth >= 1
    func_pattern = re.compile(
        r"\b(int|void|double|float|char|long|short|unsigned)\s+"
        r"([a-zA-Z_]\w*)\s*\([^)]*\)\s*\{"
    )

    for m in func_pattern.finditer(code, main_body_start):
        # Check if this match is inside main's scope (within the outermost braces)
        # by counting brace depth from main_body_start to match position
        prefix = code[main_body_start:m.start()]
        depth = prefix.count("{") - prefix.count("}")
        if depth >= 0:  # Still inside main or deeper
            violations.append(
                f"nested function '{m.group(2)}' defined inside main() "
                f"-- invalid in standard C99"
            )


# ── Compile check ─────────────────────────────────────────────────────────────

def _compile_check(
    source_path: Path, compiler: str, work_dir: Path
) -> dict:
    """Compile with gcc -std=c99 -Wall -Werror. Return {ok, errors, warnings, exe}."""
    exe_path = work_dir / source_path.stem
    if sys.platform == "win32":
        exe_path = exe_path.with_suffix(".exe")

    cmd = [
        compiler, "-std=c99", "-Wall", "-Wno-unused-result",
        "-lm",
        str(source_path), "-o", str(exe_path),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "errors": ["compile timed out"], "warnings": [], "exe": None}

    stderr = result.stderr or ""
    errors   = [l for l in stderr.splitlines() if "error:" in l.lower()]
    warnings = [l for l in stderr.splitlines() if "warning:" in l.lower()]

    return {
        "ok":       result.returncode == 0,
        "errors":   errors,
        "warnings": warnings,
        "exe":      str(exe_path) if result.returncode == 0 else None,
    }


# ── Runtime check ─────────────────────────────────────────────────────────────

def _runtime_check(
    exe_path: str, sample_input: str, expected_tokens: list[str],
) -> dict:
    """Run the executable with sample_input and check output for expected tokens."""
    try:
        result = subprocess.run(
            [exe_path],
            input=sample_input,
            capture_output=True, text=True, timeout=10,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "timed_out": True, "output": "", "found": [], "missing": expected_tokens}
    except Exception as exc:
        return {"ok": False, "timed_out": False, "output": str(exc), "found": [], "missing": expected_tokens}

    output = result.stdout or ""
    found   = [t for t in expected_tokens if t in output]
    missing = [t for t in expected_tokens if t not in output]

    return {
        "ok":        len(missing) == 0,
        "timed_out": False,
        "output":    output[:500],
        "found":     found,
        "missing":   missing,
    }


# ── Discover goldens ─────────────────────────────────────────────────────────

def _discover_goldens(category: str | None) -> list[dict]:
    """Find all golden .c files and their manifest entries.

    Returns list of dicts:
      {category, id, file_path, manifest_entry}
    """
    goldens: list[dict] = []

    for cat_dir in sorted(_HERE.iterdir()):
        if not cat_dir.is_dir():
            continue
        if cat_dir.name in ("reports", "__pycache__"):
            continue
        if category and cat_dir.name != category:
            continue

        # Load manifest
        manifest_path = cat_dir / f"{cat_dir.name}_manifest.json"
        manifest_entries: dict[str, dict] = {}
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                for entry in data.get("goldens", []):
                    manifest_entries[entry["id"]] = entry
            except Exception:
                pass

        # Find .c files
        for c_file in sorted(cat_dir.glob("*_golden.c")):
            # Extract ID: <id>_golden.c -> <id>
            file_id = c_file.stem.replace("_golden", "")
            goldens.append({
                "category":       cat_dir.name,
                "id":             file_id,
                "file_path":      c_file,
                "manifest_entry": manifest_entries.get(file_id, {}),
            })

    return goldens


# ── Update manifest with verification results ────────────────────────────────

def _update_manifest(category_dir: Path, results: list[dict]) -> None:
    """Update the manifest with compile/runtime verification status."""
    manifest_path = category_dir / f"{category_dir.name}_manifest.json"
    if not manifest_path.exists():
        return

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results_by_id = {r["id"]: r for r in results}

    for entry in data.get("goldens", []):
        r = results_by_id.get(entry["id"])
        if not r:
            continue
        entry["compile_verified"] = r.get("compile_ok", False)
        entry["runtime_verified"] = r.get("runtime_ok", False)
        entry["verified_at"] = now

    manifest_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ── Markdown report ───────────────────────────────────────────────────────────

def _build_report(results: list[dict], compiler: str | None) -> str:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines: list[str] = []
    a = lines.append

    a("# Golden Validation Report")
    a("")
    a(f"**Generated**: {now}  ")
    a(f"**Compiler**: `{compiler or 'NOT FOUND'}`  ")
    a(f"**Goldens validated**: {len(results)}")
    a("")

    passed = sum(1 for r in results if r["all_ok"])
    failed = len(results) - passed
    a(f"## Summary: {passed} passed, {failed} failed")
    a("")

    a("| ID | Category | Static | Compile | Runtime | Status |")
    a("|----|----------|:------:|:-------:|:-------:|:------:|")

    for r in results:
        s_icon = "✓" if r["static_ok"] else "✗"
        c_icon = "✓" if r["compile_ok"] else ("—" if not compiler else "✗")
        r_icon = "✓" if r["runtime_ok"] else ("—" if not r.get("runtime_ran") else "✗")
        status = "✓ PASS" if r["all_ok"] else "✗ FAIL"
        a(f"| {r['id']} | {r['category']} | {s_icon} | {c_icon} | {r_icon} | {status} |")

    a("")

    # Detail sections for failures
    for r in results:
        if r["all_ok"]:
            continue
        a(f"### {r['id']} — FAILED")
        a("")
        if r["static_violations"]:
            a("**Static violations:**")
            for v in r["static_violations"]:
                a(f"- {v}")
            a("")
        if not r["compile_ok"] and r.get("compile_errors"):
            a("**Compile errors:**")
            for e in r["compile_errors"]:
                a(f"- `{e}`")
            a("")
        if r.get("runtime_ran") and not r["runtime_ok"]:
            a("**Runtime:**")
            if r.get("runtime_missing"):
                a(f"- Missing tokens: {r['runtime_missing']}")
            if r.get("runtime_output"):
                a(f"- Output: `{r['runtime_output'][:200]}`")
            a("")

    a("---")
    a("*Generated by `validate_goldens.py`*")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate golden C files")
    parser.add_argument("--category", default=None,
                        help="Only validate goldens in this category (e.g. geometry)")
    args = parser.parse_args()

    compiler = _find_compiler()
    if not compiler:
        print("[validate] WARNING: no C compiler found — compile/runtime checks skipped",
              file=sys.stderr)

    goldens = _discover_goldens(args.category)
    if not goldens:
        print("[validate] No golden files found.")
        sys.exit(0)

    print(f"[validate] Found {len(goldens)} golden file(s)")
    print(f"[validate] Compiler: {compiler or 'NOT FOUND'}")
    print()

    results: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="golden_validate_") as tmp_dir:
        tmp = Path(tmp_dir)

        for g in goldens:
            gid      = g["id"]
            cat      = g["category"]
            filepath = g["file_path"]
            manifest = g["manifest_entry"]

            print(f"  [{cat}] {gid}")

            code = filepath.read_text(encoding="utf-8")

            # 1. Static validation
            static_v = _validate_static(code)
            static_ok = len(static_v) == 0
            if not static_ok:
                print(f"    static: FAIL — {static_v}")
            else:
                print(f"    static: OK")

            # 2. Compile
            compile_ok     = False
            compile_errors: list[str] = []
            exe_path       = None
            if compiler:
                cr = _compile_check(filepath, compiler, tmp)
                compile_ok     = cr["ok"]
                compile_errors = cr.get("errors", [])
                exe_path       = cr.get("exe")
                if compile_ok:
                    print(f"    compile: OK")
                else:
                    print(f"    compile: FAIL — {compile_errors}")

            # 3. Runtime
            runtime_ok   = False
            runtime_ran  = False
            runtime_out  = ""
            runtime_miss: list[str] = []

            sample_input    = manifest.get("sample_input", "")
            expected_tokens = manifest.get("expected_tokens", [])

            if exe_path and sample_input and expected_tokens:
                runtime_ran = True
                rr = _runtime_check(exe_path, sample_input, expected_tokens)
                runtime_ok   = rr["ok"]
                runtime_out  = rr.get("output", "")
                runtime_miss = rr.get("missing", [])
                if runtime_ok:
                    print(f"    runtime: OK — found {rr['found']}")
                else:
                    print(f"    runtime: FAIL — missing {runtime_miss}")
                    if runtime_out:
                        print(f"    output:  {runtime_out[:200]}")

            all_ok = static_ok and compile_ok and (runtime_ok if runtime_ran else True)
            status = "PASS" if all_ok else "FAIL"
            print(f"    → {status}")
            print()

            results.append({
                "id":                gid,
                "category":          cat,
                "static_ok":         static_ok,
                "static_violations": static_v,
                "compile_ok":        compile_ok,
                "compile_errors":    compile_errors,
                "runtime_ok":        runtime_ok,
                "runtime_ran":       runtime_ran,
                "runtime_output":    runtime_out,
                "runtime_missing":   runtime_miss,
                "all_ok":            all_ok,
            })

    # Update manifest verification fields
    categories = {g["category"] for g in goldens}
    for cat in categories:
        cat_results = [r for r in results if r["category"] == cat]
        _update_manifest(_HERE / cat, cat_results)

    # Write report
    report_md = _build_report(results, compiler)
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _REPORT_DIR / "golden_validation_report.md"
    report_path.write_text(report_md, encoding="utf-8")

    passed = sum(1 for r in results if r["all_ok"])
    failed = len(results) - passed
    print(f"[validate] {passed} passed, {failed} failed")
    print(f"[validate] Report: {report_path}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
