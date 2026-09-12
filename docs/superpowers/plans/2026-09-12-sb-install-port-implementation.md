# `sb install` / `sb uninstall` / `sb verify` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port `scripts/install.sh`'s locking and rollback logic to a new, standalone Python module so the `sb` CLI (currently read-only: `doctor`/`list`/`explain`/`compatibility`) can install/uninstall/verify skills for real, with no software-builder checkout present.

**Architecture:** A new module, `scripts/install_engine.py`, implements exactly what `install.sh` does NOT already delegate to Python: the mkdir-based cross-process lock (PID-liveness + wall-clock-age staleness, atomic rename-based reclaim) and the stage→validate→backup→atomic-replace→cleanup-on-failure state machine. Everything else `install.sh` already delegates to Python — `package_skill.package_skill()`, `reference_utils.classify_install_destination()`, `validate_references.validate_tree()`, `install_support.registry_skill_ids()` — is reused directly, unforked, as a library import. `install.sh` itself is not touched. `cli/sb/__main__.py` gains `install`/`uninstall`/`verify` subcommands that call the new module against the vendored snapshot.

## Global Constraints

- `scripts/install.sh` is not modified in any way — this plan adds a wholly separate, parallel Python implementation (confirmed with the user).
- Cross-platform (POSIX + Windows), matching install.sh's own scope decision to widen it (confirmed with the user) — but this repo has **no Windows CI runner** (`grep -rn "windows-latest" .github/workflows/` finds nothing), so the Windows branch of the PID-liveness check is best-effort and explicitly documented as untested-on-real-Windows in its own docstring. Do not remove that caveat; it is accurate, not hedging-for-its-own-sake.
- No new dependencies — the Windows PID-liveness check uses stdlib `ctypes`, not `psutil`.
- Zero fork of existing reusable logic: `package_skill.package_skill()`, `reference_utils.classify_install_destination()`/`reject_symlinks()`/`reject_sensitive_files()`, `validate_references.validate_tree()`, `install_support.registry_skill_ids()`, `scripts.registry.install_resolver.resolve_install_destinations()` are called directly as library functions, never reimplemented.
- Scope is deliberately narrower than 1:1 feature parity with `install.sh`: shadow-precedence warnings (`install.sh`'s own `check-shadow` step, which it treats as non-fatal) and per-selector registry-wide coverage checks (`_check_selector_coverage`) are **not** ported — they are extra niceties `install.sh` layers on top of locking/rollback, not part of it. Note their absence in `sb install --help` rather than silently omitting them.
- Every new file/function that touches the filesystem outside a test's own `tmp_path` must go through the same `dest_root`-relative staging discipline `install.sh` uses (`tempfile.mkdtemp(dir=dest_root, ...)`, never system `$TMPDIR`) — this is exactly what `test_reinstall_backup_survives_a_missing_system_tmp_dir` locks in.

---

### Task 1: Locking primitives (`scripts/install_engine.py`)

**Files:**
- Create: `scripts/install_engine.py`
- Test: `scripts/tests/test_install_engine_locking.py`

**Interfaces:**
- Produces: `is_pid_alive(pid: int) -> bool`; `LockTimeoutError(RuntimeError)`; `held_lock(dest_root: Path, skill: str, *, wait_timeout: float = 30.0, stale_after: float = 300.0) -> AbstractContextManager[None]` (a `@contextlib.contextmanager` generator function)

- [ ] **Step 1: Write the failing tests**

```python
# scripts/tests/test_install_engine_locking.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest scripts/tests/test_install_engine_locking.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.install_engine'`

- [ ] **Step 3: Write the implementation**

```python
#!/usr/bin/env python3
"""Python port of scripts/install.sh's locking and stage/backup/replace/cleanup logic, for
the standalone `sb install`/`sb uninstall`/`sb verify` commands (cli/sb/__main__.py) -- used
against an installed skill with no software-builder checkout present.

scripts/install.sh is NOT modified by this module or anything that imports it: this is a
wholly separate, parallel implementation for `sb`, not a shared engine install.sh is
refactored onto. Every piece of logic install.sh already delegates to Python
(package_skill.package_skill, reference_utils.classify_install_destination,
validate_references.validate_tree, install_support.registry_skill_ids) is reused directly
here, unforked -- only the locking and the stage/backup/replace/cleanup state machine
(currently pure bash in install.sh) are new.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_LOCK_WAIT_TIMEOUT_SECONDS = 30.0
DEFAULT_LOCK_STALE_SECONDS = 300.0
_LOCK_POLL_INTERVAL_SECONDS = 1.0


class LockTimeoutError(RuntimeError):
    """Raised when a live, non-stale lock on (dest_root, skill) is still held after the
    configured wait timeout -- mirrors install.sh's own "timed out waiting for lock" error."""


def is_pid_alive(pid: int) -> bool:
    """Best-effort process-liveness check.

    POSIX: os.kill(pid, 0) sends no signal, just asks the kernel whether the PID exists and
    is reachable -- ProcessLookupError means dead, PermissionError means alive (but owned by
    someone else), any other OSError is treated as "cannot tell, assume dead" (matching
    install.sh's own kill -0 based check).

    Windows has no equivalent via os.kill: Python's os.kill on Windows only supports process
    termination and CTRL_C/CTRL_BREAK events, not a signal-0 existence probe. This uses
    ctypes to call the same OpenProcess/GetExitCodeProcess pair Windows' own process tools
    use -- stdlib-only, no psutil dependency. This repository has no Windows CI runner, so
    this branch is untested on real Windows; treat it as best-effort until it's exercised for
    real, not as a verified-equal port of the POSIX branch above.
    """
    if sys.platform == "win32":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _lock_dir_for(dest_root: Path, skill: str) -> Path:
    return dest_root / f".{skill}.lock"


def _read_lock_pid(lock_dir: Path) -> int | None:
    try:
        return int((lock_dir / "pid").read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _read_lock_age(lock_dir: Path) -> float | None:
    try:
        acquired_at = float((lock_dir / "acquired_at").read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    return time.time() - acquired_at


def _reclaim_stale_lock(lock_dir: Path) -> None:
    """Rename-then-remove, mirroring install.sh's reclaim_stale_lock exactly: only the
    renamer whose os.rename actually succeeds ever deletes anything, so two racing waiters
    can't have one delete a lock the other just freshly re-mkdir'd. A rename failure (the
    lock was already reclaimed/removed by a racing waiter) is not an error -- it just means
    this call lost the race, and the caller's retry loop will re-observe the current state.
    """
    stale_dir = lock_dir.with_name(f"{lock_dir.name}.stale.{os.getpid()}")
    try:
        os.rename(lock_dir, stale_dir)
    except OSError:
        return
    shutil.rmtree(stale_dir, ignore_errors=True)


@contextmanager
def held_lock(
    dest_root: Path,
    skill: str,
    *,
    wait_timeout: float = DEFAULT_LOCK_WAIT_TIMEOUT_SECONDS,
    stale_after: float = DEFAULT_LOCK_STALE_SECONDS,
) -> Iterator[None]:
    """Hold an exclusive, cross-process lock on (dest_root, skill) for the duration of the
    `with` block. A directory is used (not a file) because `os.mkdir` is atomic and fails
    with FileExistsError against anything already at that path -- same reason install.sh
    uses `mkdir` for its lock rather than a lockfile.

    A lock is reclaimed (taken over) when either: its recorded PID is no longer alive, or
    its recorded age exceeds `stale_after` regardless of PID liveness (covers a PID that
    died and was later reused by an unrelated live process, e.g. after a reboot). A lock
    that is neither dead-PID-stale nor age-stale is genuinely live; after `wait_timeout`
    seconds of polling, this raises LockTimeoutError instead of waiting forever.

    There is a narrow, intentional inherited race: a lock directory exists for a brief
    window before its `pid`/`acquired_at` files are written (two separate filesystem
    operations, not one atomic one) -- the exact same window install.sh's own bash
    implementation has (`mkdir` then two separate `echo`/`date` writes). A waiter observing
    that window sees a missing pid file and treats it as stale. This is accepted, not fixed,
    here: the goal is a faithful port of install.sh's actual behavior, not an improvement on
    it beyond that scope.
    """
    lock_dir = _lock_dir_for(dest_root, skill)
    waited = 0.0
    while True:
        try:
            os.mkdir(lock_dir)
        except FileExistsError:
            lock_pid = _read_lock_pid(lock_dir)
            is_stale = lock_pid is None or not is_pid_alive(lock_pid)
            if not is_stale:
                age = _read_lock_age(lock_dir)
                is_stale = age is None or age > stale_after
            if is_stale:
                _reclaim_stale_lock(lock_dir)
                continue
            if waited >= wait_timeout:
                raise LockTimeoutError(
                    f"timed out waiting for lock on {skill} at {lock_dir} "
                    f"(held by pid {lock_pid if lock_pid is not None else 'unknown'})"
                )
            time.sleep(_LOCK_POLL_INTERVAL_SECONDS)
            waited += _LOCK_POLL_INTERVAL_SECONDS
            continue
        break

    (lock_dir / "pid").write_text(str(os.getpid()), encoding="utf-8")
    (lock_dir / "acquired_at").write_text(str(time.time()), encoding="utf-8")
    try:
        yield
    finally:
        shutil.rmtree(lock_dir, ignore_errors=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest scripts/tests/test_install_engine_locking.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/install_engine.py scripts/tests/test_install_engine_locking.py
git commit -m "$(cat <<'EOF'
Add scripts/install_engine.py's locking primitives

Python port of scripts/install.sh's acquire_lock/reclaim_stale_lock/
release_current_lock (mkdir-based lock, PID-liveness + wall-clock-age
staleness, atomic rename-before-remove reclaim) -- for the standalone
sb install/uninstall commands. Cross-platform: the Windows
PID-liveness branch uses ctypes (stdlib, no new dependency) since
os.kill has no signal-0 probe on Windows; this repo has no Windows CI
runner, so that branch is documented as best-effort/untested.
install.sh itself is not touched.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Install orchestration (`install_skill`)

**Files:**
- Modify: `scripts/install_engine.py`
- Test: `scripts/tests/test_install_engine_install.py`

**Interfaces:**
- Consumes: `held_lock` (Task 1); `scripts.package_skill.package_skill(*, skill, repo_root, dest, host) -> None`; `scripts.package_skill.validate_skill_name(skill) -> None` (raises `ValueError`); `scripts.validate_references.validate_tree(root, *, check_anchors=False, installed_package=True) -> list[str]`; `scripts.reference_utils.classify_install_destination(dest, *, skill_id) -> str` and its `OWNERSHIP_*` constants; `scripts.install_support.registry_skill_ids(root) -> list[str]`
- Produces: `@dataclass(frozen=True) class InstallOutcome: skill_id: str; dest: Path; status: str; message: str` (`status` one of `"installed"`, `"dry_run"`, `"failed"`); `install_skill(skill_id, *, repo_root, dest_root, host_label, dry_run=False) -> InstallOutcome`

- [ ] **Step 1: Write the failing tests**

```python
# scripts/tests/test_install_engine_install.py
"""Tests for scripts/install_engine.py's install_skill() -- mirrors the rollback and
same-filesystem-staging scenarios scripts/tests/test_install_rollback.py and
scripts/tests/test_install_concurrency.py already lock in for install.sh."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts.install_engine import install_skill

ROOT = Path(__file__).resolve().parents[2]


def _minimal_repo(tmp_path: Path, *, skill_id: str = "demo-skill", broken: bool = False) -> Path:
    """A minimal repo root with one registered skill, valid enough for package_skill() to
    package it. Mirrors the shape scripts/tests/test_install_rollback.py's own fixture uses --
    read that file's fixture-building helper first and match its real conventions rather than
    inventing a new shape from scratch."""
    repo = tmp_path / "repo"
    skills_dir = repo / "skills" / skill_id
    skills_dir.mkdir(parents=True)
    if broken:
        (skills_dir / "SKILL.md").write_text(
            "# Demo\n\nSee [missing](reference/missing.md).\n", encoding="utf-8"
        )
    else:
        (skills_dir / "SKILL.md").write_text("# Demo\n\nA minimal test skill.\n", encoding="utf-8")
    (repo / "skills.yaml").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "skills": {
                    skill_id: {
                        "path": skill_id,
                        "category": "test",
                        "invocation": "ambient",
                        "hosts": {"cursor": {"install": True}},
                        "install": {"requires": []},
                        "lint": {"skill_md_max_lines": 180, "target": skill_id},
                        "composition": {"invokes": []},
                        "capabilities": {"required": [], "optional": []},
                        "risk_class": ["read-only"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (repo / "VERSION").write_text("1.0.0\n", encoding="utf-8")
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
    assert (dest_root / "demo-skill" / "SKILL.md").read_text(encoding="utf-8") == "# Demo\n\nA minimal test skill.\n"


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
```

(The first fixture helper, `_minimal_repo`, has a comment pointing at `test_install_rollback.py`'s real fixture — read that file first and adapt this template to match its actual conventions, e.g. if it uses YAML instead of `json.dumps` for `skills.yaml`, or a different minimal-skill shape, follow the real file rather than this illustrative version.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest scripts/tests/test_install_engine_install.py -v`
Expected: FAIL — `ImportError: cannot import name 'install_skill' from 'scripts.install_engine'`

- [ ] **Step 3: Write the implementation**

Append to `scripts/install_engine.py`:

```python
import tempfile
from dataclasses import dataclass

from scripts.install_support import registry_skill_ids
from scripts.package_skill import package_skill, validate_skill_name
from scripts.reference_utils import (
    OWNERSHIP_CORRUPT_OWNERSHIP,
    OWNERSHIP_SOFTWARE_BUILDER_OWNED,
    OWNERSHIP_SYMLINK,
    OWNERSHIP_UNOWNED,
    classify_install_destination,
)
from scripts.validate_references import validate_tree

_BLOCKING_OWNERSHIP_STATES = frozenset(
    {OWNERSHIP_SYMLINK, OWNERSHIP_UNOWNED, OWNERSHIP_CORRUPT_OWNERSHIP}
)
_OWNERSHIP_BLOCK_MESSAGES = {
    OWNERSHIP_SYMLINK: "refusing to install over a symlink at {dest}",
    OWNERSHIP_UNOWNED: "refusing to install over an unowned directory at {dest} (not installed by software-builder)",
    OWNERSHIP_CORRUPT_OWNERSHIP: "refusing to install over {dest}: install manifest is missing, unreadable, or names a different skill",
}


@dataclass(frozen=True)
class InstallOutcome:
    skill_id: str
    dest: Path
    status: str  # "installed" | "dry_run" | "failed"
    message: str


def _cleanup_failed_install(stage_dir: Path | None, backup_dir: Path | None, skill_dest: Path) -> None:
    """Mirrors install.sh's cleanup_failed_install: discard the failed staging attempt, and
    if a previous install was moved aside into backup_dir and nothing currently occupies
    skill_dest, restore it."""
    if stage_dir is not None and stage_dir.exists():
        shutil.rmtree(stage_dir, ignore_errors=True)
    if backup_dir is not None and backup_dir.exists():
        backed_up_skill = backup_dir / "skill"
        if not skill_dest.exists() and backed_up_skill.exists():
            os.replace(backed_up_skill, skill_dest)
        shutil.rmtree(backup_dir, ignore_errors=True)


def install_skill(
    skill_id: str,
    *,
    repo_root: Path,
    dest_root: Path,
    host_label: str,
    dry_run: bool = False,
) -> InstallOutcome:
    """Install one skill from repo_root into dest_root/skill_id, following install.sh's own
    install_skill() sequence: validate -> early ownership check -> (dry-run short-circuit) ->
    lock -> stage (same filesystem as dest_root) -> package -> validate references -> re-check
    ownership -> back up any existing software-builder-owned install -> atomic replace ->
    clean up the backup on success, or restore it and discard the stage on any failure.
    """
    try:
        validate_skill_name(skill_id)
    except ValueError as exc:
        return InstallOutcome(skill_id, dest_root / skill_id, "failed", str(exc))

    if skill_id not in set(registry_skill_ids(repo_root)):
        return InstallOutcome(
            skill_id, dest_root / skill_id, "failed", f"{skill_id!r} is not in skills.yaml"
        )

    skill_dest = dest_root / skill_id
    classification = classify_install_destination(skill_dest, skill_id=skill_id)
    if classification in _BLOCKING_OWNERSHIP_STATES:
        message = _OWNERSHIP_BLOCK_MESSAGES[classification].format(dest=skill_dest)
        return InstallOutcome(skill_id, skill_dest, "failed", message)

    if dry_run:
        return InstallOutcome(skill_id, skill_dest, "dry_run", f"would install {skill_id} to {skill_dest}")

    dest_root.mkdir(parents=True, exist_ok=True)
    with held_lock(dest_root, skill_id):
        stage_dir: Path | None = None
        backup_dir: Path | None = None
        try:
            stage_dir = Path(tempfile.mkdtemp(dir=dest_root, prefix=f".{skill_id}.staging."))
            package_skill(skill=skill_id, repo_root=repo_root, dest=stage_dir, host=host_label)

            errors = validate_tree(stage_dir, check_anchors=False, installed_package=True)
            if errors:
                raise ValueError("; ".join(errors))

            reclassification = classify_install_destination(skill_dest, skill_id=skill_id)
            if reclassification in _BLOCKING_OWNERSHIP_STATES:
                message = _OWNERSHIP_BLOCK_MESSAGES[reclassification].format(dest=skill_dest)
                raise ValueError(message)

            if reclassification == OWNERSHIP_SOFTWARE_BUILDER_OWNED:
                backup_dir = Path(tempfile.mkdtemp(dir=dest_root, prefix=f".{skill_id}.backup."))
                os.replace(skill_dest, backup_dir / "skill")

            os.replace(stage_dir, skill_dest)
            stage_dir = None  # now living at skill_dest; nothing left to clean up on success
        except BaseException as exc:
            _cleanup_failed_install(stage_dir, backup_dir, skill_dest)
            message = str(exc) if str(exc) else f"{type(exc).__name__} during install"
            return InstallOutcome(skill_id, skill_dest, "failed", message)

        if backup_dir is not None:
            shutil.rmtree(backup_dir, ignore_errors=True)
        return InstallOutcome(skill_id, skill_dest, "installed", f"installed {skill_id} to {skill_dest}")
```

Note the `except BaseException` (not just `Exception`): this intentionally also catches `KeyboardInterrupt`, so a Ctrl-C mid-install (the cross-platform equivalent of install.sh's `INT`/`TERM` trap) still runs the same cleanup-and-restore path before the exception propagates — `held_lock`'s own `finally` then still releases the lock as the exception continues to unwind.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest scripts/tests/test_install_engine_install.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Run the locking tests too, to confirm no regression**

Run: `python3 -m pytest scripts/tests/test_install_engine_locking.py scripts/tests/test_install_engine_install.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/install_engine.py scripts/tests/test_install_engine_install.py
git commit -m "$(cat <<'EOF'
Add install_skill() to scripts/install_engine.py

Ports install.sh's stage/validate/backup/replace/cleanup state
machine to Python, reusing package_skill.package_skill(),
validate_references.validate_tree(), and
reference_utils.classify_install_destination() directly -- unforked.
Rollback-on-failure and same-filesystem-staging behavior mirrors
test_install_rollback.py/test_install_concurrency.py's own locked-in
scenarios for the bash version.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Uninstall orchestration (`uninstall_skill`)

**Files:**
- Modify: `scripts/install_engine.py`
- Test: `scripts/tests/test_install_engine_uninstall.py`

**Interfaces:**
- Consumes: `held_lock` (Task 1); `classify_install_destination` and its `OWNERSHIP_*` constants (already imported in Task 2)
- Produces: `@dataclass(frozen=True) class UninstallOutcome: skill_id: str; dest: Path; status: str; message: str` (`status` one of `"uninstalled"`, `"absent"`, `"dry_run"`, `"failed"`); `uninstall_skill(skill_id, *, dest_root, dry_run=False) -> UninstallOutcome`

- [ ] **Step 1: Write the failing tests**

```python
# scripts/tests/test_install_engine_uninstall.py
"""Tests for scripts/install_engine.py's uninstall_skill() -- mirrors the ownership-hardening
scenarios scripts/tests/test_install_legacy_golden.py already locks in for install.sh's
uninstall path."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.install_engine import uninstall_skill


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest scripts/tests/test_install_engine_uninstall.py -v`
Expected: FAIL — `ImportError: cannot import name 'uninstall_skill' from 'scripts.install_engine'`

- [ ] **Step 3: Write the implementation**

Append to `scripts/install_engine.py`:

```python
from scripts.reference_utils import OWNERSHIP_ABSENT


@dataclass(frozen=True)
class UninstallOutcome:
    skill_id: str
    dest: Path
    status: str  # "uninstalled" | "absent" | "dry_run" | "failed"
    message: str


def uninstall_skill(skill_id: str, *, dest_root: Path, dry_run: bool = False) -> UninstallOutcome:
    """Remove one installed skill from dest_root/skill_id, following install.sh's own
    uninstall_skill() sequence: lock -> classify ownership -> ABSENT is a warning, not a
    failure -> SYMLINK/UNOWNED/CORRUPT_OWNERSHIP block with a specific message -> a
    software-builder-owned install is removed outright (no staging/backup needed, unlike
    install -- there is nothing to roll back to).
    """
    skill_dest = dest_root / skill_id
    dest_root.mkdir(parents=True, exist_ok=True)
    with held_lock(dest_root, skill_id):
        classification = classify_install_destination(skill_dest, skill_id=skill_id)
        if classification == OWNERSHIP_ABSENT:
            return UninstallOutcome(skill_id, skill_dest, "absent", f"not installed: {skill_dest}")
        if classification in _BLOCKING_OWNERSHIP_STATES:
            message = _OWNERSHIP_BLOCK_MESSAGES[classification].format(dest=skill_dest).replace(
                "install over", "remove"
            )
            return UninstallOutcome(skill_id, skill_dest, "failed", message)

        if dry_run:
            return UninstallOutcome(skill_id, skill_dest, "dry_run", f"would uninstall {skill_id} from {skill_dest}")

        shutil.rmtree(skill_dest)
        return UninstallOutcome(skill_id, skill_dest, "uninstalled", f"uninstalled {skill_id} from {skill_dest}")
```

Note the `.replace("install over", "remove")` on the shared `_OWNERSHIP_BLOCK_MESSAGES` templates: install and uninstall both refuse the same three ownership states, and reusing one message-template dict (rather than a second, near-duplicate one) keeps the two wordings from silently drifting apart — the small string substitution is cheaper than a second dict to maintain.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest scripts/tests/test_install_engine_uninstall.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Run every install_engine test together**

Run: `python3 -m pytest scripts/tests/test_install_engine_locking.py scripts/tests/test_install_engine_install.py scripts/tests/test_install_engine_uninstall.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/install_engine.py scripts/tests/test_install_engine_uninstall.py
git commit -m "$(cat <<'EOF'
Add uninstall_skill() to scripts/install_engine.py

Ports install.sh's uninstall_skill() ownership-hardening sequence:
ABSENT is a warning (not a failure), SYMLINK/UNOWNED/CORRUPT_OWNERSHIP
all refuse removal with a specific message, only a genuinely
software-builder-owned install is removed. Reuses the same
_OWNERSHIP_BLOCK_MESSAGES templates install_skill() already defined,
substituted for uninstall's wording, so the two never drift apart.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `sb install` / `sb uninstall` / `sb verify` CLI wiring

**Files:**
- Modify: `cli/sb/__main__.py`
- Test: `cli/tests/test_sb_install.py`

**Interfaces:**
- Consumes: `install_skill`, `uninstall_skill` (Tasks 2-3, in the vendored copy); `scripts.install_support.cmd_verify(installed_path: Path) -> int` (already exists — thin reuse, no new verify logic); `scripts.registry.install_resolver.resolve_install_destinations(host_registry, agent, *, home, target_dir) -> list[tuple[Path, str]]` and `install_selectors() -> list[str]` (already exist); `scripts.registry.host_registry.parse_host_registry`

- [ ] **Step 1: Write the failing tests**

```python
# cli/tests/test_sb_install.py
"""Tests for sb install/uninstall/verify -- runs the real sb subprocess against a real,
isolated target directory (never the developer's actual ~/.cursor or ~/.claude)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CLI_ROOT = Path(__file__).resolve().parents[1]


def _run_sb(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sb", *args],
        cwd=CLI_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_install_then_verify_then_uninstall_round_trip(tmp_path: Path) -> None:
    target_dir = tmp_path / "target-repo"
    target_dir.mkdir()

    install_result = _run_sb("install", "pr-review", "--host", "cursor", "--target-dir", str(target_dir))
    assert install_result.returncode == 0, install_result.stderr
    installed_path = target_dir / ".cursor" / "skills" / "pr-review"
    assert (installed_path / "SKILL.md").is_file()

    verify_result = _run_sb("verify", str(installed_path))
    assert verify_result.returncode == 0, verify_result.stderr
    assert "ok:" in verify_result.stdout

    uninstall_result = _run_sb("uninstall", "pr-review", "--host", "cursor", "--target-dir", str(target_dir))
    assert uninstall_result.returncode == 0, uninstall_result.stderr
    assert not installed_path.exists()


def test_install_dry_run_makes_no_changes(tmp_path: Path) -> None:
    target_dir = tmp_path / "target-repo"
    target_dir.mkdir()

    result = _run_sb(
        "install", "pr-review", "--host", "cursor", "--target-dir", str(target_dir), "--dry-run"
    )

    assert result.returncode == 0
    assert not (target_dir / ".cursor").exists()


def test_install_rejects_unknown_selector(tmp_path: Path) -> None:
    target_dir = tmp_path / "target-repo"
    target_dir.mkdir()

    result = _run_sb("install", "pr-review", "--host", "not-a-real-selector", "--target-dir", str(target_dir))

    assert result.returncode == 2
    assert "not-a-real-selector" in result.stderr


def test_multi_skill_install_continues_past_one_failure_and_reports_a_summary(tmp_path: Path) -> None:
    target_dir = tmp_path / "target-repo"
    target_dir.mkdir()
    # Pre-create an unowned destination for the second skill so its install is refused,
    # while the first and third succeed -- mirrors
    # test_multi_skill_run_continues_past_a_failure_and_reports_a_summary's intent.
    unowned = target_dir / ".cursor" / "skills" / "security-review"
    unowned.mkdir(parents=True)
    (unowned / "some-file.txt").write_text("not ours\n", encoding="utf-8")

    result = _run_sb(
        "install", "pr-review", "security-review", "system-design",
        "--host", "cursor", "--target-dir", str(target_dir),
    )

    assert result.returncode != 0
    assert "installed: 2" in result.stdout or "installed: 2" in result.stderr
    assert "failed: 1" in result.stdout or "failed: 1" in result.stderr
    assert (target_dir / ".cursor" / "skills" / "pr-review" / "SKILL.md").is_file()
    assert (target_dir / ".cursor" / "skills" / "system-design" / "SKILL.md").is_file()
```

(This task's tests assume `--target-dir` behaves the same way it does for `install.sh` — a project-scope override. Verify this against `scripts/registry/install_resolver.resolve_install_destinations`'s actual `target_dir` parameter semantics, already read during planning, before finalizing the fixture paths above; adjust the exact destination path assertions — e.g. `.cursor/skills/pr-review` — to match whatever `cursor`'s real `agent-hosts.yaml` target path template actually resolves to under a given `target_dir`, rather than assuming.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd cli && python3 -m pytest tests/test_sb_install.py -v`
Expected: FAIL — `install`/`uninstall`/`verify` not recognized subcommands yet

- [ ] **Step 3: Wire the three subcommands into `cli/sb/__main__.py`**

Add imports (alongside the existing vendored-path imports):

```python
from scripts.install_engine import install_skill, uninstall_skill  # noqa: E402
from scripts.install_support import cmd_verify  # noqa: E402
from scripts.registry.install_resolver import install_selectors, resolve_install_destinations  # noqa: E402
```

Add subparsers in `main()`:

```python
    install_parser = subparsers.add_parser("install", help="install one or more skills")
    install_parser.add_argument("skill_ids", nargs="+", help="registered skill id(s)")
    install_parser.add_argument("--host", required=True, help=f"install selector: {', '.join(install_selectors())}")
    install_parser.add_argument("--target-dir", type=Path, default=None, help="project root for project-scope targets")
    install_parser.add_argument("--dry-run", action="store_true")

    uninstall_parser = subparsers.add_parser("uninstall", help="uninstall one or more skills")
    uninstall_parser.add_argument("skill_ids", nargs="+", help="registered skill id(s)")
    uninstall_parser.add_argument("--host", required=True, help=f"install selector: {', '.join(install_selectors())}")
    uninstall_parser.add_argument("--target-dir", type=Path, default=None, help="project root for project-scope targets")
    uninstall_parser.add_argument("--dry-run", action="store_true")

    verify_parser = subparsers.add_parser("verify", help="verify an installed skill's integrity")
    verify_parser.add_argument("installed_path", type=Path)
```

Add a shared helper and the three dispatch branches:

```python
def _resolve_destinations(agent: str, target_dir: Path | None) -> list[tuple[Path, str]]:
    host_registry = parse_host_registry(registry_snapshot_root() / "agent-hosts.yaml")
    return resolve_install_destinations(host_registry, agent, home=Path.home(), target_dir=target_dir)


def _cmd_install(args: argparse.Namespace) -> int:
    try:
        destinations = _resolve_destinations(args.host, args.target_dir)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    installed = failed = 0
    for skill_id in args.skill_ids:
        for dest_root, host_label in destinations:
            outcome = install_skill(
                skill_id,
                repo_root=registry_snapshot_root(),
                dest_root=dest_root,
                host_label=host_label,
                dry_run=args.dry_run,
            )
            print(outcome.message)
            if outcome.status == "failed":
                failed += 1
            elif outcome.status == "installed":
                installed += 1
    if len(args.skill_ids) * len(destinations) > 1:
        print(f"installed: {installed}, failed: {failed}", file=sys.stderr)
    return 1 if failed else 0


def _cmd_uninstall(args: argparse.Namespace) -> int:
    try:
        destinations = _resolve_destinations(args.host, args.target_dir)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    uninstalled = failed = 0
    for skill_id in args.skill_ids:
        for dest_root, _host_label in destinations:
            outcome = uninstall_skill(skill_id, dest_root=dest_root, dry_run=args.dry_run)
            print(outcome.message)
            if outcome.status == "failed":
                failed += 1
            elif outcome.status == "uninstalled":
                uninstalled += 1
    if len(args.skill_ids) * len(destinations) > 1:
        print(f"uninstalled: {uninstalled}, failed: {failed}", file=sys.stderr)
    return 1 if failed else 0
```

And in `main()`'s dispatch chain:

```python
    if args.command == "install":
        return _cmd_install(args)
    if args.command == "uninstall":
        return _cmd_uninstall(args)
    if args.command == "verify":
        return cmd_verify(args.installed_path)
```

Note: `resolve_install_destinations` raises `ValueError` for an unknown selector (`"unknown --agent {agent!r} (expected one of {install_selectors()})"`) — this is what `test_install_rejects_unknown_selector` exercises; no separate validation needed here, the existing library function already fails closed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m scripts.build_sb_snapshot` (refresh the vendored copy so it includes Tasks 1-3's new module)
Run: `cd cli && python3 -m pytest tests/test_sb_install.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Run the full `cli/tests/` suite**

Run: `cd cli && python3 -m pytest tests/ -v`
Expected: all PASS, no regressions

- [ ] **Step 6: Commit**

```bash
git add cli/sb/__main__.py cli/tests/test_sb_install.py
git commit -m "$(cat <<'EOF'
Wire sb install/uninstall/verify subcommands

install/uninstall loop over every (skill x destination) pair
independently (one failure doesn't abort the rest, matching
install.sh's own multi-skill behavior) and print an installed/failed
or uninstalled/failed summary when more than one pair ran. verify is
a thin pass-through to the already-existing install_support.cmd_verify
-- no new verify logic. Destination resolution reuses
install_resolver.resolve_install_destinations() unchanged, so an
unknown --host selector fails the same way it always has.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: End-to-end wheel smoke test extension

**Files:**
- Modify: `scripts/tests/test_sb_wheel_smoke.py`

**Interfaces:**
- No new interfaces — extends the existing real wheel-build-and-install smoke test to also exercise `install`/`verify`/`uninstall` through the actually-installed `sb` binary, closing the same "prove it for real, not just in the source tree" gap Task 8 of the diagnostics-slice plan closed for the read-only commands.

- [ ] **Step 1: Extend the smoke test**

In `scripts/tests/test_sb_wheel_smoke.py`'s `test_sb_wheel_builds_installs_and_runs`, after the existing `sb explain`/`sb doctor`/`sb compatibility` blocks, add:

```python
    target_dir = tmp_path / "target-repo"
    target_dir.mkdir()

    install_result = subprocess.run(
        [str(sb_executable), "install", "pr-review", "--host", "cursor", "--target-dir", str(target_dir)],
        check=False, capture_output=True, text=True,
    )
    assert install_result.returncode == 0, install_result.stderr
    installed_path = target_dir / ".cursor" / "skills" / "pr-review"
    assert (installed_path / "SKILL.md").is_file()

    verify_result = subprocess.run(
        [str(sb_executable), "verify", str(installed_path)],
        check=False, capture_output=True, text=True,
    )
    assert verify_result.returncode == 0, verify_result.stderr

    uninstall_result = subprocess.run(
        [str(sb_executable), "uninstall", "pr-review", "--host", "cursor", "--target-dir", str(target_dir)],
        check=False, capture_output=True, text=True,
    )
    assert uninstall_result.returncode == 0, uninstall_result.stderr
    assert not installed_path.exists()
```

(Adjust the destination path assertion to match whatever Task 4 established as the real resolved path for `--host cursor --target-dir <dir>`, consistent with that task's own tests.)

- [ ] **Step 2: Run the smoke test**

Run: `python3 -m pytest scripts/tests/test_sb_wheel_smoke.py -v`
Expected: PASS — this is the first test proving `sb install`/`verify`/`uninstall` work through the actually-built-and-installed wheel, not just the source tree.

- [ ] **Step 3: Run the full regression suite**

Run: `python3 -m pytest -n 2 scripts/tests/ -q --deselect scripts/tests/test_sb_wheel_smoke.py::test_sb_wheel_builds_installs_and_runs`
Expected: same baseline as before this plan (no new failures) — use `-n 2` specifically, matching CI's pinned `PYTEST_XDIST_WORKERS=2`, not `-n auto`, per the lesson learned in the diagnostics-slice plan (a worker-count-sensitive bug there was invisible under `-n auto` on a higher-core-count machine).

- [ ] **Step 4: Commit**

```bash
git add scripts/tests/test_sb_wheel_smoke.py
git commit -m "$(cat <<'EOF'
Extend wheel smoke test to cover sb install/verify/uninstall

Proves the full round trip through the actually-built-and-installed
wheel, not just the source tree -- the same bar Task 8 of the
diagnostics-slice plan set for doctor/list/explain/compatibility.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-review

**Spec coverage:** `sb install`, `sb uninstall`, `sb verify` are all wired (Task 4); locking (Task 1), rollback/backup (Task 2), and ownership hardening on removal (Task 3) are each ported with tests mirroring the exact scenarios `test_install_concurrency.py`/`test_install_rollback.py`/`test_install_legacy_golden.py` already lock in for the bash version. `verify` is confirmed pure reuse (`install_support.cmd_verify`), not reimplemented. The explicitly-narrowed scope (no shadow-precedence warning, no per-selector registry-wide coverage check) is stated once in Global Constraints, not silently dropped.

**Placeholder scan:** Task 2's fixture helper and Task 4/5's destination-path assertions each carry one explicit, flagged instruction to verify against the real, existing files (`test_install_rollback.py`'s fixture shape; `install_resolver`'s actual `--target-dir`/`cursor` path resolution) rather than trusting this plan's illustrative values blindly — same pattern used successfully in every prior plan this session. Every other step has complete, runnable code.

**Type consistency:** `InstallOutcome`/`UninstallOutcome` (Task 2/3) share the same four-field shape (`skill_id`, `dest`, `status`, `message`); `_BLOCKING_OWNERSHIP_STATES`/`_OWNERSHIP_BLOCK_MESSAGES` (Task 2) are defined once and reused, not redefined, by Task 3. `install_skill`/`uninstall_skill`'s signatures match exactly between their Task 2/3 definitions and Task 4's call sites.

**Scope check:** 5 tasks, each independently testable; Task 4 depends on Tasks 1-3 landing in the vendored snapshot, Task 5 depends on Task 4. `install.sh` itself is never touched by any task (confirmed: no task's file list includes it). Windows support is real code (Task 1's `ctypes` branch), not a TODO, with its actual verification gap (no Windows CI) stated plainly rather than glossed over.
