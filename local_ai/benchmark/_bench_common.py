"""Shared utilities for the benchmark pipeline.

Provides:
  - call_proxy()     HTTP request to the local proxy
  - extract_c()      extract C code from model response
  - check_truncation() detect truncated output
  - check_structure()  lightweight structural checks
  - check_keywords()   required keyword presence
  - check_output_tokens() runtime output matching
  - compile_code()    compile a C source file
  - run_exe()         execute a compiled binary
  - compute_score()   scoring formula (same weights as training_quality)
  - find_compiler()   locate gcc/clang on PATH or known Windows paths
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ───────────────────────────────────────────────────────────────────

BENCHMARK_ROOT = Path(__file__).resolve().parent
LOCAL_AI_ROOT  = BENCHMARK_ROOT.parent
REPORTS_DIR    = BENCHMARK_ROOT / "reports"
PROMPTS_DIR    = BENCHMARK_ROOT / "prompts"
GOLDEN_DIR     = BENCHMARK_ROOT / "golden"

# Make training_quality importable for static_analysis
_TQ_DIR = str(LOCAL_AI_ROOT / "training_quality")
if _TQ_DIR not in sys.path:
    sys.path.insert(0, _TQ_DIR)

try:
    from static_analysis import analyse as _static_analyse  # type: ignore[import]
    _HAS_STATIC_ANALYSIS = True
except ImportError:
    _static_analyse = None  # type: ignore[assignment]
    _HAS_STATIC_ANALYSIS = False


def semantic_check(code: str) -> dict:
    """Run static analysis on C code.  Never raises; returns a safe dict on failure."""
    if not _HAS_STATIC_ANALYSIS or _static_analyse is None:
        return {
            "passed": True, "warnings": [], "errors": [], "risk_score": 0.0,
            "note": "[warn] static_analysis not available; semantic check skipped",
        }
    try:
        result = _static_analyse(code)
        return {
            "passed":     len(result.errors) == 0,
            "warnings":   result.warnings,
            "errors":     result.errors,
            "risk_score": result.risk_score,
        }
    except Exception as exc:
        return {
            "passed": True, "warnings": [], "errors": [], "risk_score": 0.0,
            "note": f"[warn] static_analysis error: {exc}",
        }


# ── Time ────────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


# ── Proxy ───────────────────────────────────────────────────────────────────

def call_proxy(
    proxy_url: str,
    model: str,
    system: str,
    user: str,
    max_tokens: int,
    timeout: int,
    temperature: float = 0.0,
    skip_repair: bool = False,
) -> tuple[str, str | None, int]:
    """Return (text, error_message, latency_ms). error_message is None on success."""
    payload = json.dumps({
        "model":       model,
        "max_tokens":  max_tokens,
        "temperature": temperature,
        "system":      system,
        "messages":    [{"role": "user", "content": user}],
        "claw_skip_repair": skip_repair,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{proxy_url.rstrip('/')}/v1/messages",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        latency_ms = int((time.monotonic() - t0) * 1000)
        parts = body.get("content", [])
        text = "".join(b.get("text", "") for b in parts if b.get("type") == "text")
        return text.strip(), None, latency_ms
    except urllib.error.HTTPError as exc:
        return "", f"proxy HTTP error: HTTP {exc.code} {exc.reason}", 0
    except urllib.error.URLError as exc:
        return "", f"proxy unreachable: {exc}", 0
    except Exception as exc:
        return "", str(exc)[:200], 0


# ── Code extraction ─────────────────────────────────────────────────────────

_FENCE_RE = re.compile(r"```(?:c|C)?\s*\n(.*?)```", re.DOTALL)


def extract_c(text: str) -> tuple[str, str]:
    """Return (code, method). method: 'fence' | 'heuristic' | 'none'."""
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip(), "fence"
    if "#include" in text and "int main" in text:
        start = text.find("#include")
        snippet = text[start:]
        depth, end = 0, -1
        for i, ch in enumerate(snippet):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and i > 0:
                    end = i + 1  # record but keep scanning for later functions/main
        if end > 0:
            return snippet[:end].strip(), "heuristic"
    return text.strip(), "none"


# ── Structural checks ───────────────────────────────────────────────────────

def check_structure(code: str) -> dict:
    """Lightweight structural validation (subset of structure_validator)."""
    has_include = "#include" in code
    has_main    = bool(re.search(r"\bint\s+main\s*\(", code))
    opens       = code.count("{")
    closes      = code.count("}")
    balanced    = opens == closes and opens > 0
    complete    = code.rstrip().endswith("}")

    checks = [has_include, has_main, balanced, complete]
    score  = sum(checks) / len(checks)

    issues: list[str] = []
    if not has_include: issues.append("missing #include")
    if not has_main:    issues.append("missing int main")
    if not balanced:    issues.append(f"unbalanced braces ({opens} open, {closes} close)")
    if not complete:    issues.append("code appears truncated (does not end with '}')")

    return {
        "ok":      score >= 0.75,
        "score":   round(score, 3),
        "issues":  issues,
        "signals": {
            "has_include": has_include,
            "has_main":    has_main,
            "balanced":    balanced,
            "complete":    complete,
        },
    }


def is_truncated(code: str) -> bool:
    """True if the code looks cut off."""
    stripped = code.rstrip()
    if not stripped.endswith("}"):
        return True
    if code.count("{") != code.count("}"):
        return True
    return False


# ── Keyword check ───────────────────────────────────────────────────────────

def check_keywords(code: str, keywords: list[str]) -> dict:
    lower   = code.lower()
    found   = [k for k in keywords if str(k).lower() in lower]
    missing = [k for k in keywords if str(k).lower() not in lower]
    score   = len(found) / len(keywords) if keywords else 1.0
    return {"found": found, "missing": missing, "score": round(score, 3)}


# ── Output token check ──────────────────────────────────────────────────────

def check_output_tokens(output: str, expected_tokens: list[str]) -> dict:
    lower   = output.lower()
    found   = [str(t) for t in expected_tokens if str(t).lower() in lower]
    missing = [str(t) for t in expected_tokens if str(t).lower() not in lower]
    score   = len(found) / len(expected_tokens) if expected_tokens else 1.0
    return {"found": found, "missing": missing, "match_ratio": round(score, 3)}


# ── Compiler ────────────────────────────────────────────────────────────────

_WINDOWS_GCC_PATHS = [
    r"C:\msys64\ucrt64\bin\gcc.exe",
    r"C:\msys64\mingw64\bin\gcc.exe",
    r"C:\MinGW\bin\gcc.exe",
    r"C:\TDM-GCC-64\bin\gcc.exe",
    r"C:\Program Files\mingw-w64\bin\gcc.exe",
]

_MSYS2_PATH_PREFIXES = [
    r"C:\msys64\ucrt64\bin",
    r"C:\msys64\usr\bin",
    r"C:\msys64\mingw64\bin",
]


def find_compiler() -> str | None:
    for name in ("cc", "gcc", "clang"):
        p = shutil.which(name)
        if p:
            return p
    for path in _WINDOWS_GCC_PATHS:
        if Path(path).exists():
            return path
    return None


def _compiler_env(compiler: str) -> dict:
    env = os.environ.copy()
    if "msys64" in compiler.lower():
        extra = os.pathsep.join(p for p in _MSYS2_PATH_PREFIXES if Path(p).exists())
        if extra:
            env["PATH"] = extra + os.pathsep + env.get("PATH", "")
    return env


def compile_code(
    code: str,
    case_id: str,
    work_dir: Path,
    compiler: str,
) -> dict:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", case_id)
    src = work_dir / f"{safe_id}.c"
    exe = work_dir / (safe_id + (".exe" if sys.platform == "win32" else ""))
    src.write_text(code, encoding="utf-8")
    try:
        result = subprocess.run(
            [compiler, "-std=c99", "-Wall", "-o", str(exe), str(src), "-lm"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=15,
            env=_compiler_env(compiler),
        )
        ok     = result.returncode == 0
        stderr = (result.stderr or "").strip()
        errors   = [l for l in stderr.splitlines() if "error:" in l]
        warnings = [l for l in stderr.splitlines() if "warning:" in l]
        return {
            "ok":       ok,
            "message":  "ok" if ok else f"compile error ({len(errors)} errors)",
            "errors":   errors[:10],
            "warnings": warnings[:10],
            "exe":      str(exe) if ok else None,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": "compile timeout", "errors": [], "warnings": [], "exe": None}
    except Exception as exc:
        return {"ok": False, "message": str(exc)[:200], "errors": [], "warnings": [], "exe": None}


def run_exe(exe: str, sample_input: str, timeout: int = 8) -> dict:
    stdin_data = sample_input.replace("\\n", "\n")
    if not stdin_data.endswith("\n"):
        stdin_data += "\n"
    try:
        result = subprocess.run(
            [exe],
            input=stdin_data,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout,
        )
        output = (result.stdout + result.stderr).strip()
        return {"ok": result.returncode == 0, "output": output[:2000], "timed_out": False}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": f"timeout after {timeout}s", "timed_out": True}
    except Exception as exc:
        return {"ok": False, "output": str(exc)[:200], "timed_out": False}


# ── Score ────────────────────────────────────────────────────────────────────
# Weights match training_quality/score_records.py for cross-run comparability.

_WEIGHTS = {"structure": 15, "keyword": 15, "compile": 40, "runtime": 30}


def compute_score(
    structure_score: float,  # 0.0–1.0
    keyword_score:   float,  # 0.0–1.0
    compile_ok:      bool,
    runtime_ratio:   float,  # 0.0–1.0
) -> dict:
    pts_structure = round(_WEIGHTS["structure"] * structure_score)
    pts_keyword   = round(_WEIGHTS["keyword"]   * keyword_score)
    pts_compile   = _WEIGHTS["compile"] if compile_ok else 0
    pts_runtime   = round(_WEIGHTS["runtime"]   * runtime_ratio)
    total = pts_structure + pts_keyword + pts_compile + pts_runtime
    return {
        "total":     total,
        "breakdown": {
            "structure": pts_structure,
            "keyword":   pts_keyword,
            "compile":   pts_compile,
            "runtime":   pts_runtime,
        },
    }


# ── I/O helpers ─────────────────────────────────────────────────────────────

def write_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_prompt_file(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()
