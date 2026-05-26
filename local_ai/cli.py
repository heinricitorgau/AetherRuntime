#!/usr/bin/env python3
"""Unified local_ai developer CLI.

This is a thin subprocess wrapper around existing scripts. It intentionally does
not reimplement benchmark, routing, governance, release, or validation logic.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent


def _script(*parts: str) -> str:
    return str(_HERE.joinpath(*parts))


def _fmt_cmd(cmd: list[str]) -> str:
    return " ".join(f'"{part}"' if " " in part else part for part in cmd)


def _run_commands(commands: list[list[str]], dry_run: bool) -> int:
    exit_code = 0
    for cmd in commands:
        print(f"[local-ai] $ {_fmt_cmd(cmd)}", flush=True)
        if dry_run:
            continue
        completed = subprocess.run(cmd, cwd=str(_REPO_ROOT), check=False)
        if completed.returncode != 0 and exit_code == 0:
            exit_code = completed.returncode
    return 0 if dry_run else exit_code


def _base_cmd(script_path: str) -> list[str]:
    return [sys.executable, script_path]


def _cmd_smoke(args: argparse.Namespace) -> int:
    return _run_commands([_base_cmd(_script("system", "smoke_test.py"))], args.dry_run)


def _cmd_doctor(args: argparse.Namespace) -> int:
    cmd = _base_cmd(_script("doctor.py"))
    if args.benchmark:
        cmd += ["--benchmark", args.benchmark]
    if args.profile:
        cmd += ["--profile", args.profile]
    if args.training_job:
        cmd += ["--training-job", args.training_job]
    return _run_commands([cmd], args.dry_run)


def _cmd_benchmark(args: argparse.Namespace) -> int:
    cmd = _base_cmd(_script("benchmark", "run_baseline.py"))
    if args.benchmark:
        cmd += ["--benchmark", args.benchmark]
    if args.run_id:
        cmd += ["--run-id", args.run_id]
    if args.limit_filter:
        cmd += ["--filter", *args.limit_filter]
    if args.strict_code_only:
        cmd.append("--strict-code-only")
    return _run_commands([cmd], args.dry_run)


def _cmd_routing(args: argparse.Namespace) -> int:
    cmd = _base_cmd(_script("routing", "evaluate_routing.py"))
    cmd += ["--benchmark", args.benchmark]
    return _run_commands([cmd], args.dry_run)


def _cmd_adapters(args: argparse.Namespace) -> int:
    cmd = _base_cmd(_script("sft", "list_adapters.py"))
    if args.status:
        cmd += ["--status", args.status]
    if args.format:
        cmd += ["--format", args.format]
    return _run_commands([cmd], args.dry_run)


def _cmd_system(args: argparse.Namespace) -> int:
    commands = [
        _base_cmd(_script("system", "system_index.py")),
        _base_cmd(_script("system", "build_report_index.py")),
        _base_cmd(_script("system", "build_architecture_map.py")),
    ]
    return _run_commands(commands, args.dry_run)


def _cmd_snapshot(args: argparse.Namespace) -> int:
    cmd = _base_cmd(_script("release", "snapshot.py")) + ["--name", args.name]
    return _run_commands([cmd], args.dry_run)


def _cmd_validate_config(args: argparse.Namespace) -> int:
    return _run_commands([_base_cmd(_script("config", "validate_profiles.py"))], args.dry_run)


def _add_dry_run(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dry-run", action="store_true", help="Print command(s) without executing")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified local_ai developer CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    smoke = sub.add_parser("smoke", help="Run infrastructure smoke test")
    _add_dry_run(smoke)
    smoke.set_defaults(func=_cmd_smoke)

    doctor = sub.add_parser("doctor", help="Run local_ai doctor")
    doctor.add_argument("--benchmark")
    doctor.add_argument("--profile")
    doctor.add_argument("--training-job")
    _add_dry_run(doctor)
    doctor.set_defaults(func=_cmd_doctor)

    benchmark = sub.add_parser("benchmark", help="Run benchmark baseline")
    benchmark.add_argument("--benchmark", required=True)
    benchmark.add_argument("--run-id")
    benchmark.add_argument("--filter", dest="limit_filter", nargs="*")
    benchmark.add_argument("--strict-code-only", action="store_true")
    _add_dry_run(benchmark)
    benchmark.set_defaults(func=_cmd_benchmark)

    routing = sub.add_parser("routing", help="Evaluate routing plan")
    routing.add_argument("--benchmark", required=True)
    _add_dry_run(routing)
    routing.set_defaults(func=_cmd_routing)

    adapters = sub.add_parser("adapters", help="List governed adapters")
    adapters.add_argument("--status", choices=["promote", "safe_no_change", "ablation_only", "reject"])
    adapters.add_argument("--format", choices=["table", "markdown", "json"], default=None)
    _add_dry_run(adapters)
    adapters.set_defaults(func=_cmd_adapters)

    system = sub.add_parser("system", help="Rebuild system/report/architecture indexes")
    _add_dry_run(system)
    system.set_defaults(func=_cmd_system)

    snapshot = sub.add_parser("snapshot", help="Create release snapshot")
    snapshot.add_argument("--name", required=True)
    _add_dry_run(snapshot)
    snapshot.set_defaults(func=_cmd_snapshot)

    validate = sub.add_parser("validate-config", help="Validate config profiles")
    _add_dry_run(validate)
    validate.set_defaults(func=_cmd_validate_config)

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
