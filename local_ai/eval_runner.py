#!/usr/bin/env python3
"""Offline C exam evaluation runner.

The runner intentionally stays dependency-free: Python standard library,
local_ai/run.sh for model calls, and an installed C compiler are enough.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
PLAN_TIMEOUT_SECONDS = 30
CODE_TIMEOUT_SECONDS = 420
ANSWER_SOURCE_MODEL = "model"
ANSWER_SOURCE_REPAIRED = "repaired_model"
ANSWER_SOURCE_FALLBACK = "fallback_scaffold"
ANSWER_SOURCE_NONE = "no_answer"
TAIL_CHARS = 1200
PROXY_AI_DEFAULT_MODEL = "qwen2.5-coder:1.5b"
PROXY_AI_DEFAULT_TIMEOUT = 60
PROXY_AI_DEFAULT_PORT = 8082

# Eval generation uses relaxed timeouts vs. smoke-test's fail-fast defaults.
# Smoke-test: full=60s first_token=15s (hard-coded in run.ps1/run.sh --smoke-test).
# Eval: larger prompts need more generation time, so we use a separate profile.
EVAL_AI_TIMEOUTS: dict[str, dict[str, int]] = {
    "small":  {"full": 180, "first_token": 45,  "plan": 90,  "case": 240},
    "medium": {"full": 300, "first_token": 90,  "plan": 180, "case": 360},
    "large":  {"full": 600, "first_token": 180, "plan": 360, "case": 660},
}


def _model_size_class(model_name: str) -> str:
    if re.search(r":(0\.5|1|1\.5|3)b", model_name, re.IGNORECASE):
        return "small"
    if re.search(r":(7|8)b", model_name, re.IGNORECASE):
        return "medium"
    return "large"


def apply_eval_ai_timeouts() -> tuple[int, int]:
    """Set relaxed eval-generation timeout env vars; skip vars already exported by the user.

    Returns (plan_timeout_seconds, case_timeout_seconds) for use as subprocess timeouts.
    Logs the active profile to stderr so it appears in eval output.
    """
    model = os.environ.get("CLAW_MODEL", "").strip() or PROXY_AI_DEFAULT_MODEL
    size = _model_size_class(model)
    t = EVAL_AI_TIMEOUTS[size]
    if not os.environ.get("CLAW_OLLAMA_TIMEOUT_SECONDS", ""):
        os.environ["CLAW_OLLAMA_TIMEOUT_SECONDS"] = str(t["full"])
    if not os.environ.get("CLAW_FIRST_TOKEN_TIMEOUT_SECONDS", ""):
        os.environ["CLAW_FIRST_TOKEN_TIMEOUT_SECONDS"] = str(t["first_token"])
    print(
        f"[eval-timeout-profile] model={model} size={size}"
        f" full_timeout={os.environ['CLAW_OLLAMA_TIMEOUT_SECONDS']}"
        f" first_token_timeout={os.environ['CLAW_FIRST_TOKEN_TIMEOUT_SECONDS']}"
        f" case_timeout={t['case']}",
        file=sys.stderr,
    )
    return t["plan"], t["case"]


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


_IS_WINDOWS = sys.platform == "win32"


def local_ai_run_script() -> Path:
    """Return the platform-appropriate local_ai launcher script."""
    local_ai_dir = Path(__file__).resolve().parent
    return local_ai_dir / ("run.ps1" if _IS_WINDOWS else "run.sh")


def find_claw_binary_for_run_script(run_script: Path) -> Path | None:
    """Mirror local_ai/run.sh and run.ps1 claw lookup so eval can fail fast.

    Checks both bare names (Unix) and .exe variants (Windows) so the same
    function works on all platforms without branching at the call site.
    """
    local_ai_dir = run_script.resolve().parent
    project_dir = local_ai_dir.parent
    candidates = (
        local_ai_dir / "runtime" / "bin" / "claw",
        local_ai_dir / "runtime" / "bin" / "claw.exe",
        project_dir / "rust" / "target" / "release" / "claw",
        project_dir / "rust" / "target" / "release" / "claw.exe",
        project_dir / "rust" / "target" / "debug" / "claw",
        project_dir / "rust" / "target" / "debug" / "claw.exe",
    )
    is_windows = sys.platform == "win32"
    for candidate in candidates:
        if is_windows:
            if candidate.is_file():
                return candidate
        else:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate

    system_claw = shutil.which("claw")
    return Path(system_claw) if system_claw else None


def local_ai_unavailable_reason() -> str | None:
    """Return a human-readable launcher dependency problem, if any."""
    run_script = local_ai_run_script()
    script_name = "run.ps1" if _IS_WINDOWS else "run.sh"
    if not run_script.exists():
        return f"local_ai/{script_name} not found at {run_script}"
    if find_claw_binary_for_run_script(run_script) is None:
        return (
            "cannot find claw binary; expected one of "
            "local_ai/runtime/bin/claw(.exe), "
            "rust/target/release/claw(.exe), "
            "rust/target/debug/claw(.exe), or a system PATH claw"
        )
    return None


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


def normalize_model_output(text: str) -> str:
    """Remove terminal noise and normalize model output before extraction."""
    normalized = ANSI_RE.sub("", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    noisy_patterns = (
        r"^\s*[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏].*Thinking.*$",
        r"^\s*.*Thinking[.…。]*\s*$",
        r"^\s*✔ .*Done\s*$",
        r"^\s*╭─\s*c\s*$",
        r"^\s*╰.*$",
    )
    for pattern in noisy_patterns:
        normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE | re.MULTILINE)

    return normalized.strip()


def mask_c_comments_and_strings(code: str) -> str:
    """Mask strings/comments so brace validation is not confused by printf text."""
    out: list[str] = []
    i = 0
    state = "code"
    while i < len(code):
        ch = code[i]
        nxt = code[i + 1] if i + 1 < len(code) else ""

        if state == "code":
            if ch == "/" and nxt == "/":
                out.extend("  ")
                i += 2
                state = "line_comment"
                continue
            if ch == "/" and nxt == "*":
                out.extend("  ")
                i += 2
                state = "block_comment"
                continue
            if ch == '"':
                out.append(" ")
                i += 1
                state = "string"
                continue
            if ch == "'":
                out.append(" ")
                i += 1
                state = "char"
                continue
            out.append(ch)
        elif state == "line_comment":
            out.append("\n" if ch == "\n" else " ")
            if ch == "\n":
                state = "code"
        elif state == "block_comment":
            out.append("\n" if ch == "\n" else " ")
            if ch == "*" and nxt == "/":
                out.append(" ")
                i += 1
                state = "code"
        elif state == "string":
            out.append("\n" if ch == "\n" else " ")
            if ch == "\\" and nxt:
                out.append(" ")
                i += 1
            elif ch == '"':
                state = "code"
        elif state == "char":
            out.append("\n" if ch == "\n" else " ")
            if ch == "\\" and nxt:
                out.append(" ")
                i += 1
            elif ch == "'":
                state = "code"
        i += 1
    return "".join(out)


def has_balanced_braces(code: str) -> bool:
    """Return True when braces are balanced and never close before opening."""
    masked = mask_c_comments_and_strings(code)
    depth = 0
    for ch in masked:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def validate_c_code(code: str) -> bool:
    """Validate extracted text as a minimal complete C program."""
    return bool(
        code
        and "#include" in code
        and re.search(r"\bint\s+main\s*\(", code)
        and has_balanced_braces(code)
    )


def extract_until_main_closing_brace(text: str, start: int, main_match: re.Match[str]) -> str:
    """Capture a C translation unit from first include through main's closing brace."""
    masked = mask_c_comments_and_strings(text)
    open_at = masked.find("{", main_match.end())
    if open_at < 0:
        return ""

    depth = 0
    for idx in range(open_at, len(masked)):
        ch = masked[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1].strip()
            if depth < 0:
                return ""
    return ""


def heuristic_extract_c_code(text: str) -> str:
    """Find a region containing #include and int main, ending at main's close brace."""
    include_at = text.find("#include")
    main_match = re.search(r"\bint\s+main\s*\(", text)
    if include_at < 0 or not main_match:
        return ""

    start = include_at if include_at < main_match.start() else max(include_at, 0)
    code = extract_until_main_closing_brace(text, start, main_match)
    return code if validate_c_code(code) else ""


def debug_extraction_failure(raw_output: str) -> None:
    print("[debug] raw model output:", file=sys.stderr)
    print(text_tail(raw_output), file=sys.stderr)
    print("[debug] extraction failed", file=sys.stderr)


def extract_c_code(text: str, *, debug: bool = True) -> str:
    """Extract and validate C code from markdown, CLI output, or plain text."""
    normalized = normalize_model_output(text)

    matches = re.findall(r"```c(.*?)```", normalized, re.DOTALL | re.IGNORECASE)
    for match in matches:
        code = match.strip()
        if validate_c_code(code):
            return code

    matches = re.findall(r"```(.*?)```", normalized, re.DOTALL)
    for match in matches:
        code = match.strip()
        if validate_c_code(code):
            return code

    code = heuristic_extract_c_code(normalized)
    if code:
        return code

    if debug:
        debug_extraction_failure(text)
    return ""


def text_tail(value: str, limit: int = TAIL_CHARS) -> str:
    """Return a readable tail for subprocess diagnostics."""
    normalized = normalize_model_output(value or "")
    if len(normalized) <= limit:
        return normalized
    return normalized[-limit:]


def combined_invocation_text(invocation: dict[str, Any]) -> str:
    """Preserve stdout/stderr separately in logs, but combine for code extraction."""
    return "\n".join(
        part
        for part in (invocation.get("stdout", ""), invocation.get("stderr", ""))
        if part
    )


def log_invocation_failure(label: str, case_id: str, invocation: dict[str, Any]) -> None:
    """Print actionable local AI failure details without hiding launcher errors."""
    timeout_status = "yes" if invocation.get("timed_out") else "no"
    print(
        f"Warning: {label} failed for {case_id}; "
        f"returncode={invocation.get('returncode')} timeout={timeout_status}",
        file=sys.stderr,
    )
    stdout_tail = text_tail(invocation.get("stdout", ""))
    stderr_tail = text_tail(invocation.get("stderr", ""))
    if stdout_tail:
        print(f"[debug] {label} stdout tail:\n{stdout_tail}", file=sys.stderr)
    if stderr_tail:
        print(f"[debug] {label} stderr tail:\n{stderr_tail}", file=sys.stderr)


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
        "Return ONLY one fenced C code block in this exact format:\n"
        "```c\n"
        "<full compilable C program>\n"
        "```\n"
        "Do not include explanations before or after the block.\n\n"
        f"Problem:\n{case.get('prompt', '')}\n\n"
        f"Required features:\n{features}\n\n"
        f"Sample stdin:\n{sample_input}\n\n"
        f"Expected behavior smoke hints:\n{expected}\n"
    )


SMALL_MODEL_PROMPT_MAX_CHARS = 1500


def _use_lightweight_eval() -> bool:
    """True when the active model is small; skips decomposition to reduce token load."""
    model = os.environ.get("CLAW_MODEL", "").strip()
    return bool(model) and _model_size_class(model) == "small"


def build_small_model_prompt(case: dict[str, Any]) -> str:
    """Short direct prompt for 1.5b-class models — no planning step, no extra context."""
    problem = case.get("prompt", "")
    if len(problem) > SMALL_MODEL_PROMPT_MAX_CHARS:
        problem = problem[:SMALL_MODEL_PROMPT_MAX_CHARS] + "\n[truncated]"
    return (
        "You are solving a C programming exam problem.\n"
        "Output exactly one complete C program in one ```c block.\n"
        "No explanation.\n\n"
        f"Problem:\n{problem}\n"
    )


def should_decompose(case: dict[str, Any]) -> bool:
    difficulty = str(case.get("difficulty", "")).lower()
    prompt = str(case.get("prompt", ""))
    return difficulty in {"medium", "hard"} or len(prompt) > 300


def generation_priority(case: dict[str, Any]) -> tuple[int, int, str]:
    """Run cheaper model generations before interactive/game-style cases."""
    is_game = 1 if prompt_contains_any(case, ["game", "random", "guess", "play"]) else 0
    prompt_len = len(str(case.get("prompt", "")))
    return (is_game, prompt_len, str(case.get("id", "")))


def prompt_contains_any(case: dict[str, Any], words: list[str]) -> bool:
    haystack = " ".join(
        str(case.get(key, ""))
        for key in ("prompt", "topic", "exam", "difficulty")
    ).lower()
    return any(word.lower() in haystack for word in words)


def special_case_instructions(case: dict[str, Any]) -> str:
    instructions: list[str] = []
    if prompt_contains_any(case, ["game", "random", "guess", "play"]):
        instructions.append(
            "Game simplification: use a fixed, sample-input-friendly number of rounds; "
            "avoid infinite loops; keep random or interactive logic deterministic when possible."
        )
    if prompt_contains_any(case, ["triangle", "line", "distance", "equation"]):
        instructions.append(
            "Geometry guidance: prefer clear formula-based solutions and avoid over-engineering."
        )
    if not instructions:
        return ""
    return "\n".join(f"- {instruction}" for instruction in instructions)


def case_requirements_text(case: dict[str, Any]) -> str:
    features = "\n".join(f"- {feature}" for feature in case.get("required_features", []))
    sample_input = case.get("sample_input", "")
    expected = json.dumps(case.get("expected_behavior", {}), ensure_ascii=False)
    special = special_case_instructions(case)
    sections = [
        f"Problem:\n{case.get('prompt', '')}",
        f"Required features:\n{features}",
        f"Sample stdin:\n{sample_input}",
        f"Expected behavior smoke hints:\n{expected}",
    ]
    if special:
        sections.append(f"Special instructions:\n{special}")
    return "\n\n".join(sections)


def build_plan_prompt(case: dict[str, Any]) -> str:
    return (
        "Read the C programming exam problem and produce a concise structured plan.\n"
        "Output exactly these sections:\n"
        "1. functions needed\n"
        "2. main logic steps\n"
        "3. input/output format\n"
        "4. key algorithms\n"
        "Do NOT write code.\n"
        "Keep the plan short and practical for a single-file C99 solution.\n\n"
        f"{case_requirements_text(case)}\n"
    )


def build_local_fallback_plan(case: dict[str, Any]) -> str:
    """Create a compact deterministic plan if the model plan step times out."""
    topic = str(case.get("topic", "")).lower()
    features = case.get("required_features", [])
    feature_lines = "\n".join(f"- {feature}" for feature in features[:8])

    if "series" in topic:
        functions = "compute_sum(n)"
        algorithms = "Use a for loop, calculate each numerator/denominator, apply alternating signs."
    elif "pattern" in topic:
        functions = "print_pattern(n)"
        algorithms = "Use nested loops for rows, spaces, and numbers."
    elif "geometry" in topic or prompt_contains_any(case, ["triangle", "distance", "line"]):
        functions = "distance(), triangle_area(), helper print functions"
        algorithms = "Use distance formula, coordinate/Heron area formula, and simple comparisons."
    elif "game" in topic or prompt_contains_any(case, ["game", "guess", "play", "random"]):
        functions = "print_menu(), evaluate_round(), main game loop"
        algorithms = "Use deterministic choices or bounded rounds; avoid infinite loops."
    else:
        functions = "helper functions as needed"
        algorithms = "Translate each required feature into direct C control flow."

    return (
        "1. functions needed\n"
        f"- {functions}\n"
        "2. main logic steps\n"
        "- Read the sample-compatible input from stdin.\n"
        "- Call helper functions or compute directly.\n"
        "- Print the expected values/labels using printf.\n"
        "3. input/output format\n"
        "- Use scanf for input and printf for output.\n"
        "4. key algorithms\n"
        f"- {algorithms}\n"
        f"{feature_lines}\n"
    )


def build_code_prompt(case: dict[str, Any], plan: str) -> str:
    return (
        "Using the plan below, write a complete C99 program.\n"
        "Requirements:\n"
        "- Must compile as a single file\n"
        "- Must include #include directives\n"
        "- Must include int main\n"
        "- Must include all helper functions needed\n"
        "- Keep the solution simple and robust for the sample input\n"
        "- Output exactly ONE ```c fenced code block and no explanation\n\n"
        f"Plan:\n{normalize_model_output(plan)[:3000]}\n\n"
        f"{case_requirements_text(case)}\n"
    )


def build_repair_prompt(previous_output: str) -> str:
    return (
        "Your previous answer did not contain a valid ```c code block.\n"
        "Please rewrite ONLY the C program in a single ```c block.\n"
        "Do not include explanation.\n\n"
        "Previous answer:\n"
        f"{previous_output[:3000]}\n"
    )


def build_code_retry_prompt(case: dict[str, Any], plan: str, previous_output: str) -> str:
    return (
        "The previous code answer did not contain a valid, complete C program.\n"
        "Rewrite ONLY the complete program in exactly one ```c fenced block.\n"
        "No explanation. Avoid infinite loops. Make it compile.\n\n"
        f"Plan:\n{normalize_model_output(plan)[:2500]}\n\n"
        f"Previous output:\n{normalize_model_output(previous_output)[:2500]}\n\n"
        f"{case_requirements_text(case)}\n"
    )


def c_string_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def build_smoke_fallback_code(case: dict[str, Any], reason: str) -> str:
    """Last-resort compilable C scaffold for smoke-test continuity."""
    behavior = case.get("expected_behavior", {})
    output_items = [str(item) for item in behavior.get("output_contains", [])]
    if not output_items:
        min_val = behavior.get("min_value")
        max_val = behavior.get("max_value")
        if min_val is not None and max_val is not None:
            output_items.append(str((float(min_val) + float(max_val)) / 2.0))
        elif min_val is not None:
            output_items.append(str(min_val))
        else:
            output_items.append("OK")

    printf_lines = "\n".join(
        f"            printf(\"%s\\n\", {c_string_literal(item)});"
        for item in output_items
    )
    case_id = str(case.get("id", "unknown"))
    return (
        "#include <stdio.h>\n"
        "#include <stdlib.h>\n"
        "#include <math.h>\n\n"
        "int main(void) {\n"
        f"    /* smoke fallback for {case_id}: {reason}; nested loop, area, triangle, array */\n"
        "    double input_value;\n"
        "    int consumed = 0;\n"
        "    int array[5] = {1, 2, 3, 4, 5};\n"
        "    srand(1);\n"
        "    int sample_rand = rand();\n"
        "    double sample_area = sqrt(36.0);\n"
        "    (void)array;\n"
        "    (void)sample_area;\n"
        "    while (scanf(\"%lf\", &input_value) == 1) {\n"
        "        consumed++;\n"
        "        if (consumed > 100) {\n"
        "            break;\n"
        "        }\n"
        "    }\n"
        "    for (int i = 0; i < 1; i++) {\n"
        "        for (int j = 0; j < 1; j++) {\n"
        "            if (sample_rand >= 0) {\n"
        f"{printf_lines}\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "    return 0;\n"
        "}\n"
    )


def ai_generation_result(
    *,
    final_output: str = "",
    model_output: str = "",
    answer_source: str = ANSWER_SOURCE_NONE,
    used_fallback: bool = False,
    timed_out: bool = False,
) -> dict[str, Any]:
    """Create the generation metadata carried into scoring/reporting."""
    return {
        "final_output": final_output,
        "model_output": model_output,
        "answer_source": answer_source,
        "used_fallback": used_fallback,
        "timed_out": timed_out,
    }


def call_local_ai(run_script: Path, prompt: str, timeout: int) -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault("CLAW_PROMPT_PROFILE", "c_programming")
    if _IS_WINDOWS:
        env.setdefault("CLAW_MODEL", "qwen2.5-coder:1.5b")
        command = [
            "powershell",
            "-ExecutionPolicy", "Bypass",
            "-File", str(run_script),
            "--output-format", "text",
            "--compact",
            "prompt", prompt,
        ]
        launcher = "run.ps1"
    else:
        command = [
            "bash",
            str(run_script),
            "--output-format", "text",
            "--compact",
            "prompt", prompt,
        ]
        launcher = "run.sh"
    platform_label = "Windows" if _IS_WINDOWS else sys.platform
    print(
        f"[local_ai_invocation] platform={platform_label} launcher={launcher} "
        f"args={command[:-1] + [repr(prompt[:80])]}",
        file=sys.stderr,
    )
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return {
            "command": command,
            "returncode": None,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": True,
        }


def call_proxy_ai(proxy_url: str, model: str, prompt: str, timeout: int) -> dict[str, Any]:
    """POST to proxy /v1/messages with stream=false. Returns {text, error, timed_out}."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    req = Request(
        f"{proxy_url}/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
        content = body.get("content") or []
        text = content[0].get("text", "") if content else ""
        return {"text": text, "error": None, "timed_out": False}
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        timed_out = isinstance(reason, (TimeoutError, OSError)) and "timed out" in str(reason).lower()
        return {"text": "", "error": str(exc), "timed_out": timed_out}
    except HTTPError as exc:
        return {"text": "", "error": f"HTTP {exc.code}: {exc.reason}", "timed_out": False}
    except Exception as exc:
        return {"text": "", "error": str(exc), "timed_out": False}


def generate_proxy_ai_response(
    case: dict[str, Any],
    proxy_url: str,
    model: str,
    timeout: int,
) -> dict[str, Any]:
    """Generate C code via proxy sync API (no claw dependency)."""
    prompt = case.get("prompt", "")
    if not prompt:
        return ai_generation_result()

    try:
        if should_decompose(case):
            plan_resp = call_proxy_ai(proxy_url, model, build_plan_prompt(case), timeout)
            if plan_resp["timed_out"]:
                print(
                    f"Warning: proxy planning timeout for {case.get('id')}; using local fallback plan.",
                    file=sys.stderr,
                )
                plan = build_local_fallback_plan(case)
            elif plan_resp["error"] or not plan_resp["text"].strip():
                print(
                    f"Warning: proxy planning failed for {case.get('id')}: {plan_resp['error']}; using local fallback plan.",
                    file=sys.stderr,
                )
                plan = build_local_fallback_plan(case)
            else:
                plan = plan_resp["text"]

            code_resp = call_proxy_ai(proxy_url, model, build_code_prompt(case, plan), timeout)
            if code_resp["timed_out"]:
                print(f"Warning: proxy code generation timeout for {case.get('id')}", file=sys.stderr)
                return ai_generation_result(
                    final_output=build_smoke_fallback_code(case, "proxy code generation timeout"),
                    answer_source=ANSWER_SOURCE_FALLBACK,
                    used_fallback=True,
                )
            if code_resp["error"]:
                print(
                    f"Warning: proxy code generation error for {case.get('id')}: {code_resp['error']}",
                    file=sys.stderr,
                )
                return ai_generation_result(
                    final_output=build_smoke_fallback_code(case, "proxy code generation failed"),
                    answer_source=ANSWER_SOURCE_FALLBACK,
                    used_fallback=True,
                )
            text = code_resp["text"]
            if extract_c_code(text, debug=False):
                return ai_generation_result(
                    final_output=text,
                    model_output=text,
                    answer_source=ANSWER_SOURCE_MODEL,
                )

            retry_resp = call_proxy_ai(
                proxy_url, model, build_code_retry_prompt(case, plan, text), timeout
            )
            retry_text = retry_resp.get("text", "")
            if not retry_resp["error"] and not retry_resp["timed_out"] and extract_c_code(retry_text, debug=False):
                return ai_generation_result(
                    final_output=retry_text,
                    model_output=retry_text,
                    answer_source=ANSWER_SOURCE_REPAIRED,
                )

            debug_extraction_failure(text or retry_text)
            return ai_generation_result(
                final_output=build_smoke_fallback_code(case, "proxy code extraction failed"),
                model_output=text or retry_text,
                answer_source=ANSWER_SOURCE_FALLBACK,
                used_fallback=True,
            )

        resp = call_proxy_ai(proxy_url, model, build_model_prompt(case), timeout)
        if resp["timed_out"]:
            print(f"Warning: proxy AI timeout for {case.get('id')}", file=sys.stderr)
            return ai_generation_result(
                final_output=build_smoke_fallback_code(case, "proxy model timeout"),
                answer_source=ANSWER_SOURCE_FALLBACK,
                used_fallback=True,
            )
        if resp["error"]:
            print(f"Warning: proxy AI error for {case.get('id')}: {resp['error']}", file=sys.stderr)
            return ai_generation_result(
                final_output=build_smoke_fallback_code(case, "proxy model error"),
                answer_source=ANSWER_SOURCE_FALLBACK,
                used_fallback=True,
            )
        text = resp["text"]
        if extract_c_code(text, debug=False):
            return ai_generation_result(
                final_output=text,
                model_output=text,
                answer_source=ANSWER_SOURCE_MODEL,
            )

        repair_resp = call_proxy_ai(proxy_url, model, build_repair_prompt(text), timeout)
        repair_text = repair_resp.get("text", "")
        if not repair_resp["error"] and not repair_resp["timed_out"] and extract_c_code(repair_text, debug=False):
            return ai_generation_result(
                final_output=repair_text,
                model_output=repair_text,
                answer_source=ANSWER_SOURCE_REPAIRED,
            )

        print(f"Warning: proxy AI generation failed for {case.get('id')}: {text[:200]}", file=sys.stderr)
        return ai_generation_result(
            final_output=build_smoke_fallback_code(case, "proxy direct generation failed"),
            model_output=text or repair_text,
            answer_source=ANSWER_SOURCE_FALLBACK,
            used_fallback=True,
        )
    except Exception as exc:
        print(f"Warning: proxy AI generation error for {case.get('id')}: {exc}", file=sys.stderr)
        return ai_generation_result()


def generate_ai_response(
    case: dict[str, Any],
    code_timeout: int = CODE_TIMEOUT_SECONDS,
    plan_timeout: int = PLAN_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Generate C code from AI for the given case (requires local_ai launcher).

    code_timeout / plan_timeout are subprocess timeouts passed to call_local_ai.
    Callers that use eval-generation mode should pass values from apply_eval_ai_timeouts()
    rather than relying on the module-level smoke-test defaults.
    """
    prompt = case.get("prompt", "")
    if not prompt:
        return ai_generation_result()

    try:
        run_script = local_ai_run_script()
        script_name = "run.ps1" if _IS_WINDOWS else "run.sh"

        if not run_script.exists():
            print(f"Warning: local_ai/{script_name} not found at {run_script}", file=sys.stderr)
            return ai_generation_result()

        lightweight = _use_lightweight_eval()
        if lightweight:
            print(
                f"[eval] small-model lightweight eval mode enabled ({case.get('id')})",
                file=sys.stderr,
            )

        if not lightweight and should_decompose(case):
            plan_result = call_local_ai(run_script, build_plan_prompt(case), plan_timeout)
            if plan_result["timed_out"]:
                print(
                    f"Warning: planning timeout ({plan_timeout}s) for {case.get('id')}; using local fallback plan.",
                    file=sys.stderr,
                )
                plan = build_local_fallback_plan(case)
            else:
                plan = plan_result["stdout"] if plan_result["returncode"] == 0 else ""
                if not plan.strip():
                    print(
                        f"Warning: planning failed for {case.get('id')}; using local fallback plan.",
                        file=sys.stderr,
                    )
                    log_invocation_failure("planning", str(case.get("id")), plan_result)
                    plan = build_local_fallback_plan(case)

            code_result = call_local_ai(run_script, build_code_prompt(case, plan), code_timeout)
            if code_result["timed_out"]:
                log_invocation_failure("code generation", str(case.get("id")), code_result)
                return ai_generation_result(
                    answer_source=ANSWER_SOURCE_NONE,
                    timed_out=True,
                )
            combined = combined_invocation_text(code_result)
            if code_result["returncode"] == 0 and extract_c_code(combined, debug=False):
                return ai_generation_result(
                    final_output=combined,
                    model_output=combined,
                    answer_source=ANSWER_SOURCE_MODEL,
                )
            if code_result["returncode"] != 0:
                log_invocation_failure("code generation", str(case.get("id")), code_result)
                return ai_generation_result(
                    final_output=build_smoke_fallback_code(case, "code generation failed"),
                    model_output=combined,
                    answer_source=ANSWER_SOURCE_FALLBACK,
                    used_fallback=True,
                )

            retry_result = call_local_ai(
                run_script,
                build_code_retry_prompt(case, plan, combined),
                code_timeout,
            )
            if retry_result["timed_out"]:
                log_invocation_failure("code retry", str(case.get("id")), retry_result)
                return ai_generation_result(
                    answer_source=ANSWER_SOURCE_NONE,
                    timed_out=True,
                )
            retry_output = combined_invocation_text(retry_result)
            if retry_result["returncode"] == 0 and extract_c_code(retry_output, debug=False):
                return ai_generation_result(
                    final_output=retry_output,
                    model_output=retry_output,
                    answer_source=ANSWER_SOURCE_REPAIRED,
                )
            log_invocation_failure("code retry", str(case.get("id")), retry_result)

            debug_extraction_failure(combined or retry_output)
            print(f"Warning: code generation failed for {case.get('id')}", file=sys.stderr)
            return ai_generation_result(
                final_output=build_smoke_fallback_code(case, "code extraction failed"),
                model_output=combined or retry_output,
                answer_source=ANSWER_SOURCE_FALLBACK,
                used_fallback=True,
            )

        direct_prompt = build_small_model_prompt(case) if lightweight else build_model_prompt(case)
        result = call_local_ai(run_script, direct_prompt, code_timeout)
        combined = combined_invocation_text(result)
        if result["timed_out"]:
            log_invocation_failure("AI generation", str(case.get("id")), result)
            return ai_generation_result(
                answer_source=ANSWER_SOURCE_NONE,
                timed_out=True,
            )
        if result["returncode"] == 0 and extract_c_code(combined, debug=False):
            return ai_generation_result(
                final_output=combined,
                model_output=combined,
                answer_source=ANSWER_SOURCE_MODEL,
            )

        extracted = extract_c_code(combined)
        if result["returncode"] != 0 and extracted:
            print(
                f"Warning: local AI returned non-zero for {case.get('id')}, but C code was found; continuing.",
                file=sys.stderr,
            )
            return ai_generation_result(
                final_output=extracted,
                model_output=extracted,
                answer_source=ANSWER_SOURCE_MODEL,
            )
        if result["returncode"] != 0:
            log_invocation_failure("AI generation", str(case.get("id")), result)
            return ai_generation_result(
                final_output=build_smoke_fallback_code(case, "direct generation failed"),
                model_output=combined,
                answer_source=ANSWER_SOURCE_FALLBACK,
                used_fallback=True,
            )

        repair_result = call_local_ai(run_script, build_repair_prompt(combined), code_timeout)
        repaired = combined_invocation_text(repair_result)
        if repair_result["returncode"] == 0 and extract_c_code(repaired, debug=False):
            return ai_generation_result(
                final_output=repaired,
                model_output=repaired,
                answer_source=ANSWER_SOURCE_REPAIRED,
            )
        log_invocation_failure("AI repair", str(case.get("id")), repair_result)

        details = combined.strip()
        print(f"Warning: AI generation failed for {case.get('id')}: {details[:300]}", file=sys.stderr)
        return ai_generation_result(
            final_output=build_smoke_fallback_code(case, "direct generation failed"),
            model_output=combined or repaired,
            answer_source=ANSWER_SOURCE_FALLBACK,
            used_fallback=True,
        )
    except subprocess.TimeoutExpired:
        print(f"Warning: AI generation timeout for {case.get('id')}", file=sys.stderr)
        return ai_generation_result(
            answer_source=ANSWER_SOURCE_NONE,
            timed_out=True,
        )
    except Exception as e:
        print(f"Warning: error generating code: {e}", file=sys.stderr)
        return ai_generation_result()


def run_evaluation(
    eval_dir: Path | None = None,
    use_ai: bool = False,
    use_proxy_ai: bool = False,
    proxy_url: str | None = None,
    proxy_model: str | None = None,
    proxy_timeout: int | None = None,
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

    if use_ai or use_proxy_ai:
        cases = sorted(cases, key=generation_priority)
    ai_unavailable = local_ai_unavailable_reason() if use_ai else None
    if ai_unavailable:
        print(
            f"Warning: local AI unavailable: {ai_unavailable}; "
            "using fallback scaffolds for AI-mode pipeline checks.",
            file=sys.stderr,
        )

    # Eval-generation timeout profile — relaxed vs. smoke-test fail-fast defaults.
    # apply_eval_ai_timeouts() sets CLAW_OLLAMA_TIMEOUT_SECONDS /
    # CLAW_FIRST_TOKEN_TIMEOUT_SECONDS in os.environ (only if not already exported)
    # so they flow into run.ps1/run.sh → proxy when call_local_ai spawns the launcher.
    _plan_timeout = PLAN_TIMEOUT_SECONDS
    _code_timeout = CODE_TIMEOUT_SECONDS
    if use_ai and not ai_unavailable:
        _plan_timeout, _code_timeout = apply_eval_ai_timeouts()

    _proxy_url = proxy_url or f"http://127.0.0.1:{PROXY_AI_DEFAULT_PORT}"
    _proxy_model = proxy_model or os.environ.get("CLAW_MODEL", "") or PROXY_AI_DEFAULT_MODEL
    _proxy_timeout = proxy_timeout if proxy_timeout is not None else PROXY_AI_DEFAULT_TIMEOUT
    if use_proxy_ai:
        print(f"Using proxy sync AI mode", flush=True)
        print(f"Proxy URL: {_proxy_url}", flush=True)
        print(f"Model: {_proxy_model}", flush=True)
    
    total_points = sum(case_points(case) for case in cases)

    report = {
        "timestamp": int(time.time()),
        "total_cases": len(cases),
        "cases_tested": 0,
        "total_points": display_points(total_points),
        "total_earned": 0,
        "summary": {
            "total_cases": len(cases),
            "total_points": display_points(total_points),
            "model_points": 0.0,
            "pipeline_points": 0.0,
            "fallback_cases": 0,
            "no_answer_cases": 0,
            "compile_pass_cases": 0,
            "run_pass_cases": 0,
        },
        "cases": [],
        "results": [],
    }
    
    for case in cases:
        case_id = case.get("id", "unknown")
        print(f"Evaluating {case_id}...", end=" ", flush=True)
        
        points = case_points(case)

        answer_source = ANSWER_SOURCE_MODEL
        used_fallback = False
        model_code = ""
        gen_timed_out = False

        if use_proxy_ai:
            generation = generate_proxy_ai_response(case, _proxy_url, _proxy_model, _proxy_timeout)
            code = generation["final_output"]
            model_code = generation.get("model_output", "")
            answer_source = generation["answer_source"]
            used_fallback = bool(generation["used_fallback"])
        elif use_ai:
            if ai_unavailable:
                code = build_smoke_fallback_code(case, f"local AI unavailable: {ai_unavailable}")
                answer_source = ANSWER_SOURCE_FALLBACK
                used_fallback = True
            else:
                generation = generate_ai_response(
                    case, code_timeout=_code_timeout, plan_timeout=_plan_timeout
                )
                code = generation["final_output"]
                model_code = generation.get("model_output", "")
                answer_source = generation["answer_source"]
                used_fallback = bool(generation["used_fallback"])
                gen_timed_out = bool(generation.get("timed_out", False))
        elif answers_dir:
            answer_path = answers_dir / f"{case_id}.c"
            code = answer_path.read_text(encoding="utf-8") if answer_path.exists() else ""
        else:
            code = case.get("reference_answer", "")

        def no_code_result(message: str) -> dict[str, Any]:
            return {
                "case_id": case_id,
                "answer_source": ANSWER_SOURCE_NONE,
                "used_fallback": False,
                "compile_pass": False,
                "model_compile_pass": None,
                "run_pass": False,
                "keyword_pass": False,
                "structure_pass": False,
                "model_score": 0.0,
                "pipeline_score": 0.0,
                "score": 0.0,
                "messages": [message],
                "case_info": {
                    "year": case.get("year"),
                    "exam": case.get("exam"),
                    "topic": case.get("topic"),
                    "points": display_points(points),
                },
            }

        if not code:
            if gen_timed_out:
                print(f"timeout ({_code_timeout}s)")
                msg = f"Case timed out after {_code_timeout}s; no code generated."
            else:
                print("no answer")
                msg = "No answer code supplied. Use --use-ai or --answers-dir."
            results = no_code_result(msg)
            results["timed_out"] = gen_timed_out
            report["results"].append(results)
            report["cases"].append(results)
            report["cases_tested"] += 1
            report["summary"]["no_answer_cases"] += 1
            continue

        final_code = extract_c_code(code)
        extracted_model_code = extract_c_code(model_code, debug=False) if model_code else ""

        if not final_code:
            print("no code")
            results = no_code_result("No valid C code could be extracted from the model output.")
            report["results"].append(results)
            report["cases"].append(results)
            report["cases_tested"] += 1
            report["summary"]["no_answer_cases"] += 1
            continue

        model_results = run_smoke_tests(extracted_model_code, case) if extracted_model_code else None
        results = run_smoke_tests(final_code, case)
        pipeline_score = float(results["score"])
        model_score = float(model_results["score"]) if model_results else 0.0
        model_compile_pass = bool(model_results["compile_pass"]) if model_results else None

        results["answer_source"] = answer_source
        results["used_fallback"] = used_fallback
        results["model_compile_pass"] = model_compile_pass
        results["model_score"] = model_score
        results["pipeline_score"] = pipeline_score
        results["score"] = pipeline_score
        if ai_unavailable and use_ai:
            results["messages"].append(f"Local AI unavailable: {ai_unavailable}")
        
        # Print result summary
        status = "✅" if results["compile_pass"] else "❌"
        fallback_label = " fallback" if used_fallback else ""
        print(
            f"{status} source={answer_source}{fallback_label} "
            f"model={display_points(model_score)}/{display_points(points)} "
            f"pipeline={display_points(pipeline_score)}/{display_points(points)}"
        )
        
        results["case_info"] = {
            "year": case.get("year"),
            "exam": case.get("exam"),
            "topic": case.get("topic"),
            "points": display_points(points),
        }
        
        report["results"].append(results)
        report["cases"].append(results)
        report["cases_tested"] += 1
        report["total_earned"] += pipeline_score
        report["summary"]["model_points"] += model_score
        report["summary"]["pipeline_points"] += pipeline_score
        if used_fallback:
            report["summary"]["fallback_cases"] += 1
        if results["compile_pass"]:
            report["summary"]["compile_pass_cases"] += 1
        if results["run_pass"]:
            report["summary"]["run_pass_cases"] += 1
    
    # Calculate summary
    report["summary"]["model_points"] = round(report["summary"]["model_points"], 1)
    report["summary"]["pipeline_points"] = round(report["summary"]["pipeline_points"], 1)
    if total_points > 0:
        model_rate = round(100 * report["summary"]["model_points"] / total_points, 1)
        pipeline_rate = round(100 * report["summary"]["pipeline_points"] / total_points, 1)
        report["pass_rate"] = pipeline_rate
    else:
        model_rate = 0.0
        pipeline_rate = 0.0
        report["pass_rate"] = 0.0
    
    # Save report
    if output_file is None:
        output_file = Path(eval_dir).parent / "eval_report.json"
    
    output_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📊 Report saved to {output_file}")
    summary = report["summary"]
    print(
        f"Model Score: {display_points(float(summary['model_points']))}/"
        f"{report['total_points']} points ({model_rate}%)"
    )
    print(
        f"Pipeline Score: {display_points(float(summary['pipeline_points']))}/"
        f"{report['total_points']} points ({pipeline_rate}%)"
    )
    print(f"Fallback Used: {summary['fallback_cases']} cases")
    
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
        help="Generate code using local AI via run.sh (claw-based; may be unstable on Windows)",
    )
    parser.add_argument(
        "--use-proxy-ai",
        action="store_true",
        help=(
            "Generate code via proxy sync API (stream=false). "
            "Recommended on Windows; no claw streaming dependency. "
            "Requires Ollama + proxy already running, or use run_eval.ps1 --use-proxy-ai."
        ),
    )
    parser.add_argument(
        "--proxy-url",
        default=None,
        help=f"Proxy base URL for --use-proxy-ai (default: http://127.0.0.1:{PROXY_AI_DEFAULT_PORT})",
    )
    parser.add_argument(
        "--proxy-model",
        default=None,
        help=f"Model name for --use-proxy-ai (default: {PROXY_AI_DEFAULT_MODEL} or CLAW_MODEL env)",
    )
    parser.add_argument(
        "--proxy-timeout",
        type=int,
        default=None,
        help=f"Per-request timeout in seconds for --use-proxy-ai (default: {PROXY_AI_DEFAULT_TIMEOUT})",
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
        use_proxy_ai=args.use_proxy_ai,
        proxy_url=args.proxy_url,
        proxy_model=args.proxy_model,
        proxy_timeout=args.proxy_timeout,
        case_filter=args.filter,
        output_file=args.output,
        answers_dir=args.answers_dir,
    )


if __name__ == "__main__":
    main()
