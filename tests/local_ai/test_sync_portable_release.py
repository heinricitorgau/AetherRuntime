from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "local_ai" / "release" / "sync_portable_release.py"


@pytest.fixture()
def sync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location("sync_portable_release_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    # Minimal source checkout with no Rust build output (like a fresh worktree).
    source = tmp_path / "source"
    (source / "local_ai").mkdir(parents=True)
    (source / "local_ai" / "proxy.py").write_text("print('new')\n", encoding="utf-8")
    (source / "rust" / "crates").mkdir(parents=True)
    (source / "rust" / "crates" / "lib.rs").write_text("// src\n", encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", source)
    return module


def _make_target(base: Path) -> Path:
    # Lives outside the source ROOT on purpose.
    target = base / "usb" / "bundle"
    for rel_path, text in {
        # Different size from the source copy: the script treats same-size
        # files with a newer target mtime as unchanged.
        "local_ai/proxy.py": "print('stale bundle copy')\n",
        "local_ai/stale.py": "old\n",
        "rust/target/release/claw.exe": "binary",
        "rust/target/debug/claw.exe": "binary",
        "rust/target/debug/.fingerprint/x/dep": "fp",
    }.items():
        path = target / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return target


def test_plan_accepts_target_outside_root(sync, tmp_path: Path) -> None:
    target = _make_target(tmp_path)
    report = sync.build_plan(target)
    assert report["target_root"] == str(target)


def test_plan_never_deletes_rust_target(sync, tmp_path: Path) -> None:
    target = _make_target(tmp_path)
    report = sync.build_plan(target)

    deleted = report["planned"]["deleted"]
    assert not [p for p in deleted if p.startswith("rust/target")]
    assert "local_ai/stale.py" in deleted

    ignored = report["planned"]["ignored"]
    assert {"path": "rust/target", "reason": "preserved directory in portable target (never deleted)"} in ignored


def test_apply_keeps_prebuilt_claw_exe(sync, tmp_path: Path) -> None:
    target = _make_target(tmp_path)
    report = sync.build_plan(target)
    sync.apply_plan(target, report)

    assert (target / "rust" / "target" / "release" / "claw.exe").is_file()
    assert (target / "rust" / "target" / "debug" / "claw.exe").is_file()
    assert not (target / "local_ai" / "stale.py").exists()
    assert (target / "local_ai" / "proxy.py").read_text(encoding="utf-8") == "print('new')\n"
