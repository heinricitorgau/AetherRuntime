#!/usr/bin/env python3
"""Offline C exam evaluation runner.

The runner intentionally stays dependency-free: Python standard library,
local_ai/run.sh for model calls, and an installed C compiler are enough.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


def default_eval_dir() -> Path:
    """Get default eval cases directory."""
    return Path(__file__).resolve().parent / "eval_cases" / "c_exam"


def case_points(case: dict[str, Any]) -> float:
    """Read a case point value defensively from JSON."""
    try:
        return float(case.get("points", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def display_points(points: float) -> int | float:
    """Keep integer point totals tidy in console and JSON summaries."""
    return int(points) if points.is_integer() else points


def local_ai_run_script() -> Path:
    """Return the repo-local local_ai/run.sh regardless of caller cwd."""
    local_ai_dir = Path(__file__).resolve().parent
    return local_ai_dir / "run.sh"


def load_eval_cases(eval_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load all JSON eval case files."""
    directory = eval_dir or default_eval_dir()
    cases = []
    for json_file in sorted(directory.glob("*.json")):
        try:
            case = json.loads(json_file.read_text(encoding="utf-8"))
            case["_filename"] = json_file.name
            cases.append(case)
        except json.JSONDecodeError as e:
            print(f"Warning: error loading {json_file.name}: {e}", file=sys.stderr)
    return cases


def extract_c_code(text: str) -> str:
    """Extract C code from text (markdown or plain)."""
    matches = re.findall(r"```(?:c|C)\s*\n(.*?)```", text, re.DOTALL)
    if matches:
        return matches[0].strip()

    matches = re.findall(r"```\s*\n(.*?)```", text, re.DOTALL)
    if matches:
        return matches[0].strip()

    include_at = text.find("#include")
    if include_at >= 0:
        return text[include_at:].strip()

    return text.strip()


def find_c_compiler() -> str | None:
    """Find available C compiler: cc, gcc, or clang."""
    for compiler in ("cc", "gcc", "clang"):
        path = shutil.which(compiler)
        if path:
            return path
    return None


def compile_c_code(code: str, work_dir: Path, case_id: str) -> tuple[bool, str, Path | None]:
    """Compile C code and return (success, message, executable_path)."""
    compiler = find_c_compiler()
    if not compiler:
        return False, "No C compiler found (cc/gcc/clang)", None

    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", case_id or "answer")
    source_path = work_dir / f"{safe_id}.c"
    exe_path = work_dir / safe_id
    source_path.write_text(code, encoding="utf-8")

    try:
        result = subprocess.run(
            [compiler, "-std=c99", "-Wall", "-Wextra", "-o", str(exe_path), str(source_path), "-lm"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, "Compiled successfully", exe_path
        error_msg = (result.stderr or result.stdout).strip()
        return False, f"Compilation failed: {error_msg[:500]}", None
    except subprocess.TimeoutExpired:
        return False, "Compilation timeout (10s)", None
    except Exception as e:
        return False, f"Compilation error: {str(e)[:200]}", None


def run_c_program(exe_path: Path, sample_input: str, timeout: int = 5) -> tuple[bool, str]:
    """Run compiled C program with input and return (success, output)."""
    try:
        result = subprocess.run(
            [str(exe_path)],
            input=sample_input if sample_input.endswith("\n") else sample_input + "\n",
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, f"Timeout after {timeout}s"
    except Exception as e:
        return False, f"Execution error: {str(e)[:100]}"


def check_output_keywords(output: str, case: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check if output contains expected keywords."""
    checker = case.get("checker_rules", {})
    behavior = case.get("expected_behavior", {})
    keywords = []
    keywords.extend(checker.get("output_keywords", []))
    keywords.extend(behavior.get("output_contains", []))

    missing = []
    for keyword in keywords:
        if str(keyword).lower() not in output.lower():
            missing.append(str(keyword))

    return len(missing) == 0, missing


def check_structure(code: str, case: dict[str, Any]) -> tuple[bool, list[str]]:
    """Smoke-check that the answer looks like a complete C solution."""
    checker = case.get("checker_rules", {})
    required = checker.get("required_code_keywords")
    if required is None:
        required = checker.get("keywords", ["#include", "main", "scanf", "printf"])

    missing = []
    lower_code = code.lower()
    for keyword in required:
        if str(keyword).lower() not in lower_code:
            missing.append(str(keyword))

    return len(missing) == 0, missing


def check_expected_behavior(output: str, case: dict[str, Any]) -> tuple[bool, str]:
    """Check lightweight numeric/output behavior."""
    behavior = case.get("expected_behavior", {})

    min_val = behavior.get("min_value")
    max_val = behavior.get("max_value")
    if min_val is not None or max_val is not None:
        numbers = re.findall(r"-?\d+\.?\d*", output)
        if numbers:
            try:
                val = float(numbers[-1])  # Use last number found
                if min_val is not None and val < min_val:
                    return False, f"Value {val} < minimum {min_val}"
                if max_val is not None and val > max_val:
                    return False, f"Value {val} > maximum {max_val}"
            except ValueError:
                pass
    
    return True, "Expected behavior smoke check passed"


def run_smoke_tests(code: str, case: dict[str, Any]) -> dict[str, Any]:
    """Run smoke tests on code: compile, run, check output."""
    checker_rules = case.get("checker_rules", {})
    timeout = checker_rules.get("timeout_seconds", 5)
    sample_input = case.get("sample_input", "")
    
    results = {
        "case_id": case.get("id", "unknown"),
        "compile_pass": False,
        "run_pass": False,
        "keyword_pass": False,
        "structure_pass": False,
        "score": 0.0,
        "messages": [],
    }
    
    structure_pass, missing_structure = check_structure(code, case)
    results["structure_pass"] = structure_pass
    if missing_structure:
        results["messages"].append(f"Missing code structure keywords: {missing_structure}")
    else:
        results["messages"].append("Code structure keywords found")

    if checker_rules.get("compile_required", True):
        with tempfile.TemporaryDirectory(prefix="c_exam_eval_") as tmp:
            success, msg, exe_path = compile_c_code(code, Path(tmp), case.get("id", ""))
            results["compile_pass"] = success
            results["messages"].append(f"Compile: {msg}")
            if not success:
                results["score"] = 0.0
                return results

            if checker_rules.get("runtime_required", True) and exe_path is not None:
                success, output = run_c_program(exe_path, sample_input, timeout)
                results["run_pass"] = success
                results["output"] = output[:1000]
                results["messages"].append(f"Runtime: {'OK' if success else output[:200]}")

                if success:
                    kw_pass, missing = check_output_keywords(output, case)
                    results["keyword_pass"] = kw_pass
                    if missing:
                        results["messages"].append(f"Missing output keywords: {missing}")
                    else:
                        results["messages"].append("Output keywords found")

                    behavior_pass, behavior_msg = check_expected_behavior(output, case)
                    results["behavior_pass"] = behavior_pass
                    results["messages"].append(f"Behavior: {behavior_msg}")
    else:
        results["compile_pass"] = True

    max_points = case_points(case)
    if results["compile_pass"] and results["run_pass"]:
        if results["keyword_pass"] and results["structure_pass"]:
            score_pct = 1.0
        elif results["keyword_pass"] or results["structure_pass"]:
            score_pct = 0.7
        else:
            score_pct = 0.5
    else:
        score_pct = 0.0 if not results["compile_pass"] else 0.25

    results["score"] = round(max_points * score_pct, 1)

    return results


def build_model_prompt(case: dict[str, Any]) -> str:
    features = "\n".join(f"- {feature}" for feature in case.get("required_features", []))
    sample_input = case.get("sample_input", "")
    expected = json.dumps(case.get("expected_behavior", {}), ensure_ascii=False)
    return (
        "Write a complete, single-file C99 program for this exam problem.\n"
        "Return only C code inside one ```c code block. Do not include explanations.\n\n"
        f"Problem:\n{case.get('prompt', '')}\n\n"
        f"Required features:\n{features}\n\n"
        f"Sample stdin:\n{sample_input}\n\n"
        f"Expected behavior smoke hints:\n{expected}\n"
    )


def generate_ai_response(case: dict[str, Any]) -> str:
    """Generate C code from AI for the given case (requires local_ai/run.sh)."""
    prompt = case.get("prompt", "")
    if not prompt:
        return ""
    
    try:
        run_script = local_ai_run_script()
        
        if not run_script.exists():
            print(f"Warning: local_ai/run.sh not found at {run_script}", file=sys.stderr)
            return ""
        
        full_prompt = build_model_prompt(case)

        result = subprocess.run(
            ["bash", str(run_script), "--output-format", "text", "prompt", full_prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
        if result.returncode == 0:
            return combined

        extracted = extract_c_code(combined)
        if "#include" in extracted or "int main" in extracted:
            print(
                f"Warning: local AI returned non-zero for {case.get('id')}, but C code was found; continuing.",
                file=sys.stderr,
            )
            return extracted

        details = combined.strip()
        print(f"Warning: AI generation failed for {case.get('id')}: {details[:300]}", file=sys.stderr)
        return ""
    except subprocess.TimeoutExpired:
        print(f"Warning: AI generation timeout for {case.get('id')}", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"Warning: error generating code: {e}", file=sys.stderr)
        return ""


def run_evaluation(
    eval_dir: Path | None = None,
    use_ai: bool = False,
    case_filter: str | None = None,
    output_file: Path | None = None,
    answers_dir: Path | None = None,
) -> dict[str, Any]:
    """Run full evaluation suite."""
    eval_dir = eval_dir or default_eval_dir()
    cases = load_eval_cases(eval_dir)
    
    if case_filter:
        needle = case_filter.lower()
        cases = [
            c for c in cases
            if needle in c.get("id", "").lower()
            or needle in c.get("topic", "").lower()
            or needle in str(c.get("year", "")).lower()
            or needle in c.get("_filename", "").lower()
        ]
    
    if not cases:
        print("No eval cases found", file=sys.stderr)
        return {"error": "No cases found"}
    
    total_points = sum(case_points(case) for case in cases)

    report = {
        "timestamp": int(time.time()),
        "total_cases": len(cases),
        "cases_tested": 0,
        "total_points": display_points(total_points),
        "total_earned": 0,
        "results": [],
    }
    
    for case in cases:
        case_id = case.get("id", "unknown")
        print(f"Evaluating {case_id}...", end=" ", flush=True)
        
        points = case_points(case)

        if use_ai:
            code = generate_ai_response(case)
        elif answers_dir:
            answer_path = answers_dir / f"{case_id}.c"
            code = answer_path.read_text(encoding="utf-8") if answer_path.exists() else ""
        else:
            code = case.get("reference_answer", "")

        if not code:
            print("no answer")
            results = {
                "case_id": case_id,
                "compile_pass": False,
                "run_pass": False,
                "keyword_pass": False,
                "structure_pass": False,
                "score": 0.0,
                "messages": ["No answer code supplied. Use --use-ai or --answers-dir."],
                "case_info": {
                    "year": case.get("year"),
                    "exam": case.get("exam"),
                    "topic": case.get("topic"),
                    "points": display_points(points),
                },
            }
            report["results"].append(results)
            report["cases_tested"] += 1
            continue
        
        code = extract_c_code(code)
        results = run_smoke_tests(code, case)
        
        # Print result summary
        status = "✅" if results["compile_pass"] else "❌"
        print(f"{status} score={results['score']}/{display_points(points)}")
        
        results["case_info"] = {
            "year": case.get("year"),
            "exam": case.get("exam"),
            "topic": case.get("topic"),
            "points": display_points(points),
        }
        
        report["results"].append(results)
        report["cases_tested"] += 1
        report["total_earned"] += results["score"]
    
    # Calculate summary
    if total_points > 0:
        report["pass_rate"] = round(100 * report["total_earned"] / total_points, 1)
    else:
        report["pass_rate"] = 0.0
    
    # Save report
    if output_file is None:
        output_file = Path(eval_dir).parent / "eval_report.json"
    
    output_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📊 Report saved to {output_file}")
    print(f"Summary: {display_points(float(report['total_earned']))}/{report['total_points']} points ({report['pass_rate']}%)")
    
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="C Exam Offline Evaluation Runner")
    parser.add_argument(
        "--eval-dir",
        type=Path,
        default=None,
        help="Path to eval cases directory (default: local_ai/eval_cases/c_exam)",
    )
    parser.add_argument(
        "--use-ai",
        action="store_true",
        help="Generate code using local AI (requires local_ai/run.sh)",
    )
    parser.add_argument(
        "--filter",
        default=None,
        help="Filter cases by ID substring (e.g., '2021', 'series')",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output report file (default: eval_report.json)",
    )
    parser.add_argument(
        "--answers-dir",
        type=Path,
        default=None,
        help="Optional directory containing <case_id>.c answers for offline smoke tests",
    )
    args = parser.parse_args()
    
    run_evaluation(
        eval_dir=args.eval_dir,
        use_ai=args.use_ai,
        case_filter=args.filter,
        output_file=args.output,
        answers_dir=args.answers_dir,
    )


if __name__ == "__main__":
    main()
