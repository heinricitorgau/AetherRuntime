#!/usr/bin/env python3
"""Unified local_ai developer CLI.

This is a thin subprocess wrapper around existing scripts. It intentionally does
not reimplement benchmark, routing, governance, release, or validation logic.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from local_ai.shared.progress import format_elapsed, progress_bar, separator, symbols


def _script(*parts: str) -> str:
    return str(_HERE.joinpath(*parts))


def _fmt_cmd(cmd: list[str]) -> str:
    return " ".join(f'"{part}"' if " " in part else part for part in cmd)


def _run_commands(commands: list[list[str]], dry_run: bool) -> int:
    started = time.monotonic()
    exit_code = 0
    total = len(commands)
    print(separator())
    print("Local AI CLI")
    print(separator())
    print(f"Commands: {total}")
    print(progress_bar(0, total))
    print(separator(), flush=True)
    for index, cmd in enumerate(commands, 1):
        cmd_started = time.monotonic()
        print()
        print(f"Command {index} / {total}")
        print(progress_bar(index - 1, total))
        print(f"[local-ai] $ {_fmt_cmd(cmd)}", flush=True)
        if dry_run:
            print(f"{symbols()['ok']} Command {index} planned")
            continue
        completed = subprocess.run(cmd, cwd=str(_REPO_ROOT), check=False)
        if completed.returncode != 0 and exit_code == 0:
            exit_code = completed.returncode
        status = "PASS" if completed.returncode == 0 else "FAIL"
        mark = symbols()["ok"] if completed.returncode == 0 else symbols()["fail"]
        print(f"{mark} Command {index} {status} elapsed={format_elapsed(time.monotonic() - cmd_started)}")
        print(progress_bar(index, total), flush=True)
    final_status = "DRY-RUN" if dry_run else ("PASS" if exit_code == 0 else "FAIL")
    print()
    print(separator())
    print("CLI Summary")
    print(separator())
    print(f"Status: {final_status}")
    print(f"Commands: {total} / {total}")
    print(f"Elapsed Time: {format_elapsed(time.monotonic() - started)}")
    print(separator(), flush=True)
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


def _cmd_regression(args: argparse.Namespace) -> int:
    cmd = _base_cmd(_script("benchmark", "detect_regression.py"))
    if args.self_test:
        cmd.append("--self-test")
    else:
        if args.base:
            cmd += ["--base", args.base]
        if args.new:
            cmd += ["--new", args.new]
        if args.policy:
            cmd += ["--policy", args.policy]
    return _run_commands([cmd], args.dry_run)


def _cmd_trend(args: argparse.Namespace) -> int:
    cmd = _base_cmd(_script("benchmark", "benchmark_trend.py"))
    if args.self_test:
        cmd.append("--self-test")
    return _run_commands([cmd], args.dry_run)


def _cmd_governance(args: argparse.Namespace) -> int:
    cmd = _base_cmd(_script("system", "governance_status.py"))
    if args.self_test:
        cmd.append("--self-test")
    return _run_commands([cmd], args.dry_run)


def _cmd_reliability(args: argparse.Namespace) -> int:
    cmd = _base_cmd(_script("benchmark", "eval_reliability.py"))
    if args.self_test:
        cmd.append("--self-test")
    return _run_commands([cmd], args.dry_run)


def _cmd_profiles(args: argparse.Namespace) -> int:
    cmd = _base_cmd(_script("config", "govern_profiles.py"))
    if args.self_test:
        cmd.append("--self-test")
    return _run_commands([cmd], args.dry_run)


def _cmd_goldens(args: argparse.Namespace) -> int:
    cmd = _base_cmd(_script("goldens", "promote_goldens.py"))
    if args.self_test:
        cmd.append("--self-test")
    return _run_commands([cmd], args.dry_run)


def _cmd_route_audit(args: argparse.Namespace) -> int:
    cmd = _base_cmd(_script("routing", "audit_routing.py"))
    if args.self_test:
        cmd.append("--self-test")
    return _run_commands([cmd], args.dry_run)


def _cmd_deploy(args: argparse.Namespace) -> int:
    cmd = _base_cmd(_script("release", "deploy_gate.py"))
    if args.self_test:
        cmd.append("--self-test")
    return _run_commands([cmd], args.dry_run)


def _cmd_corpus(args: argparse.Namespace) -> int:
    commands = [
        _base_cmd(_script("corpus", "build_index.py")),
        _base_cmd(_script("corpus", "validate_corpus.py")),
        _base_cmd(_script("corpus", "corpus_dashboard.py")),
    ]
    return _run_commands(commands, args.dry_run)


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

    regression = sub.add_parser("regression", help="Detect benchmark regression between runs")
    regression.add_argument("--base", help="Reference run ID (default: auto-resolve previous run)")
    regression.add_argument("--new", help="New run ID to check")
    regression.add_argument("--policy", help="Optional JSON file overriding regression thresholds")
    regression.add_argument("--self-test", action="store_true", help="Model-free verdict self-test")
    _add_dry_run(regression)
    regression.set_defaults(func=_cmd_regression)

    trend = sub.add_parser("trend", help="Benchmark trend + auto-regression over run history")
    trend.add_argument("--self-test", action="store_true", help="Model-free trend-logic self-test")
    _add_dry_run(trend)
    trend.set_defaults(func=_cmd_trend)

    governance = sub.add_parser("governance", help="Unified cross-layer governance status")
    governance.add_argument("--self-test", action="store_true", help="Read-only aggregation self-test")
    _add_dry_run(governance)
    governance.set_defaults(func=_cmd_governance)

    reliability = sub.add_parser("reliability", help="Evaluation reliability / reproducibility audit")
    reliability.add_argument("--self-test", action="store_true", help="Model-free reliability self-test")
    _add_dry_run(reliability)
    reliability.set_defaults(func=_cmd_reliability)

    profiles = sub.add_parser("profiles", help="Prompt/profile governance gate")
    profiles.add_argument("--self-test", action="store_true", help="Read-only profile validation self-test")
    _add_dry_run(profiles)
    profiles.set_defaults(func=_cmd_profiles)

    goldens = sub.add_parser("goldens", help="Validate and promote human-verified goldens")
    goldens.add_argument("--self-test", action="store_true", help="Field-validation self-test")
    _add_dry_run(goldens)
    goldens.set_defaults(func=_cmd_goldens)

    route_audit = sub.add_parser("route-audit", help="Routing governance audit")
    route_audit.add_argument("--self-test", action="store_true", help="Read-only routing audit self-test")
    _add_dry_run(route_audit)
    route_audit.set_defaults(func=_cmd_route_audit)

    deploy = sub.add_parser("deploy", help="Deployment readiness gate")
    deploy.add_argument("--self-test", action="store_true", help="Read-only readiness self-test")
    _add_dry_run(deploy)
    deploy.set_defaults(func=_cmd_deploy)

    corpus = sub.add_parser("corpus", help="Rebuild corpus index, validation, and dashboard")
    _add_dry_run(corpus)
    corpus.set_defaults(func=_cmd_corpus)

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
