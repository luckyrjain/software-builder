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

from scripts import install_engine
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
    intercepting os.rename and asserting it's called before the lock_dir disappears. Other
    os.rename calls happen too now (this module's own atomic-acquisition temp-dir renames,
    both the failed first attempt against this non-empty lock_dir and the successful retry
    after reclaim) -- filtered out by source path, since only _reclaim_stale_lock ever renames
    lock_dir itself (acquisition always renames FROM a temp dir, never from lock_dir)."""
    lock_dir = tmp_path / ".demo-skill.lock"
    lock_dir.mkdir()
    (lock_dir / "pid").write_text("999999999", encoding="utf-8")
    (lock_dir / "acquired_at").write_text(str(time.time()), encoding="utf-8")

    reclaim_rename_calls: list[tuple[Path, Path]] = []
    real_rename = os.rename

    def spy_rename(src, dst):
        src, dst = Path(src), Path(dst)
        if src == lock_dir:
            reclaim_rename_calls.append((src, dst))
        return real_rename(src, dst)

    monkeypatch.setattr("scripts.install_engine.os.rename", spy_rename)

    with held_lock(tmp_path, "demo-skill", wait_timeout=20.0):
        pass

    assert len(reclaim_rename_calls) == 1
    assert reclaim_rename_calls[0][0] == lock_dir
    assert not lock_dir.exists()
    assert not reclaim_rename_calls[0][1].exists()  # the stale-renamed copy was removed too


def test_empty_leftover_lock_dir_is_claimed_immediately_via_atomic_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bare, empty lock directory -- e.g. left behind by a holder's own release whose
    shutil.rmtree removed every file inside but was interrupted before removing the directory
    itself -- is silently absorbed by the next acquisition's atomic rename (POSIX rename()
    succeeds replacing an empty directory) rather than being waited on or explicitly
    reclaimed. This is the new behavior since acquisition became atomic (see held_lock()'s
    docstring): a legitimate in-progress acquisition never leaves lock_dir visible-but-empty
    anymore, so an empty lock_dir can only mean "already vacated" -- claiming it directly is
    correct, not a bug, and replaces the old "mid-setup window, must wait" scenario this test
    used to cover, which no longer occurs under legitimate operation."""
    lock_dir = tmp_path / ".demo-skill.lock"
    lock_dir.mkdir()  # empty: simulates an interrupted release, not mid-acquisition anymore

    reclaim_calls: list[Path] = []
    real_reclaim = install_engine._reclaim_stale_lock

    def spy_reclaim(target: Path) -> None:
        reclaim_calls.append(target)
        real_reclaim(target)

    monkeypatch.setattr(install_engine, "_reclaim_stale_lock", spy_reclaim)

    start = time.monotonic()
    with held_lock(tmp_path, "demo-skill", wait_timeout=20.0):
        elapsed = time.monotonic() - start
    assert elapsed < 2.0  # claimed immediately, not waited on
    assert reclaim_calls == []  # no reclaim needed -- the rename absorbed it directly


def test_live_pid_with_unreadable_age_and_unreadable_mtime_fallback_is_still_reclaimed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The actual line this PR's second round restored: `is_stale = age is None or age >
    stale_after` (not `age is not None and ...`). The two "no pid file" tests above don't
    exercise it -- they never make lock_dir.stat() fail, so `age` is never actually None by
    the time this line runs. This forces the real double-failure case the line is about: pid
    present and genuinely alive (so the pid check alone doesn't mark it stale), acquired_at
    unreadable, AND the mtime fallback also unreadable (e.g. a TOCTOU race where the lock
    directory is removed by its own holder's cleanup between this waiter's FileExistsError
    and its stat() call) -- age stays None, and that must still mean stale, not live."""
    lock_dir = tmp_path / ".demo-skill.lock"
    lock_dir.mkdir()
    (lock_dir / "pid").write_text(str(os.getpid()), encoding="utf-8")  # alive: this process
    # no acquired_at written -- _read_lock_age() returns None

    real_stat = Path.stat

    def spy_stat(self: Path, *args: object, **kwargs: object):
        if self == lock_dir:
            raise OSError("simulated: lock_dir vanished before stat()")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", spy_stat)

    with held_lock(tmp_path, "demo-skill", wait_timeout=5.0, stale_after=300.0):
        pass  # must not raise LockTimeoutError -- age=None must still be treated as stale


def test_lock_dir_with_no_pid_file_is_reclaimed_once_its_own_mtime_is_stale(tmp_path: Path) -> None:
    """A lock directory with neither a pid nor an acquired_at file falls through to the
    directory's own mtime as an age fallback; once that's older than stale_after, it's still
    reclaimable rather than blocking forever. Deliberately non-empty (an unrelated file, not
    pid/acquired_at) so the atomic-acquisition rename can't just silently absorb it as an
    empty leftover (see the dedicated empty-dir test above) -- this forces the real
    staleness-decision path to run, the thing this test is actually about."""
    lock_dir = tmp_path / ".demo-skill.lock"
    lock_dir.mkdir()
    (lock_dir / "unrelated-file").write_text("neither pid nor acquired_at", encoding="utf-8")
    old = time.time() - 1000
    os.utime(lock_dir, (old, old))

    with held_lock(tmp_path, "demo-skill", wait_timeout=5.0, stale_after=1.0):
        pass  # must not raise LockTimeoutError -- the mtime fallback must reclaim it
