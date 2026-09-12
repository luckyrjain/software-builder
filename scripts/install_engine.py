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
