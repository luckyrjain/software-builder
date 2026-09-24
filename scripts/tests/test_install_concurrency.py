"""Tests for install.sh's advisory locking (Candidate 13 final-review fix).

The Candidate 13 adversarial review found no locking anywhere in install.sh: two concurrent
invocations installing the same skill to the same destination could race the final
stage_dir -> skill_dest mv (a losing mv nests the source inside the winner's directory instead of
overwriting it), and a companion finding showed the pre-replace backup was made with a bare
`mktemp -d` (system tmp, e.g. /tmp) instead of inside dest_root, so a cross-filesystem mv could
leave neither the old nor the new install intact under a hard kill. This file exercises the fix:
a per-(skill, dest_root) lock -- the operating system's own file lock, see
scripts/install_engine.py's held_lock() -- serializing install_skill/uninstall_skill's mutating
section, plus the backup directory now living on the same filesystem as the destination.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from scripts.install_engine import _lock_path_for
from scripts.tests.install_lock_test_helpers import spawn_lock_holder

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "scripts" / "install.sh"
SKILL = "pr-review"


def _env(home: Path, **overrides: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update({"HOME": str(home), "PATH": f"{ROOT / '.venv' / 'bin'}:{env['PATH']}"})
    env.update(overrides)
    return env


def run_installer(*args: str, home: Path, **env_overrides: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INSTALLER), *args],
        cwd=ROOT,
        env=_env(home, **env_overrides),
        capture_output=True,
        text=True,
        check=False,
    )


def test_live_held_lock_times_out_with_a_clear_error(tmp_path: Path) -> None:
    home = tmp_path / "home"
    skills_dir = home / ".cursor" / "skills"
    skills_dir.mkdir(parents=True)
    lock_path = _lock_path_for(skills_dir, SKILL)
    holder = spawn_lock_holder(lock_path)
    try:
        started = time.monotonic()
        result = run_installer(
            "--agent", "cursor", SKILL, home=home, LOCK_WAIT_TIMEOUT_SECONDS="2",
        )
        elapsed = time.monotonic() - started

        assert result.returncode != 0
        assert "timed out waiting for lock" in result.stderr
        assert str(holder.pid) in result.stderr
        assert 2 <= elapsed < 15
        assert not (skills_dir / SKILL / "SKILL.md").is_file()
    finally:
        holder.kill()
        holder.wait()


def test_concurrent_installs_of_the_same_skill_do_not_corrupt_the_destination(tmp_path: Path) -> None:
    """Two install.sh processes racing to install the same skill to the same destination must
    not produce a nested-staging-directory artifact (the pre-fix `mv` race) -- exactly one of
    them wins the mv, the other correctly serializes behind the lock and either replaces the
    winner's install cleanly or observes SOFTWARE_BUILDER_OWNED and backs it up first."""
    home = tmp_path / "home"
    (home / ".cursor" / "skills").mkdir(parents=True)

    procs = [
        subprocess.Popen(
            ["bash", str(INSTALLER), "--agent", "cursor", SKILL],
            cwd=ROOT,
            env=_env(home),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(4)
    ]
    results = [(p, *p.communicate(timeout=60)) for p in procs]

    for proc, _stdout, stderr in results:
        assert proc.returncode == 0, stderr

    dest = home / ".cursor" / "skills" / SKILL
    assert dest.is_dir()
    assert (dest / "SKILL.md").is_file()
    assert (dest / ".software-builder-manifest.json").is_file()
    # The corruption this guards against: a losing `mv` nesting the staged directory inside the
    # winner's instead of replacing it, leaving a stray `.pr-review.staging.XXXXXX` (or a nested
    # `pr-review/`) under the destination itself.
    stray_entries = [
        entry.name
        for entry in dest.iterdir()
        if entry.name.startswith(f".{SKILL}.staging.") or entry.name == SKILL
    ]
    assert stray_entries == [], f"corrupted destination contents: {stray_entries}"
    assert not any(dest.glob(f".{SKILL}.lock"))
    assert not any((home / ".cursor" / "skills").glob(f".{SKILL}.backup.*"))


def test_reinstall_backup_survives_a_missing_system_tmp_dir(tmp_path: Path) -> None:
    """The pre-replace backup directory must live on the same filesystem as the destination
    (dest_root), not the system temp dir -- otherwise a cross-filesystem mv falls back to
    copy-then-delete, which a hard kill mid-copy can catch with neither the old nor the new
    install intact. Pointing TMPDIR at a nonexistent path and confirming the reinstall (which
    exercises the SOFTWARE_BUILDER_OWNED backup-and-replace branch) still succeeds proves the
    backup no longer depends on TMPDIR/system tmp at all."""
    home = tmp_path / "home"
    first = run_installer("--agent", "cursor", SKILL, home=home)
    assert first.returncode == 0, first.stderr

    bogus_tmpdir = tmp_path / "no-such-tmp-dir"
    second = run_installer("--agent", "cursor", SKILL, home=home, TMPDIR=str(bogus_tmpdir))

    assert second.returncode == 0, second.stderr
    assert "replacing existing install" in second.stderr
    assert not bogus_tmpdir.exists()
    dest = home / ".cursor" / "skills" / SKILL
    assert (dest / "SKILL.md").is_file()


