"""Regression tests for the lock, uninstall and presentation bugs a fresh review of
scripts/install_engine.py found: stale-lock reclaim breaking mutual exclusion, a reclaim that
could spin past the wait timeout, a leaked lock temp directory on interrupt, unbounded lock
timing values, a non-atomic uninstall, and output bound to the streams present at import."""

from __future__ import annotations

import contextlib
import io
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from scripts import install_engine
from scripts.install_engine import (
    InstallOutcome,
    LockTimeoutError,
    _acquire_lock_dir,
    _lock_timing_from_env,
    _print_outcome,
    held_lock,
    install_skill,
    is_pid_alive,
    uninstall_skill,
)

ROOT = Path(__file__).resolve().parents[2]
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal semantics")


def _seed_lock(dest_root: Path, skill: str, *, pid: str, acquired_at: str) -> Path:
    lock_dir = dest_root / f".{skill}.lock"
    lock_dir.mkdir()
    (lock_dir / "pid").write_text(pid, encoding="utf-8")
    (lock_dir / "acquired_at").write_text(acquired_at, encoding="utf-8")
    return lock_dir


# --- mutual exclusion under contention ------------------------------------------------------

_HAMMER = textwrap.dedent(
    """
    import os, sys, time
    from pathlib import Path
    sys.path.insert(0, {root!r})
    from scripts import install_engine
    from scripts.install_engine import held_lock

    install_engine._LOCK_POLL_INTERVAL_SECONDS = 0.005
    dest = Path({dest!r})
    marker = dest / "in-critical-section"
    collisions = 0
    for _ in range({iterations}):
        with held_lock(dest, "demo-skill", wait_timeout=60.0, stale_after=300.0):
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


@posix_only
def test_two_holders_are_never_inside_the_critical_section_together(tmp_path: Path) -> None:
    """A waiter that lost the race to a holder's release used to read the vanished lock as
    "unreadable, therefore stale" and rename whatever a third party had just acquired -- so two
    processes ran their critical sections at once. Seeded with a dead-pid lock as well, so the
    reclaim path itself is exercised."""
    _seed_lock(tmp_path, "demo-skill", pid="999999999", acquired_at=str(time.time()))
    code = _HAMMER.format(root=str(ROOT), dest=str(tmp_path), iterations=25)
    procs = [
        subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        for _ in range(6)
    ]
    collisions = 0
    for proc in procs:
        out, _ = proc.communicate(timeout=120)
        assert proc.returncode == 0
        collisions += int(out.strip())
    assert collisions == 0


def test_a_lock_that_vanishes_between_the_failed_acquire_and_the_read_is_not_reclaimed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """"Gone" is not "abandoned". The holder released between our failed acquire and our read
    of it; reclaiming now would rename whatever a third party has acquired since."""
    monkeypatch.setattr(install_engine, "_LOCK_POLL_INTERVAL_SECONDS", 0.001)
    real_acquire = install_engine._acquire_lock_dir
    calls = 0

    def acquire_losing_once(dest_root: Path, lock_dir: Path) -> bool:
        nonlocal calls
        calls += 1
        return False if calls == 1 else real_acquire(dest_root, lock_dir)

    reclaims: list[object] = []
    monkeypatch.setattr(install_engine, "_acquire_lock_dir", acquire_losing_once)
    monkeypatch.setattr(install_engine, "_reclaim_stale_lock", lambda *a, **k: reclaims.append(a) or True)

    with held_lock(tmp_path, "demo-skill", wait_timeout=5.0):
        pass

    assert calls == 2
    assert reclaims == []


def test_reclaim_puts_back_a_lock_that_is_not_the_one_judged_stale(tmp_path: Path) -> None:
    lock_dir = _seed_lock(tmp_path, "s", pid=str(os.getpid()), acquired_at=str(time.time()))
    observed = ("999999999", "1.0")  # what the caller saw before another holder took over

    assert install_engine._reclaim_stale_lock(lock_dir, observed) is False

    assert (lock_dir / "pid").read_text(encoding="utf-8") == str(os.getpid())
    assert list(tmp_path.glob(".s.lock.stale.*")) == []


def test_reclaim_removes_the_lock_that_was_judged_stale(tmp_path: Path) -> None:
    lock_dir = _seed_lock(tmp_path, "s", pid="999999999", acquired_at="1.0")

    assert install_engine._reclaim_stale_lock(lock_dir, ("999999999", "1.0")) is True

    assert not lock_dir.exists()
    assert list(tmp_path.glob(".s.lock.stale.*")) == []


def test_a_failing_reclaim_rename_counts_toward_the_timeout_instead_of_spinning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_lock(tmp_path, "demo-skill", pid="999999999", acquired_at=str(time.time()))
    monkeypatch.setattr(install_engine, "_LOCK_POLL_INTERVAL_SECONDS", 0.05)
    attempts = 0
    real_rename = os.rename

    def rename(src: object, dst: object) -> None:
        nonlocal attempts
        if ".stale." in str(dst):
            attempts += 1
            raise PermissionError(1, "Operation not permitted")
        real_rename(src, dst)

    monkeypatch.setattr(install_engine.os, "rename", rename)

    start = time.monotonic()
    with pytest.raises(LockTimeoutError):
        with held_lock(tmp_path, "demo-skill", wait_timeout=0.3):
            pass
    assert time.monotonic() - start < 5.0
    assert attempts < 50  # bounded by the poll interval, not a hot loop


def test_a_leftover_stale_directory_from_the_same_pid_does_not_block_a_reclaim(tmp_path: Path) -> None:
    """The stale name used to be `<lock>.stale.<pid>`; a non-empty leftover under that exact
    name (a killed run with the same pid, common in containers) made every later reclaim's
    rename fail forever."""
    _seed_lock(tmp_path, "demo-skill", pid="999999999", acquired_at=str(time.time()))
    leftover = tmp_path / f".demo-skill.lock.stale.{os.getpid()}"
    leftover.mkdir()
    (leftover / "pid").write_text("1", encoding="utf-8")

    start = time.monotonic()
    with held_lock(tmp_path, "demo-skill", wait_timeout=10.0):
        pass
    assert time.monotonic() - start < 5.0


# --- pid handling ---------------------------------------------------------------------------


@pytest.mark.parametrize("pid", [0, -1, 10**30])
def test_is_pid_alive_rejects_pids_that_cannot_name_a_process(pid: int) -> None:
    assert is_pid_alive(pid) is False


def test_a_lock_file_holding_an_absurd_pid_is_stale_not_a_crash(tmp_path: Path) -> None:
    _seed_lock(tmp_path, "demo-skill", pid="99999999999999999999", acquired_at=str(time.time()))
    with held_lock(tmp_path, "demo-skill", wait_timeout=10.0):
        pass


# --- interrupts around acquisition ----------------------------------------------------------


def test_an_interrupt_between_creating_and_publishing_the_lock_leaves_no_temp_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def rename(src: object, dst: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(install_engine.os, "rename", rename)
    with pytest.raises(KeyboardInterrupt):
        _acquire_lock_dir(tmp_path, tmp_path / ".demo-skill.lock")
    assert list(tmp_path.glob(".demo-skill.lock.tmp.*")) == []


@posix_only
def test_sigterm_while_waiting_for_a_live_lock_exits_130_and_leaves_that_lock_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, signal_sentinels: object
) -> None:
    holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        lock_dir = _seed_lock(tmp_path, "demo-skill", pid=str(holder.pid), acquired_at=str(time.time()))
        real_sleep = time.sleep
        sent = False

        def sleep_and_signal(seconds: float) -> None:
            nonlocal sent
            if not sent:
                sent = True
                os.kill(os.getpid(), signal.SIGTERM)
            real_sleep(seconds)

        monkeypatch.setattr(install_engine.time, "sleep", sleep_and_signal)
        with pytest.raises(SystemExit) as exc_info:
            with held_lock(tmp_path, "demo-skill", wait_timeout=30.0):
                pass  # pragma: no cover
        assert exc_info.value.code == 130
        # The lock belongs to another process: this call never acquired it, so it must not
        # release it on the way out.
        assert (lock_dir / "pid").read_text(encoding="utf-8") == str(holder.pid)
    finally:
        holder.terminate()
        holder.wait(timeout=5)


# --- lock timing from the environment -------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("LOCK_WAIT_TIMEOUT_SECONDS", "nan"),
        ("LOCK_WAIT_TIMEOUT_SECONDS", "inf"),
        ("LOCK_WAIT_TIMEOUT_SECONDS", "-1"),
        ("LOCK_STALE_SECONDS", "nan"),
        ("LOCK_STALE_SECONDS", "0"),
        ("LOCK_STALE_SECONDS", "-5"),
    ],
)
def test_unusable_lock_timing_values_are_rejected(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        _lock_timing_from_env()


def test_a_zero_wait_timeout_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCK_WAIT_TIMEOUT_SECONDS", "0")
    assert _lock_timing_from_env()[0] == 0.0


# --- uninstall ------------------------------------------------------------------------------


def _installed_skill(tmp_path: Path) -> tuple[Path, Path, Path]:
    from scripts.tests.test_install_engine_install import _minimal_repo

    repo = _minimal_repo(tmp_path)
    dest_root = tmp_path / "dest"
    outcome = install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")
    assert outcome.status == "installed"
    return repo, dest_root, dest_root / "demo-skill"


def test_a_failed_uninstall_deletion_leaves_the_destination_absent_not_wedged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An in-place rmtree that failed partway left a directory whose manifest was already gone,
    classified "unowned" -- so neither uninstall nor install would touch it again."""
    repo, dest_root, skill_dest = _installed_skill(tmp_path)
    real_rmtree = install_engine.shutil.rmtree

    def failing_rmtree(path: object, *args: object, **kwargs: object) -> None:
        if ".removing." in str(path) and not kwargs.get("ignore_errors"):
            raise PermissionError(13, "Permission denied")
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(install_engine.shutil, "rmtree", failing_rmtree)
    outcome = uninstall_skill("demo-skill", dest_root=dest_root)

    assert outcome.status == "failed"
    assert "could not delete the leftover" in outcome.message
    assert not skill_dest.exists()

    monkeypatch.undo()
    assert install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor").status == "installed"


@posix_only
def test_sigterm_during_uninstall_deletion_is_deferred_until_it_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, signal_sentinels: object
) -> None:
    _, dest_root, skill_dest = _installed_skill(tmp_path)
    real_rmtree = install_engine.shutil.rmtree
    fired = False

    def rmtree_with_signal(path: object, *args: object, **kwargs: object) -> None:
        nonlocal fired
        if not fired and ".removing." in str(path):
            fired = True
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(0.2)
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(install_engine.shutil, "rmtree", rmtree_with_signal)
    with pytest.raises(SystemExit) as exc_info:
        uninstall_skill("demo-skill", dest_root=dest_root)

    assert exc_info.value.code == 130
    assert not skill_dest.exists()
    assert list(dest_root.glob(".demo-skill.*")) == []


@posix_only
def test_sigterm_before_the_uninstall_move_completes_restores_the_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, signal_sentinels: object
) -> None:
    _, dest_root, skill_dest = _installed_skill(tmp_path)
    real_replace = os.replace

    def replace_then_signal(src: object, dst: object) -> None:
        real_replace(src, dst)
        if ".removing." in str(dst):
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(0.2)

    monkeypatch.setattr(install_engine.os, "replace", replace_then_signal)
    with pytest.raises(SystemExit) as exc_info:
        uninstall_skill("demo-skill", dest_root=dest_root)

    assert exc_info.value.code == 130
    assert (skill_dest / "SKILL.md").exists()  # interrupted before it finished: still installed
    assert list(dest_root.glob(".demo-skill.removing.*")) == []


# --- presentation ---------------------------------------------------------------------------


def test_outcomes_are_written_to_the_streams_current_at_print_time() -> None:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        _print_outcome(InstallOutcome("s", Path("/x"), "installed", "Installed s"))
        _print_outcome(InstallOutcome("s", Path("/x"), "failed", "boom"))
    assert out.getvalue() == "Installed s\n"
    assert err.getvalue() == "error: boom\n"


def test_main_runs_with_streams_that_cannot_be_reconfigured(tmp_path: Path) -> None:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = install_engine.main(["uninstall", "demo-skill", str(tmp_path)])
    assert code == 0
    assert "not installed" in err.getvalue()


def test_an_empty_skill_name_is_rejected(tmp_path: Path) -> None:
    outcome = uninstall_skill("", dest_root=tmp_path)
    assert outcome.status == "failed"
    assert not (tmp_path / ".lock").exists()
