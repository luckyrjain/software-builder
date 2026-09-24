"""Regression tests for the lock, uninstall and presentation bugs a fresh review of
scripts/install_engine.py found: stale-lock reclaim breaking mutual exclusion, a reclaim that
could spin past the wait timeout, a leaked lock temp directory on interrupt, unbounded lock
timing values, a non-atomic uninstall, and output bound to the streams present at import."""

from __future__ import annotations

import contextlib
import io
import os
import shutil
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
    print_outcome,
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
    try:
        for proc in procs:
            out, _ = proc.communicate(timeout=120)
            assert proc.returncode == 0
            collisions += int(out.strip())
    finally:
        for proc in procs:  # a timeout must not leave hammer processes spinning
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)
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
    sleeps: list[float] = []
    monkeypatch.setattr(install_engine.time, "sleep", sleeps.append)
    monkeypatch.setattr(install_engine, "_acquire_lock_dir", acquire_losing_once)
    monkeypatch.setattr(install_engine, "_reclaim_stale_lock", lambda *a, **k: reclaims.append(a) or True)

    with held_lock(tmp_path, "demo-skill", wait_timeout=5.0):
        pass

    assert calls == 2
    assert reclaims == []
    assert sleeps == []  # retried the acquire straight away, as for any released lock


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
        print_outcome(InstallOutcome("s", Path("/x"), "installed", "Installed s"))
        print_outcome(InstallOutcome("s", Path("/x"), "failed", "boom"))
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


def test_an_empty_lock_directory_is_removed_when_the_rename_will_not_absorb_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows refuses to rename onto any existing directory (POSIX silently replaces an empty
    one), so an empty leftover lock -- an interrupted release -- used to be waited on until it
    aged out. A lock is only ever published populated, so an empty one is vacated: remove it.
    Forced here by making the first acquire fail the way Windows' rename does."""
    lock_dir = tmp_path / ".demo-skill.lock"
    lock_dir.mkdir()
    real_acquire = install_engine._acquire_lock_dir
    calls = 0

    def acquire_refused_once(dest_root: Path, target: Path) -> bool:
        nonlocal calls
        calls += 1
        return False if calls == 1 else real_acquire(dest_root, target)

    monkeypatch.setattr(install_engine, "_acquire_lock_dir", acquire_refused_once)
    sleeps: list[float] = []
    monkeypatch.setattr(install_engine.time, "sleep", sleeps.append)
    reclaims: list[object] = []
    monkeypatch.setattr(install_engine, "_reclaim_stale_lock", lambda *a, **k: reclaims.append(a) or True)

    with held_lock(tmp_path, "demo-skill", wait_timeout=5.0):
        assert (lock_dir / "pid").exists()
    assert calls == 2
    assert sleeps == []  # removed and retried straight away, not waited on
    assert reclaims == []  # a rename-based reclaim could take a live lock; rmdir cannot


def test_removing_an_empty_lock_dir_can_never_take_a_populated_one(tmp_path: Path) -> None:
    lock_dir = _seed_lock(tmp_path, "s", pid=str(os.getpid()), acquired_at=str(time.time()))
    assert install_engine._remove_empty_dir(lock_dir) is False
    assert (lock_dir / "pid").exists()


def test_a_bad_lock_timing_value_names_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCK_WAIT_TIMEOUT_SECONDS", "abc")
    with pytest.raises(ValueError, match="LOCK_WAIT_TIMEOUT_SECONDS must be a number, got 'abc'"):
        _lock_timing_from_env()


@posix_only
def test_a_second_sigterm_during_the_uninstall_restore_does_not_strand_the_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, signal_sentinels: object
) -> None:
    """The restore that undoes a half-done uninstall used to run with the conversion handler
    still active, so a second signal interrupted it and left the install in the hidden
    `.removing.*` directory."""
    _, dest_root, skill_dest = _installed_skill(tmp_path)
    real_replace = os.replace
    calls = 0

    def replace_signalling_twice(src: object, dst: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:  # the move aside: complete it, then interrupt
            real_replace(src, dst)
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(0.2)
        elif calls == 2:  # the restore: a second signal lands right before it runs
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(0.2)
            real_replace(src, dst)
        else:
            real_replace(src, dst)

    monkeypatch.setattr(install_engine.os, "replace", replace_signalling_twice)
    with pytest.raises(SystemExit) as exc_info:
        uninstall_skill("demo-skill", dest_root=dest_root)

    assert exc_info.value.code == 130
    assert (skill_dest / "SKILL.md").exists()
    assert list(dest_root.glob(".demo-skill.removing.*")) == []


_SUFFIX = "abcd1234"  # what tempfile.mkdtemp appends: 8 characters of [a-z0-9_]


def _leftover(dest_root: Path, skill: str, kind: str, suffix: str = _SUFFIX) -> Path:
    path = dest_root / f".{skill}.{kind}.{suffix}"
    path.mkdir(parents=True)
    return path


def _backup_of_the_installed_skill(dest_root: Path, skill_dest: Path, suffix: str, version: str) -> Path:
    """A `.demo-skill.backup.<suffix>` holding a genuine (manifest-bearing) copy of the install."""
    backup = _leftover(dest_root, "demo-skill", "backup", suffix)
    shutil.copytree(skill_dest, backup / "skill")
    (backup / "skill" / "VERSION").write_text(version, encoding="utf-8")
    return backup


def test_leftover_removing_and_staging_dirs_are_swept_on_the_next_run(tmp_path: Path) -> None:
    repo, dest_root, skill_dest = _installed_skill(tmp_path)
    removing = _leftover(dest_root, "demo-skill", "removing")
    (removing / "skill").mkdir()
    (removing / "skill" / "SKILL.md").write_text("x", encoding="utf-8")
    staging = _leftover(dest_root, "demo-skill", "staging")
    other = _leftover(dest_root, "other-skill", "removing")

    assert install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor").status == "installed"

    assert not removing.exists() and not staging.exists()
    assert other.exists(), "only this skill's leftovers"


def test_directories_that_merely_look_like_leftovers_are_never_touched(tmp_path: Path) -> None:
    """Sweeps matched by name prefix, so a user's own `.demo-skill.staging.notes` was deleted and
    `.demo-skill.backup.mine/skill` was moved in as the install. Only the exact
    `.<skill>.<kind>.<8 mkdtemp characters>` shape is ours."""
    repo, dest_root, skill_dest = _installed_skill(tmp_path)
    lookalikes = [
        _leftover(dest_root, "demo-skill", "staging", "notes"),
        _leftover(dest_root, "demo-skill", "removing", "old"),
        _leftover(dest_root, "demo-skill", "backup", "mine"),
        _leftover(dest_root, "demo-skill", "staging", "abcd1234.extra"),
        _leftover(dest_root, "demo-skill", "lock.tmp", "keepme"),
    ]
    for d in lookalikes:
        (d / "skill").mkdir()
        (d / "skill" / "user-file").write_text("precious", encoding="utf-8")

    assert install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor").status == "installed"
    assert uninstall_skill("demo-skill", dest_root=dest_root).status == "uninstalled"
    # ...and again with the skill absent, when a matching backup would be "restored".
    assert uninstall_skill("demo-skill", dest_root=dest_root).status == "absent"

    for d in lookalikes:
        assert (d / "skill" / "user-file").read_text(encoding="utf-8") == "precious", d.name
    assert not (dest_root / "demo-skill").exists()


def test_a_skill_whose_id_extends_another_ids_prefix_is_not_swept(tmp_path: Path) -> None:
    """Skill `x` must not sweep the working directories of a skill called `x.staging.y`
    (`.x.staging.y.staging.q1abcdef`), nor its lock, nor treat its installed directory as a backup."""
    dest_root = tmp_path / "dest"
    dest_root.mkdir()
    sibling_staging = dest_root / ".x.staging.y.staging.q1abcdef"
    sibling_lock = dest_root / ".x.staging.y.lock"
    sibling_backup = dest_root / ".x.backup.z.backup.q1abcdef"
    for d in (sibling_staging, sibling_lock, sibling_backup):
        d.mkdir()
        (d / "keep").write_text("live", encoding="utf-8")

    install_engine._sweep_leftovers(dest_root, "x")
    install_engine._recover_leftover_backups(dest_root, "x", dest_root / "x")

    for d in (sibling_staging, sibling_lock, sibling_backup):
        assert (d / "keep").exists(), d.name


def test_a_previous_install_displaced_by_a_hard_kill_is_restored_on_the_next_run(tmp_path: Path) -> None:
    """SIGKILL or power loss between moving the old install aside and finishing the replacement
    leaves the skill only inside `.{skill}.backup.*`, nothing at the destination."""
    repo, dest_root, skill_dest = _installed_skill(tmp_path)
    backup = _leftover(dest_root, "demo-skill", "backup")
    os.replace(skill_dest, backup / "skill")  # what the killed run left behind
    assert not skill_dest.exists()

    outcome = uninstall_skill("demo-skill", dest_root=dest_root, dry_run=True)  # a dry run restores nothing
    assert outcome.status == "absent" and not skill_dest.exists()

    outcome = uninstall_skill("demo-skill", dest_root=dest_root)  # restores it, then removes it
    assert outcome.status == "uninstalled"
    assert list(dest_root.glob(".demo-skill.backup.*")) == []


def test_a_displaced_install_is_put_back_by_an_install_that_then_replaces_it(tmp_path: Path) -> None:
    repo, dest_root, skill_dest = _installed_skill(tmp_path)
    backup = _leftover(dest_root, "demo-skill", "backup")
    os.replace(skill_dest, backup / "skill")

    assert install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor").status == "installed"

    assert (skill_dest / "SKILL.md").exists()
    assert list(dest_root.glob(".demo-skill.backup.*")) == []


def test_with_two_leftover_backups_the_newest_is_the_one_restored(tmp_path: Path) -> None:
    """scandir order is arbitrary; restoring the older backup and then deleting the newer one as
    "an old copy" would silently roll the user back a version."""
    repo, dest_root, skill_dest = _installed_skill(tmp_path)
    older = _backup_of_the_installed_skill(dest_root, skill_dest, "zzzzzzzz", "v1")  # sorts LAST by name
    newer = _backup_of_the_installed_skill(dest_root, skill_dest, "aaaaaaaa", "v2")  # sorts FIRST by name
    now = time.time()
    os.utime(older, (now - 100, now - 100))
    os.utime(newer, (now - 10, now - 10))
    shutil.rmtree(skill_dest)

    install_engine._recover_leftover_backups(dest_root, "demo-skill", skill_dest)

    assert (skill_dest / "VERSION").read_text(encoding="utf-8") == "v2"
    assert list(dest_root.glob(".demo-skill.backup.*")) == []


def test_a_backup_is_dropped_only_when_the_install_it_protects_is_in_place(tmp_path: Path) -> None:
    repo, dest_root, skill_dest = _installed_skill(tmp_path)
    stale = _backup_of_the_installed_skill(dest_root, skill_dest, "olddddd1", "old")

    install_engine._recover_leftover_backups(dest_root, "demo-skill", skill_dest)
    assert not stale.exists(), "the replacement is complete and owned: the backup is an old copy"

    # An unowned directory at the destination proves nothing about the backup: keep it.
    unowned_dest = dest_root / "other"
    unowned_dest.mkdir()
    (unowned_dest / "README").write_text("not ours", encoding="utf-8")
    kept = _leftover(dest_root, "other", "backup", "keptdddd")
    shutil.copytree(skill_dest, kept / "skill")
    install_engine._recover_leftover_backups(dest_root, "other", unowned_dest)
    assert kept.exists()


def test_a_backup_that_is_not_an_install_of_this_skill_is_left_alone(tmp_path: Path) -> None:
    _, dest_root, skill_dest = _installed_skill(tmp_path)
    shutil.rmtree(skill_dest)
    foreign = _leftover(dest_root, "demo-skill", "backup")
    (foreign / "skill").mkdir()
    (foreign / "skill" / "notes.txt").write_text("not a skill", encoding="utf-8")

    install_engine._recover_leftover_backups(dest_root, "demo-skill", skill_dest)

    assert not skill_dest.exists(), "a directory with no manifest must not be installed as the skill"
    assert (foreign / "skill" / "notes.txt").exists()


def test_uninstall_sweeps_leftovers_even_when_the_skill_is_already_absent(tmp_path: Path) -> None:
    dest_root = tmp_path / "dest"
    leftover = _leftover(dest_root, "demo-skill", "removing") if dest_root.mkdir() is None else None
    (leftover / "skill").mkdir()
    (leftover / "skill" / "SKILL.md").write_text("x", encoding="utf-8")

    outcome = uninstall_skill("demo-skill", dest_root=dest_root)

    assert outcome.status == "absent"
    assert not leftover.exists()


def test_a_removing_directory_holding_more_than_the_moved_skill_is_left_alone(tmp_path: Path) -> None:
    dest_root = tmp_path / "dest"
    dest_root.mkdir()
    odd = _leftover(dest_root, "demo-skill", "removing")
    (odd / "notes").write_text("user data", encoding="utf-8")

    uninstall_skill("demo-skill", dest_root=dest_root)

    assert (odd / "notes").exists()


def test_a_dry_run_uninstall_sweeps_nothing(tmp_path: Path) -> None:
    _, dest_root, _ = _installed_skill(tmp_path)
    leftover = dest_root / ".demo-skill.removing.abc"
    leftover.mkdir()

    assert uninstall_skill("demo-skill", dest_root=dest_root, dry_run=True).status == "dry_run"
    assert leftover.exists()


def test_an_old_orphaned_lock_temp_dir_is_swept_but_a_fresh_one_is_not(tmp_path: Path) -> None:
    """`_acquire_lock_dir()`'s temp dir exists for microseconds, so a fresh one may belong to a
    live acquire; only one older than any acquire could be is an orphan of a hard kill."""
    dest_root = tmp_path / "dest"
    old = dest_root / ".demo-skill.lock.tmp.oldddddd"
    fresh = dest_root / ".demo-skill.lock.tmp.freshhhh"
    other = dest_root / ".other-skill.lock.tmp.oldddddd"
    for d in (old, fresh, other):
        d.mkdir(parents=True)
    ancient = time.time() - 2 * install_engine._ORPHAN_LOCK_TMP_MIN_AGE_SECONDS
    os.utime(old, (ancient, ancient))
    os.utime(other, (ancient, ancient))

    assert uninstall_skill("demo-skill", dest_root=dest_root).status == "absent"

    assert not old.exists()
    assert fresh.exists()
    assert other.exists(), "only this skill's leftovers"


@posix_only
def test_the_engine_stops_when_its_parent_is_killed(tmp_path: Path) -> None:
    """install.sh being SIGKILLed cannot be trapped; the engine it started used to be orphaned
    and run on, holding the lock. With the opt-in parent watch it terminates itself."""
    child_code = (
        "import os, sys, time; sys.path.insert(0, %r);"
        "from scripts import install_engine;"
        "install_engine._start_parent_watch(os.getppid(), 0.05);"
        "print('ready', flush=True); time.sleep(60)" % str(ROOT)
    )
    middle_code = (
        "import subprocess, sys, time;"
        "p = subprocess.Popen([sys.executable, '-c', %r], stdout=subprocess.PIPE, text=True);"
        "p.stdout.readline();"
        "print(p.pid, flush=True); time.sleep(60)" % child_code
    )
    middle = subprocess.Popen([sys.executable, "-c", middle_code], stdout=subprocess.PIPE, text=True)
    child_pid = 0
    try:
        child_pid = int(middle.stdout.readline())
        middle.kill()  # SIGKILL: nothing can trap it
        middle.wait(timeout=10)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and install_engine.is_pid_alive(child_pid):
            time.sleep(0.05)
        assert not install_engine.is_pid_alive(child_pid), "the orphaned engine kept running"
    finally:
        if child_pid and install_engine.is_pid_alive(child_pid):
            os.kill(child_pid, signal.SIGKILL)
        if middle.poll() is None:
            middle.kill()


def test_a_dry_run_uninstall_creates_nothing_not_even_the_destination_root(tmp_path: Path) -> None:
    dest_root = tmp_path / "never-created"

    outcome = uninstall_skill("demo-skill", dest_root=dest_root, dry_run=True)

    assert outcome.status == "absent"
    assert not dest_root.exists()


def test_an_acquire_whose_temp_dir_was_swept_meanwhile_loses_the_round_instead_of_failing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A clock far ahead of the filesystem's can make a *live* lock temp dir look orphaned, so a
    concurrent sweep removes it; the acquire's rename then fails ENOENT. That is a lost round to
    retry, not an error to report."""
    real_rename = os.rename

    def rename_after_a_sweep(src: object, dst: object) -> None:
        shutil.rmtree(src)  # the sweep, landing between mkdtemp and the rename
        real_rename(src, dst)

    monkeypatch.setattr(install_engine.os, "rename", rename_after_a_sweep)

    assert _acquire_lock_dir(tmp_path, tmp_path / ".demo-skill.lock") is False
    assert list(tmp_path.glob(".demo-skill.lock*")) == []


@posix_only
def test_the_engine_stops_immediately_if_the_parent_died_before_startup_finished(tmp_path: Path) -> None:
    """A kill landing while the engine is still starting up (importing, before it would have
    taken a late os.getppid() snapshot) must be caught too, not just one after startup -- the
    watch is given the expected parent pid up front rather than reading it late."""
    import scripts.install_engine as install_engine_module

    stopped = []
    monkeypatch_pid = os.getpid() + 999999  # never this process's real parent
    real_kill = os.kill

    def fake_kill(pid: int, sig: int) -> None:
        if pid == os.getpid() and sig == signal.SIGTERM:
            stopped.append(True)
            return  # don't actually signal this test process
        real_kill(pid, sig)

    orig_kill = install_engine_module.os.kill
    install_engine_module.os.kill = fake_kill
    try:
        install_engine_module._start_parent_watch(monkeypatch_pid, poll_seconds=10.0)
    finally:
        install_engine_module.os.kill = orig_kill
    assert stopped == [True]
