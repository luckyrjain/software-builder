"""Tests for scripts/install_engine.py's locking primitives -- a Python port of
scripts/install.sh's acquire_lock/reclaim_stale_lock/release_current_lock, mirroring the
scenarios scripts/tests/test_install_concurrency.py already locks in for the bash version."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from scripts.install_engine import LockTimeoutError, held_lock


def test_stale_lock_from_a_dead_pid_is_reclaimed_immediately(tmp_path: Path) -> None:
    lock_dir = tmp_path / ".demo-skill.lock"
    lock_dir.mkdir()
    (lock_dir / "pid").write_text("999999999", encoding="utf-8")
    (lock_dir / "acquired_at").write_text(str(time.time()), encoding="utf-8")

    start = time.monotonic()
    with held_lock(tmp_path, "demo-skill", wait_timeout=20.0):
        elapsed = time.monotonic() - start
    assert elapsed < 10.0


def test_stale_lock_past_the_age_threshold_is_reclaimed_even_with_a_live_pid(tmp_path: Path) -> None:
    lock_dir = tmp_path / ".demo-skill.lock"
    lock_dir.mkdir()
    (lock_dir / "pid").write_text(str(os.getpid()), encoding="utf-8")  # alive: this test process
    (lock_dir / "acquired_at").write_text(str(time.time() - 1000), encoding="utf-8")

    with held_lock(tmp_path, "demo-skill", wait_timeout=20.0, stale_after=300.0):
        pass  # must not raise LockTimeoutError -- age fallback must fire regardless of liveness


def test_live_held_lock_times_out_with_a_clear_error(tmp_path: Path) -> None:
    holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        lock_dir = tmp_path / ".demo-skill.lock"
        lock_dir.mkdir()
        (lock_dir / "pid").write_text(str(holder.pid), encoding="utf-8")
        (lock_dir / "acquired_at").write_text(str(time.time()), encoding="utf-8")

        start = time.monotonic()
        with pytest.raises(LockTimeoutError, match=f"held by pid {holder.pid}"):
            with held_lock(tmp_path, "demo-skill", wait_timeout=2.0):
                pass
        elapsed = time.monotonic() - start
        assert 2.0 <= elapsed < 15.0
    finally:
        holder.terminate()
        holder.wait(timeout=5)


def test_stale_lock_reclaim_renames_before_removing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mirrors test_install_concurrency.py's own approach: confirm the rename-before-remove
    discipline is actually implemented (not just that reclaim eventually succeeds), by
    intercepting os.rename and asserting it's called before the lock_dir disappears."""
    lock_dir = tmp_path / ".demo-skill.lock"
    lock_dir.mkdir()
    (lock_dir / "pid").write_text("999999999", encoding="utf-8")
    (lock_dir / "acquired_at").write_text(str(time.time()), encoding="utf-8")

    rename_calls: list[tuple[Path, Path]] = []
    real_rename = os.rename

    def spy_rename(src, dst):
        rename_calls.append((Path(src), Path(dst)))
        return real_rename(src, dst)

    monkeypatch.setattr("scripts.install_engine.os.rename", spy_rename)

    with held_lock(tmp_path, "demo-skill", wait_timeout=20.0):
        pass

    assert len(rename_calls) == 1
    assert rename_calls[0][0] == lock_dir
    assert not lock_dir.exists()
    assert not rename_calls[0][1].exists()  # the stale-renamed copy was removed too
