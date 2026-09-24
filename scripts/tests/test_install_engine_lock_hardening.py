"""Regression tests for uninstall, leftover-sweep/backup-recovery, and presentation bugs a
fresh review of scripts/install_engine.py found. The lock mechanism itself (mutual exclusion,
timeouts, timing values) is covered in test_install_engine_locking.py."""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from scripts import install_engine
from scripts.install_engine import (
    InstallOutcome,
    _lock_timing_from_env,
    print_outcome,
    install_skill,
    uninstall_skill,
)

ROOT = Path(__file__).resolve().parents[2]
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal semantics")


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
    assert [p for p in dest_root.glob(".demo-skill.*") if p.name != ".demo-skill.lock"] == []


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


def _is_alive(pid: int) -> bool:
    """POSIX-only liveness probe for this file's own (posix_only) subprocess tests -- unrelated
    to locking, so it doesn't belong in install_engine.py itself."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


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
        while time.monotonic() < deadline and _is_alive(child_pid):
            time.sleep(0.05)
        assert not _is_alive(child_pid), "the orphaned engine kept running"
    finally:
        if child_pid and _is_alive(child_pid):
            os.kill(child_pid, signal.SIGKILL)
        if middle.poll() is None:
            middle.kill()


def test_a_dry_run_uninstall_creates_nothing_not_even_the_destination_root(tmp_path: Path) -> None:
    dest_root = tmp_path / "never-created"

    outcome = uninstall_skill("demo-skill", dest_root=dest_root, dry_run=True)

    assert outcome.status == "absent"
    assert not dest_root.exists()


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


def test_a_genuine_backup_is_kept_when_the_destination_is_present_but_unowned(tmp_path: Path) -> None:
    """The destination being *present* only proves the backup is an old copy when what's there is
    demonstrably this skill's own replacement install -- an unowned directory at the destination
    (someone else's files, a half-finished unrelated write) proves nothing either way, so the
    backup -- the only copy of the user's previous install -- must be kept, not discarded."""
    _, dest_root, skill_dest = _installed_skill(tmp_path)
    genuine = _backup_of_the_installed_skill(dest_root, skill_dest, "genuine1", "v1")
    shutil.rmtree(skill_dest)
    skill_dest.mkdir()
    (skill_dest / "not-a-manifest.txt").write_text("unrelated", encoding="utf-8")

    install_engine._recover_leftover_backups(dest_root, "demo-skill", skill_dest)

    assert genuine.exists(), "an unowned destination must not cause the backup to be discarded"
    assert (skill_dest / "not-a-manifest.txt").exists(), "the unowned destination itself is untouched"


@posix_only
def test_a_third_signal_during_the_uninstall_restore_still_forces_the_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, signal_sentinels: object
) -> None:
    """The restore-after-a-failed-move step runs under its own `_defer_interrupts()`, nested
    inside the outer `_sigterm_as_system_exit()` the whole uninstall runs under. The outer layer
    absorbs everything after its first signal with no way out -- `_defer_interrupts()`'s own
    3rd-signal force-quit is what gives a hung restore (a stuck filesystem, an uninterruptible
    rmtree) an escape hatch. Losing that wrapper silently removes the only escape for this step."""
    _, dest_root, skill_dest = _installed_skill(tmp_path)
    real_replace = os.replace
    calls = 0

    def replace_then_hang_then_signal_three_times(src: object, dst: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            real_replace(src, dst)  # the move-aside succeeds
            os.kill(os.getpid(), signal.SIGTERM)  # triggers the except-BaseException restore path
            time.sleep(0.2)
        else:
            for _ in range(3):  # the restore itself is "stuck": only repeated signals end it
                os.kill(os.getpid(), signal.SIGTERM)
                time.sleep(0.1)
            pytest.fail("os._exit should have ended the process before this point")  # pragma: no cover

    exit_calls: list[int] = []
    monkeypatch.setattr(
        install_engine.os,
        "_exit",
        lambda code: (exit_calls.append(code), (_ for _ in ()).throw(SystemExit(code)))[-1],
    )
    monkeypatch.setattr(install_engine.os, "replace", replace_then_hang_then_signal_three_times)
    with pytest.raises(SystemExit) as exc_info:
        uninstall_skill("demo-skill", dest_root=dest_root)
    assert exit_calls == [130], "the force-quit escape must still fire during this step"
    assert exc_info.value.code == 130


@posix_only
def test_a_signal_during_the_leftover_sweep_still_exits_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, signal_sentinels: object
) -> None:
    """`_sweep_leftovers`/`_recover_leftover_backups` run after `held_lock`'s own conversion has
    exited and before the primary work's -- unprotected, a signal there hits the default
    disposition (a raw 143/-15) instead of the engine's clean 130."""
    repo, dest_root, skill_dest = _installed_skill(tmp_path)

    def sweep_then_signal(dest_root: Path, skill: str) -> None:
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(0.2)

    monkeypatch.setattr(install_engine, "_sweep_leftovers", sweep_then_signal)
    with pytest.raises(SystemExit) as exc_info:
        install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")
    assert exc_info.value.code == 130

    def sweep_then_signal_uninstall(dest_root: Path, skill: str) -> None:
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(0.2)

    monkeypatch.setattr(install_engine, "_sweep_leftovers", sweep_then_signal_uninstall)
    with pytest.raises(SystemExit) as exc_info:
        uninstall_skill("demo-skill", dest_root=dest_root)
    assert exc_info.value.code == 130
