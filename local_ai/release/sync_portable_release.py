#!/usr/bin/env python3
"""Synchronize the portable USB release without copying development garbage.

This script is intentionally conservative:
- it builds a scan report before applying changes;
- it syncs only approved source-controlled/release surfaces;
- it preserves the existing portable runtime bundle;
- it validates the portable tree before creating a release manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TARGET = ROOT / "usb_export" / "research-claw-code-portable-20260518"

RELEASE_NAME = "portable_release_latest"
VERSION = "V11 Portable Offline Release"

TOP_LEVEL_DIRS = {
    ".github",
    "assets",
    "docs",
    "local_ai",
    "rust",
    "src",
    "tests",
}

OPTIONAL_TOP_LEVEL_DIRS = {
    "scripts",
}

TOP_LEVEL_FILES = {
    ".gitignore",
    "AGENTS.md",
    "AGENT_USAGE.txt",
    "CLAUDE.md",
    "C_EXAM_EVAL_PACK.md",
    "Containerfile",
    "OFFLINE_ENHANCEMENT_REPORT.md",
    "PARITY.md",
    "PHILOSOPHY.md",
    "README.md",
    "RELEASE_NOTES.md",
    "ROADMAP.md",
    "USAGE.md",
    "install.sh",
    "pyrightconfig.json",
}

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    ".venv-sft",
    "__pycache__",
    ".pytest_cache",
    ".claude",
    ".claw",
    ".vscode",
    "node_modules",
    "usb_export",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".tmp",
    ".gguf",
    ".safetensors",
}

PRESERVE_TARGET_PARTS = {
    ("local_ai", "runtime"),
    ("pdf_files",),
}

EXCLUDED_TARGET_DIRS = {
    ".git",
    ".venv",
    ".venv-sft",
    "__pycache__",
    ".pytest_cache",
    ".claude",
    ".claw",
    ".vscode",
    "node_modules",
    ("local_ai", "benchmark", "reports", "runs"),
    ("local_ai", "runtime", "logs"),
    ("local_ai", "sft", "artifacts"),
}

ROOT_DEV_FILES = {
    "log.txt",
    "test",
    "test.c",
    "test題目.txt",
    "usage.txt",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rel(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


def split_rel(rel_path: str) -> tuple[str, ...]:
    return tuple(part for part in rel_path.replace("\\", "/").split("/") if part)


def has_prefix(parts: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    return len(parts) >= len(prefix) and parts[: len(prefix)] == prefix


def is_under_preserved_target(rel_path: str) -> bool:
    parts = split_rel(rel_path)
    return any(has_prefix(parts, prefix) for prefix in PRESERVE_TARGET_PARTS)


def excluded_reason(rel_path: str) -> str | None:
    parts = split_rel(rel_path)
    if any(part in EXCLUDED_PARTS for part in parts):
        return "excluded development/cache path"
    suffix = Path(rel_path).suffix.lower()
    if suffix in EXCLUDED_SUFFIXES:
        return f"excluded file suffix {suffix}"
    if has_prefix(parts, ("local_ai", "benchmark", "reports", "runs")):
        return "excluded benchmark run history"
    if has_prefix(parts, ("local_ai", "runtime")):
        return "portable runtime is preserved, not synced from development workspace"
    if has_prefix(parts, ("local_ai", "sft", "artifacts")):
        return "excluded SFT adapter artifact"
    return None


def is_explicit_target_excluded(rel_path: str) -> bool:
    parts = split_rel(rel_path)
    for item in EXCLUDED_TARGET_DIRS:
        prefix = (item,) if isinstance(item, str) else item
        if has_prefix(parts, prefix):
            return True
    suffix = Path(rel_path).suffix.lower()
    return suffix in EXCLUDED_SUFFIXES


def is_allowed_root(path: Path) -> bool:
    rel_path = rel(path, ROOT)
    parts = split_rel(rel_path)
    if not parts:
        return False
    if len(parts) == 1 and path.is_file():
        return parts[0] in TOP_LEVEL_FILES
    first = parts[0]
    return first in TOP_LEVEL_DIRS or first in OPTIONAL_TOP_LEVEL_DIRS


def should_prune_source_dir(rel_path: str) -> str | None:
    parts = split_rel(rel_path)
    if any(part in EXCLUDED_PARTS for part in parts):
        return "excluded development/cache path"
    if has_prefix(parts, ("local_ai", "benchmark", "reports", "runs")):
        return "excluded benchmark run history"
    if has_prefix(parts, ("local_ai", "runtime")):
        return "portable runtime is preserved, not synced from development workspace"
    if has_prefix(parts, ("local_ai", "sft", "artifacts")):
        return "excluded SFT adapter artifact"
    return None


def should_prune_target_dir(rel_path: str) -> bool:
    parts = split_rel(rel_path)
    if any(has_prefix(parts, prefix) for prefix in PRESERVE_TARGET_PARTS):
        return True
    for item in EXCLUDED_TARGET_DIRS:
        prefix = (item,) if isinstance(item, str) else item
        if has_prefix(parts, prefix):
            return True
    return False


def iter_source_candidates() -> tuple[dict[str, Path], list[dict[str, str]]]:
    files: dict[str, Path] = {}
    ignored: list[dict[str, str]] = []

    roots: list[Path] = []
    for name in sorted(TOP_LEVEL_DIRS | OPTIONAL_TOP_LEVEL_DIRS):
        path = ROOT / name
        if path.exists():
            roots.append(path)
    for name in sorted(TOP_LEVEL_FILES):
        path = ROOT / name
        if path.exists():
            roots.append(path)

    for root in roots:
        if root.is_file():
            rel_path = rel(root, ROOT)
            reason = excluded_reason(rel_path)
            if reason:
                ignored.append({"path": rel_path, "reason": reason})
            else:
                files[rel_path] = root
            continue

        for current, dirs, filenames in os.walk(root):
            current_path = Path(current)
            kept_dirs: list[str] = []
            for dirname in dirs:
                dir_path = current_path / dirname
                dir_rel = rel(dir_path, ROOT)
                reason = should_prune_source_dir(dir_rel)
                if reason:
                    ignored.append({"path": dir_rel, "reason": reason})
                else:
                    kept_dirs.append(dirname)
            dirs[:] = kept_dirs

            for filename in filenames:
                path = current_path / filename
                rel_path = rel(path, ROOT)
                reason = excluded_reason(rel_path)
                if reason:
                    ignored.append({"path": rel_path, "reason": reason})
                    continue
                files[rel_path] = path

    return files, ignored


def iter_target_files(target: Path) -> dict[str, Path]:
    if not target.exists():
        return {}
    files: dict[str, Path] = {}
    for current, dirs, filenames in os.walk(target):
        current_path = Path(current)
        kept_dirs: list[str] = []
        for dirname in dirs:
            dir_path = current_path / dirname
            dir_rel = rel(dir_path, target)
            if not should_prune_target_dir(dir_rel):
                kept_dirs.append(dirname)
        dirs[:] = kept_dirs
        for filename in filenames:
            path = current_path / filename
            rel_path = rel(path, ROOT)
            files[rel(path, target)] = path
    return files


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def same_file(src: Path, dst: Path) -> bool:
    if not dst.exists() or not dst.is_file():
        return False
    if src.stat().st_size != dst.stat().st_size:
        return False
    # Scan speed matters for portable releases. If size matches and the target
    # is at least as new as the source, treat it as unchanged. The manifest
    # computes SHA256 after synchronization for integrity.
    return dst.stat().st_mtime >= src.stat().st_mtime


def build_plan(target: Path) -> dict[str, Any]:
    source_files, ignored = iter_source_candidates()
    target_files = iter_target_files(target)

    added: list[str] = []
    modified: list[str] = []
    unchanged: list[str] = []
    deleted: list[str] = []
    preserved: list[str] = []

    for rel_path, src in sorted(source_files.items()):
        dst = target / rel_path
        if not dst.exists():
            added.append(rel_path)
        elif same_file(src, dst):
            unchanged.append(rel_path)
        else:
            modified.append(rel_path)

    source_rel = set(source_files)
    for rel_path in sorted(target_files):
        parts = split_rel(rel_path)
        if rel_path in source_rel:
            continue
        if is_under_preserved_target(rel_path):
            preserved.append(rel_path)
            continue
        if is_explicit_target_excluded(rel_path):
            deleted.append(rel_path)
            continue
        if len(parts) == 1 and parts[0] in ROOT_DEV_FILES:
            deleted.append(rel_path)
            continue
        if parts and (parts[0] in TOP_LEVEL_DIRS or parts[0] in OPTIONAL_TOP_LEVEL_DIRS):
            deleted.append(rel_path)
        elif len(parts) == 1 and parts[0] not in TOP_LEVEL_FILES:
            preserved.append(rel_path)

    ignored.extend(
        {"path": path, "reason": "preserved portable runtime or unmanaged asset"}
        for path in preserved
    )

    report = {
        "generated_at": utc_now(),
        "source_root": str(ROOT),
        "target_root": str(target),
        "version": VERSION,
        "planned": {
            "added_count": len(added),
            "modified_count": len(modified),
            "deleted_count": len(deleted),
            "unchanged_count": len(unchanged),
            "ignored_count": len(ignored),
            "added": added,
            "modified": modified,
            "deleted": deleted,
            "ignored": ignored,
        },
        "guardrails": {
            "changes_benchmark_scoring": False,
            "changes_routing_policy": False,
            "changes_governance": False,
            "changes_datasets": False,
            "trains_lora": False,
            "runs_long_benchmarks": False,
        },
    }
    return report


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_sync_markdown(path: Path, report: dict[str, Any]) -> None:
    plan = report["planned"]
    lines = [
        "# USB Sync Report",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Source: `{report['source_root']}`",
        f"Target: `{report['target_root']}`",
        f"Version: `{report['version']}`",
        "",
        "## Summary",
        "",
        "| Category | Count |",
        "|----------|------:|",
        f"| Added | {plan['added_count']} |",
        f"| Modified | {plan['modified_count']} |",
        f"| Deleted | {plan['deleted_count']} |",
        f"| Unchanged | {plan['unchanged_count']} |",
        f"| Ignored/Preserved | {plan['ignored_count']} |",
        "",
    ]
    for key, title in (("added", "Added"), ("modified", "Modified"), ("deleted", "Deleted")):
        lines += [f"## {title}", ""]
        rows = plan[key]
        if rows:
            lines.extend(f"- `{item}`" for item in rows[:200])
            if len(rows) > 200:
                lines.append(f"- ... {len(rows) - 200} more")
        else:
            lines.append("- None")
        lines.append("")
    lines += ["## Ignored / Preserved", ""]
    for item in plan["ignored"][:200]:
        lines.append(f"- `{item['path']}` - {item['reason']}")
    if len(plan["ignored"]) > 200:
        lines.append(f"- ... {len(plan['ignored']) - 200} more")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def remove_empty_dirs(target: Path) -> None:
    for path in sorted((p for p in target.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if path == target or is_under_preserved_target(rel(path, target)):
            continue
        try:
            path.rmdir()
        except OSError:
            pass


def remove_explicit_excluded_dirs(target: Path) -> list[str]:
    removed: list[str] = []
    candidates: list[Path] = []
    for item in EXCLUDED_TARGET_DIRS:
        parts = (item,) if isinstance(item, str) else item
        candidates.append(target.joinpath(*parts))
    for path in sorted(candidates, key=lambda p: len(p.parts), reverse=True):
        if path.exists() and path.is_dir() and not is_under_preserved_target(rel(path, target)):
            force_rmtree(path)
            removed.append(rel(path, target))
    return removed


def force_rmtree(path: Path) -> None:
    def onerror(func: Any, failing_path: str, _exc_info: Any) -> None:
        try:
            os.chmod(failing_path, stat.S_IWRITE)
            func(failing_path)
        except Exception:
            raise

    shutil.rmtree(path, onerror=onerror)


def apply_plan(target: Path, report: dict[str, Any]) -> dict[str, Any]:
    source_files, _ignored = iter_source_candidates()
    plan = report["planned"]
    copied: list[str] = []
    deleted: list[str] = []

    for rel_path in plan["added"] + plan["modified"]:
        src = source_files[rel_path]
        dst = target / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel_path)

    for rel_path in plan["deleted"]:
        path = target / rel_path
        if path.exists() and path.is_file():
            path.unlink()
            deleted.append(rel_path)

    deleted_dirs = remove_explicit_excluded_dirs(target)
    remove_empty_dirs(target)
    return {
        "copied": copied,
        "deleted": deleted,
        "deleted_dirs": deleted_dirs,
    }


def run_command(target: Path, args: list[str], timeout: int = 300) -> dict[str, Any]:
    command = [sys.executable, *args]
    started = utc_now()
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        command,
        cwd=str(target),
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    return {
        "command": command,
        "started_at": started,
        "returncode": completed.returncode,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def run_validations(target: Path) -> list[dict[str, Any]]:
    return [
        run_command(target, ["local_ai/cli.py", "smoke"], timeout=600),
        run_command(target, ["local_ai/system/system_index.py"], timeout=120),
        run_command(target, ["local_ai/system/build_architecture_map.py"], timeout=120),
    ]


def run_post_snapshot_refresh(target: Path) -> list[dict[str, Any]]:
    return [
        run_command(target, ["local_ai/system/system_index.py"], timeout=120),
        run_command(target, ["local_ai/system/build_report_index.py"], timeout=120),
        run_command(target, ["local_ai/system/build_architecture_map.py"], timeout=120),
    ]


def get_commit() -> dict[str, Any]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        commit = None
    try:
        dirty = subprocess.run(
            ["git", "diff", "--quiet"],
            cwd=str(ROOT),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode != 0
    except Exception:
        dirty = None
    return {"commit": commit, "dirty": dirty}


def managed_manifest_files(target: Path) -> list[str]:
    source_files, _ignored = iter_source_candidates()
    return sorted(path for path in source_files if (target / path).exists())


def manifest_digest(target: Path, files: list[str]) -> str:
    h = hashlib.sha256()
    for rel_path in files:
        path = target / rel_path
        h.update(rel_path.encode("utf-8"))
        h.update(b"\0")
        h.update(sha256_file(path).encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def latest_snapshot(target: Path) -> str | None:
    snapshots = target / "local_ai" / "release" / "snapshots"
    if not snapshots.exists():
        return None
    candidates = sorted(snapshots.glob(f"{RELEASE_NAME}*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0].name if candidates else None


def build_manifest(target: Path, validations: list[dict[str, Any]], snapshot_result: dict[str, Any]) -> dict[str, Any]:
    files = managed_manifest_files(target)
    commit = get_commit()
    smoke = next((row for row in validations if "smoke" in " ".join(row["command"])), None)
    return {
        "version": VERSION,
        "snapshot": latest_snapshot(target),
        "snapshot_command_status": snapshot_result.get("status"),
        "commit": commit.get("commit"),
        "dirty": commit.get("dirty"),
        "file_count": len([path for path in target.rglob("*") if path.is_file()]),
        "managed_file_count": len(files),
        "managed_sha256": manifest_digest(target, files),
        "build_time": utc_now(),
        "smoke_status": smoke.get("status") if smoke else None,
        "target_root": str(target),
    }


def write_release_markdown(path: Path, report: dict[str, Any]) -> None:
    sync = report["sync"]
    validation = report["validation"]
    manifest = report.get("manifest") or {}
    lines = [
        "# Portable Release Report",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Version: `{report['version']}`",
        f"Status: `{report['status']}`",
        "",
        "## Sync",
        "",
        f"- Copied files: {sync['copied_count']}",
        f"- Deleted files: {sync['deleted_count']}",
        f"- Deleted directories: {sync['deleted_dir_count']}",
        f"- Ignored/preserved entries: {sync['ignored_count']}",
        "",
        "## Validation",
        "",
        "| Step | Status | Return Code |",
        "|------|--------|------------:|",
    ]
    for row in validation:
        cmd = " ".join(row["command"][1:])
        lines.append(f"| `{cmd}` | {row['status']} | {row['returncode']} |")
    lines += [
        "",
        "## Post-Snapshot Refresh",
        "",
        "| Step | Status | Return Code |",
        "|------|--------|------------:|",
    ]
    for row in report.get("post_snapshot_refresh", []):
        cmd = " ".join(row["command"][1:])
        lines.append(f"| `{cmd}` | {row['status']} | {row['returncode']} |")
    if not report.get("post_snapshot_refresh"):
        lines.append("| none | SKIPPED | - |")
    lines += [
        "",
        "## Manifest",
        "",
        f"- Snapshot: `{manifest.get('snapshot')}`",
        f"- Commit: `{manifest.get('commit')}`",
        f"- Dirty: `{manifest.get('dirty')}`",
        f"- Managed file count: `{manifest.get('managed_file_count')}`",
        f"- Managed SHA256: `{manifest.get('managed_sha256')}`",
        f"- Smoke status: `{manifest.get('smoke_status')}`",
        "",
        "## Known Limitations",
        "",
        "- Portable runtime/model blobs are preserved from the existing USB package and are not refreshed from the development workspace.",
        "- Benchmark run history is intentionally excluded.",
        "- LoRA artifacts and large model weights are intentionally excluded from source synchronization.",
        "- This release validates infrastructure smoke paths; it does not run long generated benchmarks or training.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize portable USB release")
    parser.add_argument("--target", default=str(DEFAULT_TARGET))
    parser.add_argument("--scan-only", action="store_true")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    target.mkdir(parents=True, exist_ok=True)

    sync_report = build_plan(target)
    write_json(target / "usb_sync_report.json", sync_report)
    write_sync_markdown(target / "usb_sync_report.md", sync_report)
    print(f"[usb-sync] scan report -> {target / 'usb_sync_report.md'}")

    if args.scan_only:
        print("[usb-sync] scan-only complete")
        return 0

    applied = apply_plan(target, sync_report)
    print(
        "[usb-sync] applied "
        f"copied={len(applied['copied'])} "
        f"deleted={len(applied['deleted'])} "
        f"deleted_dirs={len(applied['deleted_dirs'])}"
    )

    validations = run_validations(target)
    validation_ok = all(row["returncode"] == 0 for row in validations)
    post_snapshot_refresh: list[dict[str, Any]] = []
    snapshot_result: dict[str, Any] = {
        "command": [sys.executable, "local_ai/release/snapshot.py", "--name", RELEASE_NAME],
        "status": "SKIPPED",
        "returncode": None,
    }
    manifest: dict[str, Any] | None = None

    if validation_ok:
        snapshot_result = run_command(
            target,
            ["local_ai/release/snapshot.py", "--name", RELEASE_NAME],
            timeout=300,
        )
        if snapshot_result["returncode"] == 0:
            post_snapshot_refresh = run_post_snapshot_refresh(target)
            manifest = build_manifest(target, validations, snapshot_result)
            write_json(target / "portable_manifest.json", manifest)

    refresh_ok = all(row["returncode"] == 0 for row in post_snapshot_refresh)
    status = (
        "PASS"
        if validation_ok and snapshot_result.get("returncode") == 0 and refresh_ok
        else "FAIL"
    )
    release_report = {
        "generated_at": utc_now(),
        "version": VERSION,
        "target_root": str(target),
        "status": status,
        "sync": {
            "copied_count": len(applied["copied"]),
            "deleted_count": len(applied["deleted"]),
            "deleted_dir_count": len(applied["deleted_dirs"]),
            "ignored_count": sync_report["planned"]["ignored_count"],
            "added_count": sync_report["planned"]["added_count"],
            "modified_count": sync_report["planned"]["modified_count"],
            "planned_deleted_count": sync_report["planned"]["deleted_count"],
            "copied": applied["copied"],
            "deleted": applied["deleted"],
            "deleted_dirs": applied["deleted_dirs"],
        },
        "validation": validations,
        "snapshot": snapshot_result,
        "post_snapshot_refresh": post_snapshot_refresh,
        "manifest": manifest,
        "known_limitations": [
            "Portable runtime/model blobs are preserved and not refreshed from development workspace.",
            "Benchmark run history is excluded.",
            "LoRA artifacts and large model weights are excluded.",
            "No training or long generated benchmarks are run during release sync.",
        ],
    }
    write_json(target / "portable_release_report.json", release_report)
    write_release_markdown(target / "portable_release_report.md", release_report)

    print(f"[usb-sync] release report -> {target / 'portable_release_report.md'}")
    if status != "PASS":
        print("[usb-sync] release validation failed", file=sys.stderr)
        return 1
    print("[usb-sync] portable release PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
