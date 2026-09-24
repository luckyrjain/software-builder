"""Tests for scripts/install_engine.py's uninstall_skill() -- mirrors the ownership-hardening
scenarios scripts/tests/test_install_legacy_golden.py already locks in for install.sh's
uninstall path."""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path

import pytest

import scripts.install_engine as install_engine
from scripts.install_engine import uninstall_skill
from scripts.tests.install_lock_test_helpers import spawn_lock_holder


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


def test_unexpected_exception_from_classify_destination_yields_failed_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """classify_install_destination() used to run inside a try whose except only caught
    (LockTimeoutError, OSError) -- an unexpected exception type from it (e.g. a malformed
    on-disk manifest raising something other than ManifestError) propagated straight through
    uninstall_skill() as an uncaught traceback instead of a clean failed outcome."""
    dest_root = tmp_path / "dest"
    _owned_install(dest_root, "demo-skill")

    def _boom(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr(install_engine, "classify_install_destination", _boom)

    outcome = uninstall_skill("demo-skill", dest_root=dest_root)

    assert outcome.status == "failed"
    assert "boom" in outcome.message


@pytest.mark.skipif(sys.platform == "win32", reason="os.kill(pid, SIGTERM) bypasses Python's signal module on Windows")
def test_sigterm_during_rmtree_exits_130(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A real SIGTERM mid-uninstall must produce the same clean exit-130 convention
    install_skill() uses, not a raw signal-death exit code install.sh's `((status == 130))`
    check wouldn't recognize -- even though there's nothing to roll back here."""
    dest_root = tmp_path / "dest"
    dest = _owned_install(dest_root, "demo-skill")
    original_handler = signal.getsignal(signal.SIGTERM)

    real_rmtree = install_engine.shutil.rmtree
    fired = False

    def _send_sigterm_once(path: object, *args: object, **kwargs: object) -> None:
        # shutil.rmtree is patched process-wide -- only the deletion of the moved-aside
        # `.removing.*` copy should trip this, not any other rmtree call this test's setup or
        # teardown might make.
        nonlocal fired
        if not fired and ".removing." in str(path):
            fired = True
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(0.2)
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(install_engine.shutil, "rmtree", _send_sigterm_once)

    try:
        with pytest.raises(SystemExit) as exc_info:
            uninstall_skill("demo-skill", dest_root=dest_root)
        assert exc_info.value.code == 130
        # The deletion is deferred, not abandoned: it ran to completion before the exit.
        assert not dest.exists()
        assert [p for p in dest_root.glob(".demo-skill.*") if p.name != ".demo-skill.lock"] == []
        assert signal.getsignal(signal.SIGTERM) == original_handler
    finally:
        signal.signal(signal.SIGTERM, original_handler)


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


def test_uninstall_live_held_lock_yields_a_failed_outcome_instead_of_raising(tmp_path: Path) -> None:
    """A concurrent/stuck lock must surface as UninstallOutcome(status="failed"), not an
    unhandled LockTimeoutError -- mirrors test_install_engine_locking.py's
    test_a_live_held_lock_times_out_with_a_clear_error's real-subprocess-holder technique (and
    install_skill's own matching test in test_install_engine_install.py), through
    uninstall_skill() itself so a multi-skill `sb uninstall` run can keep going instead of
    crashing mid-run. Calls uninstall_skill()'s own `wait_timeout` parameter directly -- it
    forwards straight to held_lock()."""
    dest_root = tmp_path / "dest"
    dest = _owned_install(dest_root, "demo-skill")

    lock_path = install_engine._lock_path_for(dest_root, "demo-skill")
    holder = spawn_lock_holder(lock_path)
    try:
        outcome = uninstall_skill("demo-skill", dest_root=dest_root, wait_timeout=2.0)

        assert outcome.status == "failed"
        assert "timed out waiting for lock" in outcome.message
        assert dest.exists()
    finally:
        holder.kill()
        holder.wait(timeout=5)


def test_two_different_skills_at_the_same_dest_root_do_not_block_each_other(tmp_path: Path) -> None:
    """The lock is keyed on (dest_root, skill); holding skill A's lock must never make skill
    B's uninstall wait."""
    dest_root = tmp_path / "dest"
    _owned_install(dest_root, "demo-skill")

    other_lock = install_engine._lock_path_for(dest_root, "some-other-skill")
    holder = spawn_lock_holder(other_lock)
    try:
        start = time.monotonic()
        outcome = uninstall_skill("demo-skill", dest_root=dest_root, wait_timeout=10.0)
        elapsed = time.monotonic() - start
        assert outcome.status == "uninstalled"
        assert elapsed < 2.0
    finally:
        holder.kill()
        holder.wait(timeout=5)


def test_a_preexisting_lock_file_with_garbage_content_is_still_acquired_normally(tmp_path: Path) -> None:
    """The lock file is deliberately left behind after every run -- a pre-existing, non-empty
    file at that path is the common case, not the exception; acquiring must not care what
    bytes are already there."""
    dest_root = tmp_path / "dest"
    _owned_install(dest_root, "demo-skill")
    lock_path = install_engine._lock_path_for(dest_root, "demo-skill")
    lock_path.write_bytes(b"\xff\xfe not a pid, not utf-8, no trailing newline")

    outcome = uninstall_skill("demo-skill", dest_root=dest_root)

    assert outcome.status == "uninstalled"


def test_uninstall_reports_failure_when_rmtree_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dest_root = tmp_path / "dest"
    dest = _owned_install(dest_root, "demo-skill")
    real_rmtree = install_engine.shutil.rmtree

    def _boom(path: Path, *args: object, **kwargs: object) -> None:
        # Only the deletion of the skill itself (moved aside to `.removing.*` first) should
        # fail.
        if ".removing." in str(path):
            raise OSError("permission denied")
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(install_engine.shutil, "rmtree", _boom)

    outcome = uninstall_skill("demo-skill", dest_root=dest_root)

    assert outcome.status == "failed"
    assert "permission denied" in outcome.message
    # Renamed aside before the failing delete: the destination is absent (a later install or
    # uninstall works), not a half-deleted directory that nothing would touch again.
    assert not dest.exists()
