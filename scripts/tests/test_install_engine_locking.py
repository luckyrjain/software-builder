"""Tests for scripts/install_engine.py's locking primitives -- an OS advisory file lock
(`flock()` on POSIX, `msvcrt.locking()` on Windows), not a directory this module tracks the
identity, age, or liveness of itself. See docs/adr/0007-shared-install-engine.md for why."""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

import pytest

from scripts import install_engine
from scripts.install_engine import LockTimeoutError, held_lock
from scripts.tests.install_lock_test_helpers import spawn_lock_holder

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal semantics")


def test_an_uncontended_lock_is_acquired_immediately(tmp_path: Path) -> None:
    start = time.monotonic()
    with held_lock(tmp_path, "demo-skill", wait_timeout=20.0):
        elapsed = time.monotonic() - start
    assert elapsed < 2.0


def test_a_live_held_lock_times_out_with_a_clear_error(tmp_path: Path) -> None:
    lock_path = install_engine._lock_path_for(tmp_path, "demo-skill")
    holder = spawn_lock_holder(lock_path)
    try:
        start = time.monotonic()
        with pytest.raises(LockTimeoutError, match=f"held by pid {holder.pid}"):
            with held_lock(tmp_path, "demo-skill", wait_timeout=2.0):
                pass  # pragma: no cover
        elapsed = time.monotonic() - start
        assert 2.0 <= elapsed < 15.0
    finally:
        holder.kill()
        holder.wait(timeout=5)


_HELD_LOCK_HOLDER_CODE = """
import sys, time
from pathlib import Path
sys.path.insert(0, {root!r})
from scripts.install_engine import held_lock

with held_lock(Path({dest!r}), "demo-skill", wait_timeout=30.0):
    print("locked", flush=True)
    time.sleep(30)
"""


def test_a_lock_held_via_held_lock_itself_identifies_its_pid_in_the_timeout_message(tmp_path: Path) -> None:
    """The test above's holder writes its pid through the shared helper's own direct
    `_write_holder_pid` call, bypassing `held_lock()` entirely -- this exercises `held_lock()`'s
    own write, on the path every real caller actually takes."""
    import subprocess

    from scripts.tests.install_lock_test_helpers import ROOT

    code = _HELD_LOCK_HOLDER_CODE.format(root=str(ROOT), dest=str(tmp_path))
    holder = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "locked"
        with pytest.raises(LockTimeoutError, match=f"held by pid {holder.pid}"):
            with held_lock(tmp_path, "demo-skill", wait_timeout=2.0):
                pass  # pragma: no cover
    finally:
        holder.kill()
        holder.wait(timeout=5)


def test_a_zero_wait_timeout_times_out_immediately_against_a_live_lock(tmp_path: Path) -> None:
    """`waited >= wait_timeout` must be checked before the first sleep, not after -- an off-by-
    one (`>` instead of `>=`) would make a wait_timeout=0 caller wait out one full poll
    interval before giving up, instead of failing on the very first check."""
    lock_path = install_engine._lock_path_for(tmp_path, "demo-skill")
    holder = spawn_lock_holder(lock_path)
    try:
        start = time.monotonic()
        with pytest.raises(LockTimeoutError):
            with held_lock(tmp_path, "demo-skill", wait_timeout=0.0):
                pass  # pragma: no cover
        assert time.monotonic() - start < 0.5
    finally:
        holder.kill()
        holder.wait(timeout=5)


def test_the_lock_is_released_the_moment_the_holder_is_killed(tmp_path: Path) -> None:
    """The whole point of moving to an OS advisory lock: nothing this module does is needed to
    free it after a hard kill -- the kernel does it as part of tearing down the process."""
    lock_path = install_engine._lock_path_for(tmp_path, "demo-skill")
    holder = spawn_lock_holder(lock_path)
    try:
        holder.kill()
        holder.wait(timeout=5)
        start = time.monotonic()
        with held_lock(tmp_path, "demo-skill", wait_timeout=10.0):
            elapsed = time.monotonic() - start
        assert elapsed < 5.0
    finally:
        if holder.poll() is None:
            holder.kill()


def test_two_holders_are_never_inside_the_critical_section_together(tmp_path: Path) -> None:
    """The old directory-based design's reclaim logic could, under the right race, let two
    processes believe they both held the lock; the OS's own lock has no such window by
    construction, but this stays as a regression guard."""
    import subprocess
    import textwrap

    root = Path(__file__).resolve().parents[2]
    code = textwrap.dedent(
        f"""
        import os, sys, time
        from pathlib import Path
        sys.path.insert(0, {str(root)!r})
        from scripts.install_engine import held_lock

        dest = Path({str(tmp_path)!r})
        marker = os.path.join(dest, "in-critical-section")
        collisions = 0
        for _ in range(25):
            with held_lock(dest, "demo-skill", wait_timeout=60.0):
                try:
                    fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                except FileExistsError:
                    collisions += 1
                else:
                    os.close(fd)
                    time.sleep(0.001)
                    os.unlink(marker)
        print(collisions)
        """
    )
    procs = [
        subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        for _ in range(6)
    ]
    collisions = 0
    try:
        for proc in procs:
            out, _ = proc.communicate(timeout=120)
            assert proc.returncode == 0
            collisions += int(out.strip())
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)
    assert collisions == 0


def test_a_directory_format_lock_from_before_the_flock_rewrite_is_cleared_and_replaced(tmp_path: Path) -> None:
    """A version of this module before it switched to flock() left `.{skill}.lock` as a
    directory (holding `pid`/`acquired_at` files); nothing ever held an OS-level lock on that
    directory under either scheme, so a leftover one must not block the new file-based lock."""
    lock_path = install_engine._lock_path_for(tmp_path, "demo-skill")
    lock_path.mkdir()
    (lock_path / "pid").write_text("12345", encoding="utf-8")
    (lock_path / "acquired_at").write_text("0", encoding="utf-8")

    with held_lock(tmp_path, "demo-skill", wait_timeout=5.0):
        pass
    assert lock_path.is_file()


def test_concurrent_migration_of_the_same_leftover_directory_lock_is_safe(tmp_path: Path) -> None:
    """The single-process migration test above never exercises the actual race: several
    processes discovering the same leftover directory-format lock at once, each clearing it
    (`shutil.rmtree(..., ignore_errors=True)`) and racing to create the replacement file. None
    of that may crash, corrupt the lock, or let two of them believe they hold it together."""
    import subprocess
    import textwrap

    root = Path(__file__).resolve().parents[2]
    lock_path = install_engine._lock_path_for(tmp_path, "demo-skill")
    lock_path.mkdir()
    (lock_path / "pid").write_text("12345", encoding="utf-8")
    (lock_path / "acquired_at").write_text("0", encoding="utf-8")

    code = textwrap.dedent(
        f"""
        import os, sys, time
        from pathlib import Path
        sys.path.insert(0, {str(root)!r})
        from scripts.install_engine import held_lock

        dest = Path({str(tmp_path)!r})
        marker = os.path.join(dest, "in-critical-section")
        collisions = 0
        for _ in range(10):
            with held_lock(dest, "demo-skill", wait_timeout=60.0):
                try:
                    fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                except FileExistsError:
                    collisions += 1
                else:
                    os.close(fd)
                    time.sleep(0.001)
                    os.unlink(marker)
        print(collisions)
        """
    )
    procs = [
        subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        for _ in range(6)
    ]
    collisions = 0
    try:
        for proc in procs:
            out, _ = proc.communicate(timeout=120)
            assert proc.returncode == 0
            collisions += int(out.strip())
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)
    assert collisions == 0
    assert lock_path.is_file()


@posix_only
def test_sigterm_while_waiting_for_a_live_lock_exits_130_and_leaves_that_lock_alone(
    tmp_path: Path, signal_sentinels: object
) -> None:
    lock_path = install_engine._lock_path_for(tmp_path, "demo-skill")
    holder = spawn_lock_holder(lock_path)
    try:
        import threading

        def _signal_shortly() -> None:
            time.sleep(0.3)
            os.kill(os.getpid(), signal.SIGTERM)

        threading.Thread(target=_signal_shortly, daemon=True).start()
        with pytest.raises(SystemExit) as exc_info:
            with held_lock(tmp_path, "demo-skill", wait_timeout=30.0):
                pass  # pragma: no cover
        assert exc_info.value.code == 130
        # This call never acquired the lock: the holder subprocess must still hold it, not have
        # been disturbed by the signal aimed at the *waiter*.
        assert holder.poll() is None
        probe_fd = os.open(lock_path, os.O_RDWR)
        try:
            assert not install_engine._try_lock(probe_fd)
        finally:
            os.close(probe_fd)
    finally:
        holder.kill()
        holder.wait(timeout=5)


def test_unusable_wait_timeout_values_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    for value in ("nan", "inf", "-1"):
        monkeypatch.setenv("LOCK_WAIT_TIMEOUT_SECONDS", value)
        with pytest.raises(ValueError, match="LOCK_WAIT_TIMEOUT_SECONDS"):
            install_engine._lock_timing_from_env()


def test_a_zero_wait_timeout_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCK_WAIT_TIMEOUT_SECONDS", "0")
    assert install_engine._lock_timing_from_env() == 0.0


def test_lock_stale_seconds_is_no_longer_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """There is nothing left to stale-reclaim, so this environment variable is inert now --
    setting it must not raise or change the timeout that comes back."""
    monkeypatch.setenv("LOCK_STALE_SECONDS", "not-a-number-at-all")
    assert install_engine._lock_timing_from_env() == install_engine.DEFAULT_LOCK_WAIT_TIMEOUT_SECONDS


def test_pid_diagnostics_are_written_and_read_outside_the_locked_byte(tmp_path: Path) -> None:
    """Windows' `msvcrt.locking()` is mandatory: it blocks *reads* of the locked byte range
    from other handles, not just writes or further locks -- unlike POSIX flock, which is purely
    advisory and never interferes with plain reads/writes at all. `_write_holder_pid()`/
    `_read_holder_pid()` must agree on writing and reading the diagnostic text outside byte 0,
    the byte `_try_lock()` locks, so it stays visible to a waiter on every platform. This can't
    reproduce the Windows-only symptom (mandatory locking doesn't exist on POSIX), but it does
    guard the two functions from drifting to different offsets."""
    lock_path = install_engine._lock_path_for(tmp_path, "demo-skill")
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        install_engine._write_holder_pid(fd)
        raw = lock_path.read_bytes()
        assert raw[: install_engine._PID_TEXT_OFFSET] == b"\x00" * install_engine._PID_TEXT_OFFSET
        assert raw[install_engine._PID_TEXT_OFFSET :] == str(os.getpid()).encode("ascii")
        assert install_engine._read_holder_pid(fd) == str(os.getpid())
    finally:
        os.close(fd)
