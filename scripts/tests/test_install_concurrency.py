"""Tests for install.sh's advisory locking (Candidate 13 final-review fix).

The Candidate 13 adversarial review found no locking anywhere in install.sh: two concurrent
invocations installing the same skill to the same destination could race the final
stage_dir -> skill_dest mv (a losing mv nests the source inside the winner's directory instead of
overwriting it), and a companion finding showed the pre-replace backup was made with a bare
`mktemp -d` (system tmp, e.g. /tmp) instead of inside dest_root, so a cross-filesystem mv could
leave neither the old nor the new install intact under a hard kill. This file exercises the fix:
a per-(skill, dest_root) mkdir-based lock serializing install_skill/uninstall_skill's mutating
section, with PID-liveness and wall-clock-age staleness recovery, plus the backup directory now
living on the same filesystem as the destination.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

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


def _lock_dir(home: Path) -> Path:
    return home / ".cursor" / "skills" / f".{SKILL}.lock"


def test_stale_lock_from_a_dead_pid_is_reclaimed_immediately(tmp_path: Path) -> None:
    home = tmp_path / "home"
    lock_dir = _lock_dir(home)
    lock_dir.mkdir(parents=True)
    # A PID essentially guaranteed not to be a live process on any real machine (PIDs wrap well
    # below this) -- exercises the kill -0-based staleness path, not the age-based fallback.
    (lock_dir / "pid").write_text("999999999\n", encoding="utf-8")
    (lock_dir / "acquired_at").write_text(str(int(time.time())), encoding="utf-8")

    started = time.monotonic()
    result = run_installer(
        "--agent", "cursor", SKILL, home=home, LOCK_WAIT_TIMEOUT_SECONDS="20",
    )
    elapsed = time.monotonic() - started

    assert result.returncode == 0, result.stderr
    assert elapsed < 10, "should reclaim a dead-pid lock immediately, not wait out the timeout"
    assert (home / ".cursor" / "skills" / SKILL / "SKILL.md").is_file()


def test_stale_lock_past_the_age_threshold_is_reclaimed_even_with_a_live_pid(tmp_path: Path) -> None:
    home = tmp_path / "home"
    lock_dir = _lock_dir(home)
    lock_dir.mkdir(parents=True)
    # This test process's own PID is alive (kill -0 succeeds), so only the wall-clock-age
    # fallback -- not PID liveness -- can explain a reclaim here.
    (lock_dir / "pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
    (lock_dir / "acquired_at").write_text(str(int(time.time()) - 1000), encoding="utf-8")

    started = time.monotonic()
    result = run_installer(
        "--agent", "cursor", SKILL, home=home,
        LOCK_WAIT_TIMEOUT_SECONDS="20", LOCK_STALE_SECONDS="300",
    )
    elapsed = time.monotonic() - started

    assert result.returncode == 0, result.stderr
    assert elapsed < 10, "should reclaim an aged-out lock immediately, not wait out the timeout"


def test_live_held_lock_times_out_with_a_clear_error(tmp_path: Path) -> None:
    home = tmp_path / "home"
    lock_dir = _lock_dir(home)
    lock_dir.mkdir(parents=True)
    holder = subprocess.Popen(["sleep", "30"])
    try:
        (lock_dir / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")
        (lock_dir / "acquired_at").write_text(str(int(time.time())), encoding="utf-8")

        started = time.monotonic()
        result = run_installer(
            "--agent", "cursor", SKILL, home=home, LOCK_WAIT_TIMEOUT_SECONDS="2",
        )
        elapsed = time.monotonic() - started

        assert result.returncode != 0
        assert "timed out waiting for lock" in result.stderr
        assert str(holder.pid) in result.stderr
        assert 2 <= elapsed < 15
        assert not (home / ".cursor" / "skills" / SKILL / "SKILL.md").is_file()
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


def test_stale_lock_reclaim_renames_before_removing(tmp_path: Path) -> None:
    """Reclaim must not be "check, rm -rf, mkdir": two waiters that read the same dead PID could
    both remove the lock directory, with the loser's rm -rf deleting the winner's freshly created
    live lock and both then entering the section the lock serializes. Renaming first makes the
    reclaim atomic -- only the winner of the mv removes anything -- and leaves no `.stale.<pid>`
    directory behind."""
    installer = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
    assert 'mv "${lock_dir}" "${stale_dir}"' in installer

    home = tmp_path / "home"
    lock_dir = _lock_dir(home)
    lock_dir.mkdir(parents=True)
    (lock_dir / "pid").write_text("999999999\n", encoding="utf-8")
    (lock_dir / "acquired_at").write_text(str(int(time.time())), encoding="utf-8")

    result = run_installer("--agent", "cursor", SKILL, home=home, LOCK_WAIT_TIMEOUT_SECONDS="20")

    assert result.returncode == 0, result.stderr
    leftovers = list((home / ".cursor" / "skills").glob(f".{SKILL}.lock.stale.*"))
    assert leftovers == []
