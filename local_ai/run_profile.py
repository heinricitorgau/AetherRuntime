#!/usr/bin/env python3
"""Unified profile runner for common local_ai workflows."""
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


LOCAL_AI_ROOT = Path(__file__).resolve().parent


def _script(*parts: str) -> Path:
    return LOCAL_AI_ROOT.joinpath(*parts)


def _quote_command(cmd: list[str]) -> str:
    if sys.platform == "win32":
        return subprocess.list2cmdline(cmd)
    return " ".join(shlex.quote(part) for part in cmd)


def _run(cmd: list[str], dry_run_only: bool = False) -> int:
    print(f"[run_profile] command: {_quote_command(cmd)}", flush=True)
    if dry_run_only:
        print("[run_profile] dry-run: command not executed", flush=True)
        return 0
    completed = subprocess.run(cmd)
    return int(completed.returncode)


def _add_common_passthrough(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "extra_args",
        nargs=argparse.REMAINDER,
        help="Extra args passed to the underlying script after --",
    )


def _add_dry_run(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the delegated command without executing it",
    )


def _clean_extra(extra_args: list[str]) -> list[str]:
    if extra_args and extra_args[0] == "--":
        return extra_args[1:]
    return extra_args


def build_doctor_cmd(args: argparse.Namespace) -> tuple[list[str], bool]:
    cmd = [sys.executable, str(_script("doctor.py"))]
    if args.profile:
        cmd.extend(["--profile", args.profile])
    if args.benchmark:
        cmd.extend(["--benchmark", args.benchmark])
    if args.training_job:
        cmd.extend(["--training-job", args.training_job])
    if args.proxy_url:
        cmd.extend(["--proxy-url", args.proxy_url])
    cmd.extend(_clean_extra(args.extra_args))
    return cmd, bool(args.dry_run)


def build_benchmark_cmd(args: argparse.Namespace) -> tuple[list[str], bool]:
    cmd = [sys.executable, str(_script("benchmark", "run_baseline.py"))]
    if args.benchmark:
        cmd.extend(["--benchmark", args.benchmark])
    if args.verbose:
        cmd.append("--verbose")
    cmd.extend(_clean_extra(args.extra_args))
    return cmd, bool(args.dry_run)


def build_train_cmd(args: argparse.Namespace) -> tuple[list[str], bool]:
    cmd = [sys.executable, str(_script("sft", "train_lora.py"))]
    if args.job:
        cmd.extend(["--job", args.job])
    if args.verbose:
        cmd.append("--verbose")
    cmd.extend(_clean_extra(args.extra_args))
    return cmd, bool(args.dry_run)


def build_compare_lora_cmd(args: argparse.Namespace) -> tuple[list[str], bool]:
    cmd = [sys.executable, str(_script("sft", "benchmark_lora.py"))]
    if args.benchmark:
        cmd.extend(["--benchmark", args.benchmark])
    cmd.extend(["--adapter", args.adapter])
    if args.limit is not None:
        cmd.extend(["--limit", str(args.limit)])
    if args.verbose:
        cmd.append("--verbose")
    cmd.extend(_clean_extra(args.extra_args))
    return cmd, bool(args.dry_run)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run common local_ai workflows through profile-aware subcommands"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Run startup environment doctor")
    doctor.add_argument("--profile")
    doctor.add_argument("--benchmark")
    doctor.add_argument("--training-job")
    doctor.add_argument("--proxy-url")
    _add_dry_run(doctor)
    _add_common_passthrough(doctor)

    benchmark = sub.add_parser("benchmark", help="Run configured benchmark")
    benchmark.add_argument("--benchmark", required=True)
    _add_dry_run(benchmark)
    benchmark.add_argument("--verbose", action="store_true")
    _add_common_passthrough(benchmark)

    train = sub.add_parser("train", help="Run configured LoRA training job")
    train.add_argument("--job", required=True)
    _add_dry_run(train)
    train.add_argument("--verbose", action="store_true")
    _add_common_passthrough(train)

    compare = sub.add_parser("compare-lora", help="Compare LoRA adapter to base")
    compare.add_argument("--benchmark", required=True)
    compare.add_argument("--adapter", required=True)
    compare.add_argument("--limit", type=int)
    _add_dry_run(compare)
    compare.add_argument("--verbose", action="store_true")
    _add_common_passthrough(compare)

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    builders = {
        "doctor": build_doctor_cmd,
        "benchmark": build_benchmark_cmd,
        "train": build_train_cmd,
        "compare-lora": build_compare_lora_cmd,
    }
    cmd, dry_run_only = builders[args.command](args)
    raise SystemExit(_run(cmd, dry_run_only=dry_run_only))


if __name__ == "__main__":
    main()
