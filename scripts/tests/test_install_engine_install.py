"""Tests for scripts/install_engine.py's install_skill() -- mirrors the rollback and
same-filesystem-staging scenarios scripts/tests/test_install_rollback.py and
scripts/tests/test_install_concurrency.py already lock in for install.sh."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

from scripts import install_engine
from scripts.install_engine import install_skill

ROOT = Path(__file__).resolve().parents[2]


def _minimal_repo(tmp_path: Path, *, skill_id: str = "demo-skill", broken: bool = False) -> Path:
    """A minimal, self-contained repo root with one registered skill -- valid enough for
    package_skill() to package it and (unless broken=True) for validate_tree() to accept it.

    Mirrors test_install_rollback.py's real fixture-building approach: a fresh git repository
    (package_skill.py's release provenance shells out to `git rev-parse HEAD`, so an
    uncommitted tree fails packaging outright) with a *flat* skill directory (`repo/<skill_id>`,
    not the nested `repo/skills/<skill_id>` the brief's own illustrative template used) and a
    plain YAML skills.yaml (not JSON) -- matching the shape entry.path defaults to (skill_id
    itself) in scripts/registry/paths.py's skill_dir(). Unlike test_install_rollback.py's own
    fixture (which drives the real install.sh via subprocess, and so also needs its own copies
    of scripts/, agent-hosts.yaml, and a scripts/registry/skills.d/ fragment for install.sh's
    shelled-out Python to find), install_skill() here is called in-process against this
    checkout's own scripts.registry.schema module, so none of that copying is needed -- only a
    skills.yaml entry with every field _parse_skill_entry requires (schema.py falls back to the
    default {cursor, claude, kiro} host set when no sibling agent-hosts.yaml exists, and each of
    those three hosts' block is mandatory regardless of which ones are actually declared).
    """
    repo = tmp_path / "repo"
    skill_dir = repo / skill_id
    skill_dir.mkdir(parents=True)
    if broken:
        (skill_dir / "SKILL.md").write_text(
            "---\nname: demo-skill\ndescription: Demo test skill.\n---\n\n"
            "See [missing](reference/missing.md)\n",
            encoding="utf-8",
        )
    else:
        (skill_dir / "SKILL.md").write_text(
            "---\nname: demo-skill\ndescription: Demo test skill.\n---\n\n"
            "A minimal test skill.\n",
            encoding="utf-8",
        )
    (repo / "skills.yaml").write_text(
        f"""schema_version: 1
skills:
  {skill_id}:
    invocation: ambient
    hosts:
      cursor: {{discovery: manual}}
      claude: {{install: true}}
      kiro: {{discovery: manual}}
    install:
      requires: []
    lint:
      skill_md_max_lines: 180
      target: {skill_id}
    risk_class: [read-only]
""",
        encoding="utf-8",
    )
    (repo / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    # -c commit.gpgsign=false: don't depend on the invoking machine's global Git signing
    # config (commit signing turned on would otherwise block this fixture commit on a
    # passphrase/hardware-key prompt or fail outright).
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], cwd=repo, check=True
    )
    return repo


def test_install_succeeds_into_an_empty_destination(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    dest_root = tmp_path / "dest"

    outcome = install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert outcome.status == "installed"
    assert (dest_root / "demo-skill" / "SKILL.md").is_file()
    assert (dest_root / "demo-skill" / ".software-builder-manifest.json").is_file()


def test_dry_run_makes_no_filesystem_changes(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    dest_root = tmp_path / "dest"

    outcome = install_skill(
        "demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor", dry_run=True
    )

    assert outcome.status == "dry_run"
    assert not (dest_root / "demo-skill").exists()


def test_validation_failure_restores_previous_install_unchanged(tmp_path: Path) -> None:
    """Mirrors test_install_rollback.py's test_install_restores_previous_package_when_validation_fails:
    a pre-existing, software-builder-owned install with a marker file must survive a failed
    (broken-link) install byte-for-byte."""
    repo = _minimal_repo(tmp_path, broken=True)
    dest_root = tmp_path / "dest"
    existing = dest_root / "demo-skill"
    existing.mkdir(parents=True)
    (existing / "SKILL.md").write_text("# Previous good install\n", encoding="utf-8")
    (existing / "KEEP_ME.txt").write_text("do not touch\n", encoding="utf-8")
    (existing / ".software-builder-manifest.json").write_text(
        json.dumps({"manifest_version": 1, "skill": "demo-skill", "files": {}}), encoding="utf-8"
    )

    outcome = install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert outcome.status == "failed"
    assert (existing / "KEEP_ME.txt").read_text(encoding="utf-8") == "do not touch\n"
    assert (existing / "SKILL.md").read_text(encoding="utf-8") == "# Previous good install\n"
    # no leftover staging/backup directories
    assert not list(dest_root.glob(".demo-skill.staging.*"))
    assert not list(dest_root.glob(".demo-skill.backup.*"))
    assert not list(dest_root.glob(".demo-skill.lock*"))


def test_reinstall_backup_survives_a_missing_system_tmp_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mirrors test_install_concurrency.py's test_reinstall_backup_survives_a_missing_system_tmp_dir:
    proves staging/backup directories are created under dest_root, never under $TMPDIR, by
    pointing TMPDIR at a path that does not exist and confirming install still succeeds."""
    repo = _minimal_repo(tmp_path)
    dest_root = tmp_path / "dest"
    existing = dest_root / "demo-skill"
    existing.mkdir(parents=True)
    (existing / "SKILL.md").write_text("# Old\n", encoding="utf-8")
    (existing / ".software-builder-manifest.json").write_text(
        json.dumps({"manifest_version": 1, "skill": "demo-skill", "files": {}}), encoding="utf-8"
    )
    monkeypatch.setenv("TMPDIR", str(tmp_path / "does-not-exist"))

    outcome = install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert outcome.status == "installed"
    assert (
        dest_root / "demo-skill" / "SKILL.md"
    ).read_text(encoding="utf-8") == "---\nname: demo-skill\ndescription: Demo test skill.\n---\n\nA minimal test skill.\n"


def test_keyboard_interrupt_during_staging_propagates_after_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """install.sh's own INT/TERM trap (on_install_interrupt) runs cleanup_failed_install()
    and then `exit 130`, terminating the whole process -- it does NOT fall through to
    per-skill failure bookkeeping and continue to the next skill, the way an ordinary
    validation failure (a plain `return 1`) does. A Ctrl-C mid-install must behave the same
    way here: cleanup still runs, but the interrupt propagates out of install_skill() instead
    of being swallowed into a normal InstallOutcome(status="failed", ...) that a future
    multi-skill caller could mistake for just one more failed skill."""
    repo = _minimal_repo(tmp_path)
    dest_root = tmp_path / "dest"

    seen_stage_dirs: list[Path] = []

    def _interrupt(stage_dir: Path, **_kwargs: object) -> list[str]:
        seen_stage_dirs.append(stage_dir)
        raise KeyboardInterrupt

    monkeypatch.setattr(install_engine, "validate_tree", _interrupt)

    with pytest.raises(KeyboardInterrupt):
        install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert seen_stage_dirs, "validate_tree was never reached"
    # cleanup ran before propagating: the staging dir is gone, nothing landed at the
    # destination, and held_lock's own finally released the lock.
    assert not seen_stage_dirs[0].exists()
    assert not (dest_root / "demo-skill").exists()
    assert not list(dest_root.glob(".demo-skill.lock*"))


@pytest.mark.skipif(sys.platform == "win32", reason="os.kill(pid, SIGTERM) bypasses Python's signal module on Windows")
def test_sigterm_during_staging_runs_cleanup_and_exits_130(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real SIGTERM (not KeyboardInterrupt) delivered mid-staging must run the same cleanup
    as the KeyboardInterrupt test above -- install.sh's deleted bash trap used to handle both
    INT and TERM identically, and _sigterm_as_system_exit() is what restores that parity.
    Delivers a genuine OS signal via os.kill (not a direct `raise`), so this actually exercises
    signal registration/delivery/restoration, not just the exception-handling shape."""
    repo = _minimal_repo(tmp_path)
    dest_root = tmp_path / "dest"
    original_handler = signal.getsignal(signal.SIGTERM)

    seen_stage_dirs: list[Path] = []

    def _send_sigterm(stage_dir: Path, **_kwargs: object) -> list[str]:
        seen_stage_dirs.append(stage_dir)
        os.kill(os.getpid(), signal.SIGTERM)
        # Give the signal a chance to be delivered (checked between bytecode instructions)
        # before this fake validate_tree would otherwise return normally.
        time.sleep(1)
        return []  # pragma: no cover -- unreachable if the signal was delivered as expected

    monkeypatch.setattr(install_engine, "validate_tree", _send_sigterm)

    try:
        with pytest.raises(SystemExit) as exc_info:
            install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

        assert exc_info.value.code == 130
        assert seen_stage_dirs, "validate_tree was never reached"
        assert not seen_stage_dirs[0].exists()
        assert not (dest_root / "demo-skill").exists()
        assert not list(dest_root.glob(".demo-skill.lock*"))
        # the handler installed for the duration of the staged section must be restored
        assert signal.getsignal(signal.SIGTERM) == original_handler
    finally:
        signal.signal(signal.SIGTERM, original_handler)


def test_live_held_lock_yields_a_failed_outcome_instead_of_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A concurrent/stuck lock must surface as InstallOutcome(status="failed"), not an
    unhandled LockTimeoutError -- mirrors test_install_engine_locking.py's
    test_live_held_lock_times_out_with_a_clear_error's real-subprocess-holder technique, but
    through install_skill() itself so a multi-skill `sb install` run can keep going instead of
    crashing mid-run. install_skill() doesn't expose held_lock's wait_timeout, so it's shortened
    here by wrapping the module-level held_lock the same way other tests in this file patch
    install_engine's module globals (e.g. the KeyboardInterrupt test's validate_tree patch)."""
    real_held_lock = install_engine.held_lock

    @contextmanager
    def _short_wait_held_lock(dest_root: Path, skill_id: str, **_kwargs: object):
        with real_held_lock(dest_root, skill_id, wait_timeout=2.0):
            yield

    monkeypatch.setattr(install_engine, "held_lock", _short_wait_held_lock)

    repo = _minimal_repo(tmp_path)
    dest_root = tmp_path / "dest"
    dest_root.mkdir()

    holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        lock_dir = dest_root / ".demo-skill.lock"
        lock_dir.mkdir()
        (lock_dir / "pid").write_text(str(holder.pid), encoding="utf-8")
        (lock_dir / "acquired_at").write_text(str(time.time()), encoding="utf-8")

        outcome = install_skill(
            "demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor"
        )

        assert outcome.status == "failed"
        assert "timed out waiting for lock" in outcome.message
    finally:
        holder.terminate()
        holder.wait(timeout=5)


def test_symlinked_destination_is_refused(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    dest_root = tmp_path / "dest"
    dest_root.mkdir()
    real_target = tmp_path / "elsewhere"
    real_target.mkdir()
    (dest_root / "demo-skill").symlink_to(real_target)

    outcome = install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert outcome.status == "failed"
    assert "symlink" in outcome.message.lower()


def test_dry_run_fails_when_skill_source_is_missing(tmp_path: Path) -> None:
    """install_skill()'s dry-run path only checks registry membership and destination
    ownership before this fix -- it never called package_skill(), so a stale/deleted
    skills.yaml `path:` entry would report "would install" success for a skill that could
    never actually install. The dry-run check must catch the same thing a real install would
    fail on."""
    repo = _minimal_repo(tmp_path)
    (repo / "demo-skill" / "SKILL.md").unlink()
    dest_root = tmp_path / "dest"

    outcome = install_skill(
        "demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor", dry_run=True
    )

    assert outcome.status == "failed"
    assert "skill not found" in outcome.message
    assert not (dest_root / "demo-skill").exists()


def test_malformed_skills_yaml_yields_a_failed_outcome_not_a_traceback(tmp_path: Path) -> None:
    """registry_skill_ids()/classify_install_destination() used to sit outside any try/except
    at the top of install_skill() -- a malformed skills.yaml raised straight through install_skill()
    as an uncaught yaml.YAMLError instead of a clean InstallOutcome(status="failed", ...)."""
    repo = _minimal_repo(tmp_path)
    (repo / "skills.yaml").write_text("skills:\n  demo-skill: [unterminated\n", encoding="utf-8")
    dest_root = tmp_path / "dest"

    outcome = install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert outcome.status == "failed"
    assert outcome.message


@pytest.mark.skipif(sys.platform == "win32", reason="os.kill(pid, SIGTERM) bypasses Python's signal module on Windows")
def test_sigterm_during_cleanup_failed_install_is_deferred_until_rollback_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, signal_sentinels: object
) -> None:
    """_cleanup_failed_install() runs from install_skill()'s `except` handlers, after the
    `with _sigterm_as_system_exit()` block that wrapped the primary staged work has already
    exited -- so without its own protection, a second SIGTERM landing mid-rollback would
    terminate the process immediately, leaving an un-swept orphaned `.{skill}.staging.*`/
    `.{skill}.backup.*` directory (unlike held_lock()'s own cleanup, this one isn't
    self-healing -- nothing later sweeps it). Deferred, not converted to SystemExit: converting
    would just interrupt the rollback itself partway, leaving the very orphan it exists to
    prevent. So the rollback must actually finish (staging directory gone), and only then does
    the process exit 130."""
    stage_dir = tmp_path / ".demo-skill.staging.abc123"
    stage_dir.mkdir()
    skill_dest = tmp_path / "demo-skill"
    original_handler = signal.getsignal(signal.SIGTERM)

    real_rmtree = install_engine.shutil.rmtree
    fired = False

    def _send_sigterm_once(path: object, *args: object, **kwargs: object) -> None:
        # shutil.rmtree is patched process-wide; only fire once, for the staging directory.
        nonlocal fired
        if not fired and Path(path) == stage_dir:
            fired = True
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(1)
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(install_engine.shutil, "rmtree", _send_sigterm_once)

    try:
        with pytest.raises(SystemExit) as exc_info:
            install_engine._cleanup_failed_install(stage_dir, None, skill_dest)
        assert exc_info.value.code == 130
        assert not stage_dir.exists()  # the rollback ran to completion despite the signal
        assert signal.getsignal(signal.SIGTERM) == original_handler
    finally:
        signal.signal(signal.SIGTERM, original_handler)


@pytest.mark.skipif(sys.platform == "win32", reason="os.kill(pid, SIGTERM) bypasses Python's signal module on Windows")
def test_sigterm_mid_rollback_still_restores_the_backed_up_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, signal_sentinels: object
) -> None:
    """The restore branch -- moving the previous install back out of the backup directory -- is
    what actually protects a user's existing install. A signal landing at the start of the
    rollback (on the staging-directory removal that runs first) must not skip it: the previous
    install has to come back, and only then does the process exit 130."""
    stage_dir = tmp_path / ".demo-skill.staging.abc123"
    stage_dir.mkdir()
    backup_dir = tmp_path / ".demo-skill.backup.abc123"
    (backup_dir / "skill").mkdir(parents=True)
    (backup_dir / "skill" / "SKILL.md").write_text("previous", encoding="utf-8")
    skill_dest = tmp_path / "demo-skill"  # absent: it was moved aside into the backup

    real_rmtree = install_engine.shutil.rmtree
    fired = False

    def _send_sigterm_once(path: object, *args: object, **kwargs: object) -> None:
        nonlocal fired
        if not fired and Path(path) == stage_dir:
            fired = True
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(0.2)
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(install_engine.shutil, "rmtree", _send_sigterm_once)

    with pytest.raises(SystemExit) as exc_info:
        install_engine._cleanup_failed_install(stage_dir, backup_dir, skill_dest)

    assert exc_info.value.code == 130
    assert not stage_dir.exists()
    assert (skill_dest / "SKILL.md").read_text(encoding="utf-8") == "previous"
    assert not backup_dir.exists()


def test_an_interrupt_is_not_swallowed_when_its_own_cleanup_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A rollback that itself raises OSError used to escape the interrupt handler, land in the
    outer `except (LockTimeoutError, OSError)`, and come back as an ordinary "failed"
    InstallOutcome -- so `sb install a b c` carried on to the next skill after being told to
    stop. The interrupt must still propagate; the cleanup failure is reported, not fatal."""
    repo = _minimal_repo(tmp_path)
    dest_root = tmp_path / "dest"

    def _interrupt(stage_dir: Path, **_kwargs: object) -> list[str]:
        raise KeyboardInterrupt

    def _failing_cleanup(*_args: object, **_kwargs: object) -> None:
        raise OSError(5, "simulated I/O error during rollback")

    monkeypatch.setattr(install_engine, "validate_tree", _interrupt)
    monkeypatch.setattr(install_engine, "_cleanup_failed_install", _failing_cleanup)

    with pytest.raises(KeyboardInterrupt):
        install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert "cleanup after interrupt failed" in capsys.readouterr().err


@pytest.mark.skipif(sys.platform == "win32", reason="os.kill(pid, SIGTERM) bypasses Python's signal module on Windows")
def test_sigterm_during_the_backup_failure_cleanup_leaves_the_existing_install_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, signal_sentinels: object
) -> None:
    """The dedicated backup-failure call site: `_cleanup_failed_install()` runs from *inside*
    the outer `with _sigterm_as_system_exit()` block (so its deferral nests), and the
    SystemExit it raises is then caught by that block's own handler, which runs the rollback a
    second time. That second run must be a harmless no-op on the already-cleaned directories --
    and the install that was there beforehand must be exactly as it was."""
    repo = _minimal_repo(tmp_path)
    dest_root = tmp_path / "dest"
    existing = dest_root / "demo-skill"
    existing.mkdir(parents=True)
    (existing / "SKILL.md").write_text("# Previous good install\n", encoding="utf-8")
    (existing / ".software-builder-manifest.json").write_text(
        json.dumps({"manifest_version": 1, "skill": "demo-skill", "files": {}}), encoding="utf-8"
    )

    real_replace = os.replace
    real_rmtree = install_engine.shutil.rmtree
    fired = False

    def _failing_backup_replace(src: object, dst: object) -> None:
        if Path(src) == existing:  # the move-aside-into-backup step
            raise OSError(5, "simulated backup failure")
        return real_replace(src, dst)

    def _send_sigterm_once(path: object, *args: object, **kwargs: object) -> None:
        nonlocal fired
        if not fired and ".demo-skill.staging." in str(path):
            fired = True
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(0.2)
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(install_engine.os, "replace", _failing_backup_replace)
    monkeypatch.setattr(install_engine.shutil, "rmtree", _send_sigterm_once)

    with pytest.raises(SystemExit) as exc_info:
        install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert exc_info.value.code == 130
    assert (existing / "SKILL.md").read_text(encoding="utf-8") == "# Previous good install\n"
    assert not list(dest_root.glob(".demo-skill.staging.*"))
    assert not list(dest_root.glob(".demo-skill.backup.*"))
    assert not list(dest_root.glob(".demo-skill.lock*"))


@pytest.mark.skipif(sys.platform == "win32", reason="os.kill(pid, SIGTERM) bypasses Python's signal module on Windows")
def test_sigterm_while_removing_the_backup_after_a_successful_replace_still_removes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, signal_sentinels: object
) -> None:
    """The success path's own backup removal is cleanup too: nothing sweeps an orphaned
    `.{skill}.backup.*` directory, so a signal landing on it must not abandon it."""
    repo = _minimal_repo(tmp_path)
    dest_root = tmp_path / "dest"
    assert install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor").status == "installed"

    real_rmtree = install_engine.shutil.rmtree
    fired = False

    def _send_sigterm_once(path: object, *args: object, **kwargs: object) -> None:
        nonlocal fired
        if not fired and ".demo-skill.backup." in str(path):
            fired = True
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(0.2)
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(install_engine.shutil, "rmtree", _send_sigterm_once)

    with pytest.raises(SystemExit) as exc_info:
        install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert exc_info.value.code == 130
    assert fired
    assert list(dest_root.glob(".demo-skill.*")) == []
    assert (dest_root / "demo-skill" / "SKILL.md").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="os.kill(pid, SIGTERM) bypasses Python's signal module on Windows")
def test_a_second_signal_landing_as_the_rollback_starts_cannot_abandon_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, signal_sentinels: object
) -> None:
    """Between the first signal ending the work and the rollback's own deferral starting, the
    process used to be back on the default disposition: a second signal in that gap killed it
    with the staging directory (holding a SKILL.md) still on disk."""
    repo = _minimal_repo(tmp_path)
    dest_root = tmp_path / "dest"
    seen_stage_dirs: list[Path] = []

    def _first_signal(stage_dir: Path, **_kwargs: object) -> list[str]:
        seen_stage_dirs.append(stage_dir)
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(1)
        return []  # pragma: no cover

    real_cleanup = install_engine._cleanup_failed_install

    def cleanup_after_a_second_signal(*args: object, **kwargs: object) -> None:
        os.kill(os.getpid(), signal.SIGTERM)  # lands exactly as the rollback begins
        time.sleep(0.2)
        real_cleanup(*args, **kwargs)

    monkeypatch.setattr(install_engine, "validate_tree", _first_signal)
    monkeypatch.setattr(install_engine, "_cleanup_failed_install", cleanup_after_a_second_signal)

    with pytest.raises(SystemExit) as exc_info:
        install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert exc_info.value.code == 130
    assert seen_stage_dirs and not seen_stage_dirs[0].exists()
    assert list(dest_root.glob(".demo-skill.*")) == []
