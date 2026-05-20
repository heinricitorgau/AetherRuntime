#!/usr/bin/env python3
"""Profile-based startup doctor for local AI research workflows."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from local_ai.shared.config_loader import (
    ConfigError,
    load_benchmark_profile,
    load_dataset_profile,
    load_model_profile,
    load_training_job,
)
from local_ai.shared.paths import (
    BENCHMARK_DIR,
    CONFIG_DIR,
    LOCAL_AI_ROOT,
    resolve_repo_path,
)
from local_ai.shared.report_utils import write_json_report, write_text_report


REPORT_DIR = LOCAL_AI_ROOT / "reports"
REPORT_JSON = REPORT_DIR / "doctor_report.json"
REPORT_MD = REPORT_DIR / "doctor_report.md"
DEFAULT_PROXY_URL = "http://127.0.0.1:8082"
MIN_PYTHON = (3, 12)
BENCHMARK_FULL_TIMEOUT = 300
BENCHMARK_FIRST_TOKEN_TIMEOUT = 90
FAIL_FAST_FULL_TIMEOUT = 180

WINDOWS_GCC_PATHS = [
    r"C:\msys64\ucrt64\bin\gcc.exe",
    r"C:\msys64\mingw64\bin\gcc.exe",
    r"C:\MinGW\bin\gcc.exe",
    r"C:\TDM-GCC-64\bin\gcc.exe",
    r"C:\Program Files\mingw-w64\bin\gcc.exe",
]


@dataclass
class Check:
    name: str
    status: str
    detail: str
    fix: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _check(name: str, status: str, detail: str, fix: str = "", **metadata: Any) -> Check:
    return Check(name=name, status=status, detail=detail, fix=fix, metadata=metadata)


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _find_compiler() -> str | None:
    for name in ("cc", "gcc", "clang"):
        found = shutil.which(name)
        if found:
            return found
    for raw_path in WINDOWS_GCC_PATHS:
        path = Path(raw_path)
        if path.exists():
            return str(path)
    return None


def _read_url_json(url: str, timeout: int = 3) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
        return json.loads(body), None
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code} {exc.reason}"
    except urllib.error.URLError as exc:
        return None, str(exc.reason)
    except TimeoutError:
        return None, "timeout"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    except Exception as exc:
        return None, str(exc)


def check_python() -> Check:
    version = sys.version_info
    text = f"{version.major}.{version.minor}.{version.micro} ({sys.executable})"
    if (version.major, version.minor) >= MIN_PYTHON:
        return _check("python_version", "PASS", text)
    return _check(
        "python_version",
        "FAIL",
        text,
        "Use Python 3.12+ or activate the project's .venv-sft environment.",
    )


def check_import(module: str, package_hint: str | None = None) -> Check:
    if _module_available(module):
        return _check(f"import_{module}", "PASS", f"{module} import available")
    package = package_hint or module
    return _check(
        f"import_{module}",
        "FAIL",
        f"{module} is not importable",
        f"Install/activate dependencies, e.g. pip install {package}.",
    )


def check_cuda() -> list[Check]:
    if not _module_available("torch"):
        return [
            _check(
                "cuda_available",
                "WARN",
                "torch not importable; CUDA check skipped",
                "Install/activate torch before training or direct LoRA evaluation.",
            )
        ]
    try:
        import torch  # type: ignore[import-not-found]

        available = bool(torch.cuda.is_available())
        if not available:
            return [
                _check(
                    "cuda_available",
                    "WARN",
                    "CUDA not available",
                    "Training can fall back to CPU but will be very slow; install CUDA-enabled torch if needed.",
                )
            ]
        props = torch.cuda.get_device_properties(0)
        vram_gb = round(props.total_memory / (1024**3), 2)
        return [
            _check("cuda_available", "PASS", "CUDA available"),
            _check(
                "gpu",
                "PASS",
                f"{torch.cuda.get_device_name(0)} ({vram_gb} GB VRAM)",
                gpu_name=torch.cuda.get_device_name(0),
                vram_gb=vram_gb,
            ),
        ]
    except Exception as exc:
        return [
            _check(
                "cuda_available",
                "WARN",
                f"CUDA check failed: {exc}",
                "Verify torch/CUDA installation.",
            )
        ]


def check_unwanted_packages() -> list[Check]:
    checks: list[Check] = []
    for module in ("datasets", "pyarrow"):
        if _module_available(module):
            checks.append(
                _check(
                    f"unwanted_{module}",
                    "WARN",
                    f"{module} is installed but not required by this local pipeline",
                    f"Remove it from this environment if it causes dependency drift: pip uninstall {module}",
                )
            )
        else:
            checks.append(
                _check(
                    f"unwanted_{module}",
                    "PASS",
                    f"{module} not installed",
                )
            )
    return checks


def check_compiler() -> Check:
    compiler = _find_compiler()
    if compiler:
        return _check("c_compiler", "PASS", compiler, compiler=compiler)
    return _check(
        "c_compiler",
        "FAIL",
        "No cc/gcc/clang found",
        "Install MSYS2 UCRT64 GCC or add gcc/cc/clang to PATH.",
    )


def check_ollama_binary() -> Check:
    bundled = LOCAL_AI_ROOT / "runtime" / "bin" / "ollama.exe"
    found = bundled if bundled.exists() else None
    if found is None:
        system = shutil.which("ollama")
        if system:
            found = Path(system)
    if found:
        return _check("ollama_binary", "PASS", str(found))
    return _check(
        "ollama_binary",
        "FAIL",
        "Ollama binary not found",
        "Run local_ai/prepare_bundle.ps1 or install Ollama.",
    )


def _proxy_url(args: argparse.Namespace) -> str:
    return args.proxy_url.rstrip("/")


def check_proxy(args: argparse.Namespace) -> list[Check]:
    base = _proxy_url(args)
    checks: list[Check] = []
    health, health_error = _read_url_json(f"{base}/health")
    if health_error:
        checks.append(
            _check(
                "proxy_health",
                "WARN",
                f"proxy health unavailable at {base}/health: {health_error}",
                "Start the runtime first: powershell -ExecutionPolicy Bypass -File .\\local_ai\\run.ps1",
            )
        )
    else:
        checks.append(_check("proxy_health", "PASS", f"{base}/health ok", response=health))

    config, config_error = _read_url_json(f"{base}/config")
    if config_error:
        checks.append(
            _check(
                "proxy_config",
                "WARN",
                f"proxy /config unavailable: {config_error}",
                "Start/restart the proxy if you need benchmark timeout validation.",
            )
        )
        return checks

    full_timeout = int(config.get("full_timeout", 0) or 0)
    first_token_timeout = int(config.get("first_token_timeout", 0) or 0)
    checks.append(
        _check(
            "proxy_config",
            "PASS",
            f"full_timeout={full_timeout}s first_token_timeout={first_token_timeout}s",
            response=config,
        )
    )
    if full_timeout < FAIL_FAST_FULL_TIMEOUT:
        checks.append(
            _check(
                "proxy_timeout",
                "FAIL",
                f"proxy full timeout too short: {full_timeout}s",
                'Set $env:CLAW_OLLAMA_TIMEOUT_SECONDS="300" and restart local_ai/run.ps1.',
            )
        )
    elif full_timeout < BENCHMARK_FULL_TIMEOUT or first_token_timeout < BENCHMARK_FIRST_TOKEN_TIMEOUT:
        checks.append(
            _check(
                "proxy_timeout",
                "WARN",
                (
                    f"benchmark timeout may be too short: full={full_timeout}s "
                    f"first_token={first_token_timeout}s"
                ),
                (
                    'Use full timeout >= 300s and first-token >= 90s; '
                    'set $env:CLAW_OLLAMA_TIMEOUT_SECONDS="300" and '
                    '$env:CLAW_FIRST_TOKEN_TIMEOUT_SECONDS="90".'
                ),
            )
        )
    else:
        checks.append(
            _check(
                "proxy_timeout",
                "PASS",
                f"benchmark timeout ok: full={full_timeout}s first_token={first_token_timeout}s",
            )
        )
    return checks


def _import_profile_checks(args: argparse.Namespace) -> list[Check]:
    checks: list[Check] = []
    selected_dataset_names: set[str] = set()

    if args.profile:
        try:
            profile = load_model_profile(args.profile)
            checks.append(
                _check(
                    "model_profile",
                    "PASS",
                    f"{args.profile}: {profile['hf_model']} / {profile['ollama_model']}",
                    profile=args.profile,
                )
            )
        except ConfigError as exc:
            checks.append(_check("model_profile", "FAIL", str(exc), "Fix local_ai/config/models.json."))

    if args.benchmark:
        try:
            profile = load_benchmark_profile(args.benchmark)
            selected_dataset_names.add(str(profile["dataset"]))
            checks.append(
                _check(
                    "benchmark_profile",
                    "PASS",
                    f"{args.benchmark}: model={profile['model']} dataset={profile['dataset']}",
                    profile=args.benchmark,
                )
            )
        except ConfigError as exc:
            checks.append(_check("benchmark_profile", "FAIL", str(exc), "Fix local_ai/config/benchmarks.json."))

    if args.training_job:
        try:
            job = load_training_job(args.training_job)
            selected_dataset_names.add(str(job["dataset"]))
            checks.append(
                _check(
                    "training_job",
                    "PASS",
                    f"{args.training_job}: model={job['model']} dataset={job['dataset']}",
                    profile=args.training_job,
                )
            )
        except ConfigError as exc:
            checks.append(_check("training_job", "FAIL", str(exc), "Fix local_ai/config/training_jobs.json."))

    checks.extend(check_dataset_paths(selected_dataset_names))
    return checks


def check_config_registry() -> Check:
    try:
        spec = importlib.util.spec_from_file_location(
            "validate_profiles", CONFIG_DIR / "validate_profiles.py"
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("could not load validate_profiles.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        report = module.validate_profiles()
        if report.get("success"):
            return _check(
                "config_registry",
                "PASS",
                f"profile registry valid ({report.get('issue_count', 0)} issues)",
                report=report,
            )
        messages = [issue.get("message", str(issue)) for issue in report.get("issues", [])]
        return _check(
            "config_registry",
            "FAIL",
            "; ".join(messages),
            "Run python local_ai/config/validate_profiles.py and fix reported config issues.",
            report=report,
        )
    except Exception as exc:
        return _check(
            "config_registry",
            "FAIL",
            f"config registry validation crashed: {exc}",
            "Fix local_ai/config/validate_profiles.py or malformed config JSON.",
        )


def check_dataset_paths(required_only: set[str] | None = None) -> list[Check]:
    datasets = _load_json(CONFIG_DIR / "datasets.json")
    checks: list[Check] = []
    selected = required_only or set(datasets)
    for name in sorted(selected):
        profile = datasets.get(name)
        if not isinstance(profile, dict):
            checks.append(
                _check(
                    f"dataset_path:{name}",
                    "FAIL",
                    f"dataset profile not found or invalid: {name}",
                    "Fix local_ai/config/datasets.json.",
                )
            )
            continue
        raw_path = profile.get("path")
        if not raw_path:
            checks.append(
                _check(
                    f"dataset_path:{name}",
                    "FAIL",
                    f"dataset profile has no path: {name}",
                    "Add a path field in local_ai/config/datasets.json.",
                )
            )
            continue
        resolved = resolve_repo_path(raw_path)
        if resolved.exists():
            checks.append(_check(f"dataset_path:{name}", "PASS", str(resolved)))
        else:
            checks.append(
                _check(
                    f"dataset_path:{name}",
                    "FAIL",
                    f"missing dataset path: {resolved}",
                    "Regenerate the dataset or update local_ai/config/datasets.json.",
                )
            )
    return checks


def check_golden_baseline() -> Check:
    golden = BENCHMARK_DIR / "golden" / "golden_baseline.json"
    if not golden.exists():
        return _check(
            "golden_baseline",
            "WARN",
            f"golden baseline not found: {golden}",
            "Lock a baseline with local_ai/benchmark/lock_golden_baseline.py when ready.",
        )
    data = _load_json(golden)
    return _check(
        "golden_baseline",
        "PASS",
        f"{golden} ref={data.get('run_id', '?')} tasks={data.get('task_count', '?')}",
        path=str(golden),
    )


def check_sft_readiness(training_job_selected: bool) -> Check:
    script = LOCAL_AI_ROOT / "training_quality" / "sft_readiness_check.py"
    if not script.exists():
        return _check(
            "sft_readiness",
            "WARN",
            f"readiness script not found: {script}",
            "Restore local_ai/training_quality/sft_readiness_check.py.",
        )
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
    except Exception as exc:
        return _check(
            "sft_readiness",
            "WARN",
            f"SFT readiness check could not run: {exc}",
            "Run python local_ai/training_quality/sft_readiness_check.py manually.",
        )

    report_path = LOCAL_AI_ROOT / "training_quality" / "reports" / "sft_readiness_report.json"
    report = _load_json(report_path)
    ready = bool(report.get("ready_for_sft", False))
    stdout = result.stdout.strip().splitlines()
    tail = " | ".join(stdout[-4:]) if stdout else f"exit={result.returncode}"
    if ready:
        return _check("sft_readiness", "PASS", tail, report=str(report_path))
    status = "FAIL" if training_job_selected else "WARN"
    return _check(
        "sft_readiness",
        status,
        tail,
        "Fix failing SFT readiness sections before LoRA training.",
        report=str(report_path),
    )


def _status_rank(status: str) -> int:
    return {"PASS": 0, "WARN": 1, "FAIL": 2}.get(status, 2)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    checks: list[Check] = []
    checks.append(check_python())
    checks.append(check_import("torch", "torch"))
    checks.extend(check_cuda())
    checks.append(check_import("transformers", "transformers"))
    checks.append(check_import("peft", "peft"))
    checks.extend(check_unwanted_packages())
    checks.append(check_compiler())
    checks.append(check_ollama_binary())
    checks.extend(check_proxy(args))
    checks.append(check_config_registry())
    checks.append(check_golden_baseline())
    checks.extend(_import_profile_checks(args))
    checks.append(check_sft_readiness(training_job_selected=bool(args.training_job)))

    status = max((c.status for c in checks), key=_status_rank)
    return {
        "timestamp": _now(),
        "status": status,
        "success": status != "FAIL",
        "args": {
            "profile": args.profile,
            "benchmark": args.benchmark,
            "training_job": args.training_job,
            "proxy_url": args.proxy_url,
        },
        "summary": {
            "pass": sum(1 for c in checks if c.status == "PASS"),
            "warn": sum(1 for c in checks if c.status == "WARN"),
            "fail": sum(1 for c in checks if c.status == "FAIL"),
        },
        "checks": [
            {
                "name": c.name,
                "status": c.status,
                "detail": c.detail,
                "fix": c.fix,
                "metadata": c.metadata,
            }
            for c in checks
        ],
    }


def _markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Local AI Doctor Report")
    lines.append("")
    lines.append(f"Generated: `{report['timestamp']}`")
    lines.append(f"Status: **{report['status']}**")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| PASS | WARN | FAIL |")
    lines.append("|-----:|-----:|-----:|")
    summary = report["summary"]
    lines.append(f"| {summary['pass']} | {summary['warn']} | {summary['fail']} |")
    lines.append("")
    lines.append("## Checks")
    lines.append("")
    lines.append("| Status | Check | Detail | Fix |")
    lines.append("|:------:|-------|--------|-----|")
    for check in report["checks"]:
        detail = str(check["detail"]).replace("|", "\\|")
        fix = str(check.get("fix") or "").replace("|", "\\|")
        lines.append(f"| {check['status']} | `{check['name']}` | {detail} | {fix} |")
    lines.append("")
    return "\n".join(lines)


def print_report(report: dict[str, Any]) -> None:
    print(f"Local AI doctor: {report['status']}")
    for check in report["checks"]:
        print(f"  {check['status']:<4}  {check['name']}: {check['detail']}")
        if check.get("fix"):
            print(f"        fix: {check['fix']}")
    print(f"\nReport: {REPORT_MD}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check local AI environment health")
    parser.add_argument("--profile", help="Model profile name from config/models.json")
    parser.add_argument("--benchmark", help="Benchmark profile name from config/benchmarks.json")
    parser.add_argument("--training-job", help="Training job name from config/training_jobs.json")
    parser.add_argument(
        "--proxy-url",
        default=DEFAULT_PROXY_URL,
        help=f"Proxy base URL (default: {DEFAULT_PROXY_URL})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args)
    write_json_report(REPORT_JSON, report)
    write_text_report(REPORT_MD, _markdown(report))
    print_report(report)
    raise SystemExit(0 if report["status"] != "FAIL" else 1)


if __name__ == "__main__":
    main()
