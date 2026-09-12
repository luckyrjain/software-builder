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
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from scripts.install_support import registry_skill_ids
from scripts.package_skill import package_skill, validate_skill_name
from scripts.reference_utils import (
    OWNERSHIP_ABSENT,
    OWNERSHIP_CORRUPT_OWNERSHIP,
    OWNERSHIP_SOFTWARE_BUILDER_OWNED,
    OWNERSHIP_SYMLINK,
    OWNERSHIP_UNOWNED,
    classify_install_destination,
)
from scripts.validate_references import validate_tree

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
        except (KeyboardInterrupt, SystemExit):
            # Mirrors install.sh's own INT/TERM trap: on_install_interrupt() runs
            # cleanup_failed_install() and then `exit 130`, terminating the whole process
            # rather than falling through to per-skill failure bookkeeping the way an
            # ordinary validation failure does (which returns 1 and lets a multi-skill loop
            # continue to the next skill). Re-raising here after cleanup is the Python
            # equivalent: it propagates out through this `with held_lock(...)` block --
            # whose own `finally` still releases the lock on the way out, same as any other
            # exit path -- instead of being swallowed into a normal InstallOutcome that a
            # future multi-skill caller could mistake for just one more failed skill.
            _cleanup_failed_install(stage_dir, backup_dir, skill_dest)
            raise
        except Exception as exc:
            _cleanup_failed_install(stage_dir, backup_dir, skill_dest)
            message = str(exc) if str(exc) else f"{type(exc).__name__} during install"
            return InstallOutcome(skill_id, skill_dest, "failed", message)

        if backup_dir is not None:
            shutil.rmtree(backup_dir, ignore_errors=True)
        return InstallOutcome(skill_id, skill_dest, "installed", f"installed {skill_id} to {skill_dest}")


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
    try:
        validate_skill_name(skill_id)
    except ValueError as exc:
        return UninstallOutcome(skill_id, dest_root / skill_id, "failed", str(exc))

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

        try:
            shutil.rmtree(skill_dest)
        except Exception as exc:
            message = str(exc) if str(exc) else f"{type(exc).__name__} during uninstall"
            return UninstallOutcome(skill_id, skill_dest, "failed", message)
        return UninstallOutcome(skill_id, skill_dest, "uninstalled", f"uninstalled {skill_id} from {skill_dest}")
