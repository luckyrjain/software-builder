"""Tests for scripts/install_engine.py's uninstall_skill() -- mirrors the ownership-hardening
scenarios scripts/tests/test_install_legacy_golden.py already locks in for install.sh's
uninstall path."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

import scripts.install_engine as install_engine
from scripts.install_engine import uninstall_skill


def _owned_install(dest_root: Path, skill_id: str) -> Path:
    dest = dest_root / skill_id
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
    (dest / ".software-builder-manifest.json").write_text(
        json.dumps({"manifest_version": 1, "skill": skill_id, "files": {}}), encoding="utf-8"
    )
    return dest


def test_uninstall_removes_an_owned_install(tmp_path: Path) -> None:
    dest_root = tmp_path / "dest"
    dest = _owned_install(dest_root, "demo-skill")

    outcome = uninstall_skill("demo-skill", dest_root=dest_root)

    assert outcome.status == "uninstalled"
    assert not dest.exists()


def test_uninstall_of_absent_skill_warns_without_failing(tmp_path: Path) -> None:
    dest_root = tmp_path / "dest"
    dest_root.mkdir()

    outcome = uninstall_skill("demo-skill", dest_root=dest_root)

    assert outcome.status == "absent"


def test_uninstall_refuses_to_remove_a_symlink(tmp_path: Path) -> None:
    dest_root = tmp_path / "dest"
    dest_root.mkdir()
    target = tmp_path / "elsewhere"
    target.mkdir()
    (dest_root / "demo-skill").symlink_to(target)

    outcome = uninstall_skill("demo-skill", dest_root=dest_root)

    assert outcome.status == "failed"
    assert "symlink" in outcome.message.lower()
    assert (dest_root / "demo-skill").is_symlink()  # untouched


def test_uninstall_refuses_to_remove_an_unowned_directory(tmp_path: Path) -> None:
    dest_root = tmp_path / "dest"
    dest = dest_root / "demo-skill"
    dest.mkdir(parents=True)
    (dest / "some-other-file.txt").write_text("not ours\n", encoding="utf-8")

    outcome = uninstall_skill("demo-skill", dest_root=dest_root)

    assert outcome.status == "failed"
    assert "unowned" in outcome.message.lower()
    assert dest.exists()


def test_uninstall_refuses_to_remove_a_directory_with_corrupt_manifest(tmp_path: Path) -> None:
    dest_root = tmp_path / "dest"
    dest = dest_root / "demo-skill"
    dest.mkdir(parents=True)
    (dest / ".software-builder-manifest.json").write_text("not valid json", encoding="utf-8")

    outcome = uninstall_skill("demo-skill", dest_root=dest_root)

    assert outcome.status == "failed"
    assert dest.exists()


def test_uninstall_dry_run_makes_no_changes(tmp_path: Path) -> None:
    dest_root = tmp_path / "dest"
    dest = _owned_install(dest_root, "demo-skill")

    outcome = uninstall_skill("demo-skill", dest_root=dest_root, dry_run=True)

    assert outcome.status == "dry_run"
    assert dest.exists()


def test_uninstall_rejects_a_skill_id_with_a_path_separator(tmp_path: Path) -> None:
    dest_root = tmp_path / "dest"
    dest_root.mkdir()

    outcome = uninstall_skill("../escape", dest_root=dest_root)

    assert outcome.status == "failed"
    assert not (tmp_path / "escape").exists()  # nothing touched outside dest_root


def test_uninstall_live_held_lock_yields_a_failed_outcome_instead_of_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A concurrent/stuck lock must surface as UninstallOutcome(status="failed"), not an
    unhandled LockTimeoutError -- mirrors test_install_engine_locking.py's
    test_live_held_lock_times_out_with_a_clear_error's real-subprocess-holder technique (and
    install_skill's own matching test in test_install_engine_install.py), through
    uninstall_skill() itself so a multi-skill `sb uninstall` run can keep going instead of
    crashing mid-run. uninstall_skill() doesn't expose held_lock's wait_timeout, so it's
    shortened here by wrapping the module-level held_lock."""
    real_held_lock = install_engine.held_lock

    @contextmanager
    def _short_wait_held_lock(dest_root: Path, skill_id: str, **_kwargs: object):
        with real_held_lock(dest_root, skill_id, wait_timeout=2.0):
            yield

    monkeypatch.setattr(install_engine, "held_lock", _short_wait_held_lock)

    dest_root = tmp_path / "dest"
    dest = _owned_install(dest_root, "demo-skill")

    holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        lock_dir = dest_root / ".demo-skill.lock"
        lock_dir.mkdir()
        (lock_dir / "pid").write_text(str(holder.pid), encoding="utf-8")
        (lock_dir / "acquired_at").write_text(str(time.time()), encoding="utf-8")

        outcome = uninstall_skill("demo-skill", dest_root=dest_root)

        assert outcome.status == "failed"
        assert "timed out waiting for lock" in outcome.message
        assert dest.exists()
    finally:
        holder.terminate()
        holder.wait(timeout=5)


def test_uninstall_reports_failure_when_rmtree_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dest_root = tmp_path / "dest"
    dest = _owned_install(dest_root, "demo-skill")
    real_rmtree = install_engine.shutil.rmtree

    def _boom(path: Path, *args: object, **kwargs: object) -> None:
        # Only the terminal removal of the skill itself should fail; held_lock's own
        # lock-directory cleanup (a separate shutil.rmtree call) must still work normally.
        if Path(path) == dest:
            raise OSError("permission denied")
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(install_engine.shutil, "rmtree", _boom)

    outcome = uninstall_skill("demo-skill", dest_root=dest_root)

    assert outcome.status == "failed"
    assert "permission denied" in outcome.message
    assert dest.exists()
