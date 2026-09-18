#!/usr/bin/env python3
"""The install/uninstall engine: locking and the stage/backup/replace/cleanup state machine
for writing one skill into one destination.

This is the single implementation of that state machine -- both `scripts/install.sh` (via
this module's CLI, `python3 -m scripts.install_engine install|uninstall ...`, one subprocess
call per skill x destination) and the standalone `sb install`/`sb uninstall` commands
(cli/sb/__main__.py, calling install_skill()/uninstall_skill() in-process) call into it.
Neither caller re-implements locking, staging, backup, or rollback locally. Every piece of
logic install.sh already delegated to Python before this module existed
(package_skill.package_skill, reference_utils.classify_install_destination,
validate_references.validate_tree, install_support.registry_skill_ids) is reused directly
here, unforked.

ADR: see docs/adr/0007-shared-install-engine.md for why install.sh shells out to this module
instead of keeping its own bash port of the state machine.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from scripts.install_support import registry_skill_ids
from scripts.package_skill import _resolve_source_dir, package_skill, validate_skill_name
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
def _sigterm_as_system_exit() -> Iterator[None]:
    """Converts SIGTERM into a catchable SystemExit for the duration of the block, mirroring
    install.sh's own `trap on_install_interrupt INT TERM`. Python's default SIGTERM
    disposition terminates the process immediately, bypassing try/finally -- unlike SIGINT,
    which Python already converts to a catchable KeyboardInterrupt -- so a supervisor kill or
    CI timeout sent as SIGTERM would otherwise skip install_skill()'s own
    (KeyboardInterrupt, SystemExit) cleanup handler entirely. Not registered on Windows, which
    has no equivalent POSIX signal semantics.
    """
    if sys.platform == "win32":
        yield
        return
    previous_handler = signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(130))
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous_handler)


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

    A lock is reclaimed (taken over) when its recorded PID both exists and is no longer
    alive, or its recorded age exceeds `stale_after` regardless of PID liveness (covers a
    PID that died and was later reused by an unrelated live process, e.g. after a reboot).
    A lock that is neither dead-PID-stale nor age-stale is genuinely live; after
    `wait_timeout` seconds of polling, this raises LockTimeoutError instead of waiting
    forever.

    A lock directory exists for a brief window before its `pid`/`acquired_at` files are
    written (two separate filesystem operations, not one atomic one) -- matching
    install.sh's own bash implementation (`mkdir` then two separate `echo`/`date` writes). A
    waiter observing that window (missing/unreadable pid) does NOT treat it as stale -- it
    falls through to the age check exactly like bash's own `[[ -f "${lock_dir}/pid" ]]`
    guard does, so a lock that's still mid-setup is waited on, not reclaimed out from under
    its own holder. Only a genuinely old directory (age > stale_after, via the pid file's
    timestamp when present, falling back to the lock directory's own mtime when the pid
    file itself hasn't been written yet) is treated as abandoned.
    """
    lock_dir = _lock_dir_for(dest_root, skill)
    waited = 0.0
    while True:
        try:
            os.mkdir(lock_dir)
        except FileExistsError:
            lock_pid = _read_lock_pid(lock_dir)
            is_stale = lock_pid is not None and not is_pid_alive(lock_pid)
            if not is_stale:
                age = _read_lock_age(lock_dir)
                if age is None:
                    try:
                        age = time.time() - lock_dir.stat().st_mtime
                    except OSError:
                        age = None
                # age is None here only when acquired_at AND the directory's own stat() both
                # failed (e.g. the holder's cleanup removed lock_dir out from under this read) --
                # matching the pre-fallback behavior, treat that as stale rather than live: the
                # reclaim below is a harmless no-op if the directory is already gone (os.rename
                # raises, is swallowed, and the next loop iteration's mkdir succeeds anyway).
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
# Wording matches scripts/install.sh's own historical messages exactly (locked in by
# scripts/tests/test_install_legacy_golden.py and test_install_rollback.py, which run
# install.sh as a subprocess and assert this literal text) -- install and uninstall use
# different verbs ("replace" vs "remove"), so two dicts rather than one derived by string
# substitution, which is how these two message sets drifted apart before this module existed.
_INSTALL_BLOCK_MESSAGES = {
    OWNERSHIP_SYMLINK: "refusing to replace symlink at {dest}",
    OWNERSHIP_UNOWNED: "refusing to replace unowned directory at {dest} (not installed by software-builder)",
    OWNERSHIP_CORRUPT_OWNERSHIP: "refusing to replace {dest}: install manifest is missing, unreadable, or names a different skill",
}
_UNINSTALL_BLOCK_MESSAGES = {
    OWNERSHIP_SYMLINK: "refusing to remove symlink at {dest}",
    OWNERSHIP_UNOWNED: "refusing to remove unowned directory at {dest} (not installed by software-builder)",
    OWNERSHIP_CORRUPT_OWNERSHIP: "refusing to remove {dest}: install manifest is missing, unreadable, or names a different skill",
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
            # install.sh golden-tests this exact line (test_install_legacy_golden.py /
            # test_install_rollback.py): a rollback restore is worth surfacing to the caller
            # even though this function otherwise just returns results.
            print(f"warning: restored previous install at {skill_dest}", file=sys.stderr)
        shutil.rmtree(backup_dir, ignore_errors=True)


def install_skill(
    skill_id: str,
    *,
    repo_root: Path,
    dest_root: Path,
    host_label: str,
    dry_run: bool = False,
    wait_timeout: float = DEFAULT_LOCK_WAIT_TIMEOUT_SECONDS,
    stale_after: float = DEFAULT_LOCK_STALE_SECONDS,
) -> InstallOutcome:
    """Install one skill from repo_root into dest_root/skill_id, following install.sh's own
    install_skill() sequence: validate -> early ownership check -> (dry-run short-circuit) ->
    lock -> stage (same filesystem as dest_root) -> package -> validate references -> re-check
    ownership -> back up any existing software-builder-owned install -> atomic replace ->
    clean up the backup on success, or restore it and discard the stage on any failure.
    """
    try:
        validate_skill_name(skill_id)

        if skill_id not in set(registry_skill_ids(repo_root)):
            return InstallOutcome(
                skill_id, dest_root / skill_id, "failed", f"{skill_id!r} is not in skills.yaml"
            )

        skill_dest = dest_root / skill_id
        classification = classify_install_destination(skill_dest, skill_id=skill_id)
        if classification in _BLOCKING_OWNERSHIP_STATES:
            message = _INSTALL_BLOCK_MESSAGES[classification].format(dest=skill_dest)
            return InstallOutcome(skill_id, skill_dest, "failed", message)

        if dry_run:
            # package_skill() is only called below, on the non-dry-run path -- check the same
            # thing it would fail on (a missing/mismatched skills.yaml `path:` entry) so a
            # dry-run doesn't report "would install" for a skill that can't actually install.
            skill_md = _resolve_source_dir(repo_root, skill_id) / "SKILL.md"
            if not skill_md.is_file():
                return InstallOutcome(skill_id, skill_dest, "failed", f"skill not found at {skill_md}")
            return InstallOutcome(
                skill_id, skill_dest, "dry_run", f"would install {skill_id} → {skill_dest} (host={host_label})"
            )
    except Exception as exc:
        return InstallOutcome(
            skill_id, dest_root / skill_id, "failed", str(exc) if str(exc) else f"{type(exc).__name__} during install"
        )

    try:
        dest_root.mkdir(parents=True, exist_ok=True)
        with held_lock(dest_root, skill_id, wait_timeout=wait_timeout, stale_after=stale_after):
            stage_dir: Path | None = None
            backup_dir: Path | None = None
            try:
                # SIGTERM (a supervisor kill, CI timeout) must reach the same cleanup path as
                # SIGINT/KeyboardInterrupt below -- Python has no built-in conversion for it.
                with _sigterm_as_system_exit():
                    stage_dir = Path(tempfile.mkdtemp(dir=dest_root, prefix=f".{skill_id}.staging."))
                    package_skill(skill=skill_id, repo_root=repo_root, dest=stage_dir, host=host_label)

                    errors = validate_tree(stage_dir, check_anchors=False, installed_package=True)
                    if errors:
                        raise ValueError("; ".join(errors))

                    reclassification = classify_install_destination(skill_dest, skill_id=skill_id)
                    if reclassification in _BLOCKING_OWNERSHIP_STATES:
                        message = _INSTALL_BLOCK_MESSAGES[reclassification].format(dest=skill_dest)
                        raise ValueError(message)

                    if reclassification == OWNERSHIP_SOFTWARE_BUILDER_OWNED:
                        # install.sh golden-tests this exact line -- see _cleanup_failed_install's
                        # matching "restored previous install" print for the rollback half of the pair.
                        print(f"warning: replacing existing install at {skill_dest}", file=sys.stderr)
                        backup_dir = Path(tempfile.mkdtemp(dir=dest_root, prefix=f".{skill_id}.backup."))
                        try:
                            os.replace(skill_dest, backup_dir / "skill")
                        except OSError:
                            # Nothing was actually backed up, so _cleanup_failed_install's restore
                            # branch is a no-op here; this matches install.sh's own dedicated
                            # backup-failure message rather than falling through to the generic
                            # exception handler below, which would report the raw OSError text.
                            _cleanup_failed_install(stage_dir, backup_dir, skill_dest)
                            return InstallOutcome(
                                skill_id, skill_dest, "failed", f"failed to back up existing install at {skill_dest}"
                            )

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
            return InstallOutcome(skill_id, skill_dest, "installed", f"Installed {skill_id} → {skill_dest}")
    except (LockTimeoutError, OSError) as exc:
        # A concurrent/stuck lock (LockTimeoutError) or a failure acquiring it in the first
        # place (OSError from dest_root.mkdir, e.g. permission denied) must become a failed
        # outcome, not an unhandled traceback -- install.sh's own lock-acquire failure is a
        # plain `return 1` that lets a multi-skill run continue to the next skill; a raised
        # exception here would instead crash `sb`'s multi-skill CLI loop mid-run. Only the
        # lock-acquisition step is covered here -- OSErrors raised once inside the lock (e.g.
        # during staging) are already handled by the inner `except Exception` above, which
        # returns rather than raises, so they never reach this outer handler.
        return InstallOutcome(skill_id, skill_dest, "failed", str(exc))


@dataclass(frozen=True)
class UninstallOutcome:
    skill_id: str
    dest: Path
    status: str  # "uninstalled" | "absent" | "dry_run" | "failed"
    message: str


def uninstall_skill(
    skill_id: str,
    *,
    dest_root: Path,
    dry_run: bool = False,
    wait_timeout: float = DEFAULT_LOCK_WAIT_TIMEOUT_SECONDS,
    stale_after: float = DEFAULT_LOCK_STALE_SECONDS,
) -> UninstallOutcome:
    """Remove one installed skill from dest_root/skill_id, following install.sh's own
    uninstall_skill() sequence: lock -> classify ownership -> ABSENT is a warning, not a
    failure -> SYMLINK/UNOWNED/CORRUPT_OWNERSHIP block with a specific message -> a
    software-builder-owned install is removed outright (no staging/backup needed, unlike
    install -- there is nothing to roll back to).

    Deliberate divergence from install.sh: this does not re-check registry membership
    (install.sh's own registry_check_skill-equivalent) the way install_skill() does, so a
    since-deregistered skill can still be uninstalled -- ownership classification alone still
    bounds what gets touched, so this is arguably safer, not a gap.
    """
    try:
        validate_skill_name(skill_id)
    except ValueError as exc:
        return UninstallOutcome(skill_id, dest_root / skill_id, "failed", str(exc))

    skill_dest = dest_root / skill_id
    try:
        dest_root.mkdir(parents=True, exist_ok=True)
        with held_lock(dest_root, skill_id, wait_timeout=wait_timeout, stale_after=stale_after):
            classification = classify_install_destination(skill_dest, skill_id=skill_id)
            if classification == OWNERSHIP_ABSENT:
                return UninstallOutcome(skill_id, skill_dest, "absent", f"not installed: {skill_dest}")
            if classification in _BLOCKING_OWNERSHIP_STATES:
                message = _UNINSTALL_BLOCK_MESSAGES[classification].format(dest=skill_dest)
                return UninstallOutcome(skill_id, skill_dest, "failed", message)

            if dry_run:
                return UninstallOutcome(skill_id, skill_dest, "dry_run", f"would remove {skill_dest}")

            try:
                shutil.rmtree(skill_dest)
            except Exception as exc:
                message = str(exc) if str(exc) else f"{type(exc).__name__} during uninstall"
                return UninstallOutcome(skill_id, skill_dest, "failed", message)
            return UninstallOutcome(
                skill_id, skill_dest, "uninstalled", f"Uninstalled {skill_id} from {skill_dest}"
            )
    except Exception as exc:
        # Covers a concurrent/stuck lock (LockTimeoutError), a failure acquiring it (OSError,
        # e.g. permission denied on dest_root.mkdir), and classify_install_destination() above
        # raising something unexpected (e.g. a malformed on-disk manifest) -- any of these must
        # become a failed outcome, not an unhandled traceback, so a multi-skill `sb uninstall`
        # run can continue to the next skill instead of crashing mid-run.
        return UninstallOutcome(skill_id, skill_dest, "failed", str(exc) if str(exc) else f"{type(exc).__name__} during uninstall")


# Status -> (line prefix, stream) for the CLI presentation below. install_skill()/
# uninstall_skill() return unprefixed content on `.message` (that's the contract
# cli/sb/__main__.py already calls and tests against directly); the prefix and stdout-vs-
# stderr split are presentation, decided once here rather than duplicated by each caller.
_PRESENTATION = {
    "installed": ("", sys.stdout),
    "uninstalled": ("", sys.stdout),
    "dry_run": ("dry-run: ", sys.stdout),
    "absent": ("warning: ", sys.stderr),
    "failed": ("error: ", sys.stderr),
}


def _print_outcome(outcome: InstallOutcome | UninstallOutcome) -> None:
    prefix, stream = _PRESENTATION[outcome.status]
    print(f"{prefix}{outcome.message}", file=stream)


def _env_float(name: str, default: float) -> float:
    # Mirrors bash's `${VAR:-default}`, which install.sh's own acquire_lock previously used to
    # read these same two env vars: an empty value falls back to the default exactly like an
    # unset one, rather than failing float() with an empty string.
    value = os.environ.get(name, "")
    return float(value) if value else default


def _lock_timing_from_env() -> tuple[float, float]:
    # scripts/tests/test_install_concurrency.py sets these to exercise timeout/staleness
    # behavior without waiting out real-world-sized delays.
    wait_timeout = _env_float("LOCK_WAIT_TIMEOUT_SECONDS", DEFAULT_LOCK_WAIT_TIMEOUT_SECONDS)
    stale_after = _env_float("LOCK_STALE_SECONDS", DEFAULT_LOCK_STALE_SECONDS)
    return wait_timeout, stale_after


def _cli_install(args: argparse.Namespace) -> int:
    wait_timeout, stale_after = _lock_timing_from_env()
    try:
        outcome = install_skill(
            args.skill_id,
            repo_root=args.repo_root,
            dest_root=args.dest_root,
            host_label=args.host_label,
            dry_run=args.dry_run,
            wait_timeout=wait_timeout,
            stale_after=stale_after,
        )
    except (KeyboardInterrupt, SystemExit):
        # install_skill() already ran its own cleanup before re-raising (see the
        # (KeyboardInterrupt, SystemExit) handler inside it -- SystemExit is how
        # _sigterm_as_system_exit() converts a SIGTERM into the same cleanup path); 130
        # matches install.sh's own on_install_interrupt trap, and the caller (install.sh's
        # run_python wrapper, or a future multi-skill batch here) must treat this as a
        # whole-run abort, not a per-skill failure it continues past.
        return 130
    _print_outcome(outcome)
    return 1 if outcome.status == "failed" else 0


def _cli_uninstall(args: argparse.Namespace) -> int:
    wait_timeout, stale_after = _lock_timing_from_env()
    try:
        outcome = uninstall_skill(
            args.skill_id,
            dest_root=args.dest_root,
            dry_run=args.dry_run,
            wait_timeout=wait_timeout,
            stale_after=stale_after,
        )
    except (KeyboardInterrupt, SystemExit):
        return 130
    _print_outcome(outcome)
    return 1 if outcome.status == "failed" else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="install_engine.py",
        description="Install/uninstall one skill into one destination -- the state machine "
        "scripts/install.sh shells out to and sb install/uninstall call in-process.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("skill_id")
    install_parser.add_argument("dest_root", type=Path)
    install_parser.add_argument("host_label")
    install_parser.add_argument("--repo-root", type=Path, required=True)
    install_parser.add_argument("--dry-run", action="store_true")
    install_parser.set_defaults(func=_cli_install)

    uninstall_parser = subparsers.add_parser("uninstall")
    uninstall_parser.add_argument("skill_id")
    uninstall_parser.add_argument("dest_root", type=Path)
    uninstall_parser.add_argument("--dry-run", action="store_true")
    uninstall_parser.set_defaults(func=_cli_uninstall)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
