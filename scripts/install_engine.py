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
import math
import os
import re
import shutil
import signal
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

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
_LOCK_POLL_INTERVAL_SECONDS = 1.0
_EXIT_WITH_PARENT_ENV = "INSTALL_ENGINE_EXIT_WITH_PARENT"  # holds the expected parent pid
_PARENT_POLL_SECONDS = 0.5
_FORCE_QUIT_SIGNAL_COUNT = 3


class LockTimeoutError(RuntimeError):
    """Raised when a live lock on (dest_root, skill) is still held after the configured wait
    timeout -- mirrors install.sh's own historical "timed out waiting for lock" error."""


def _lock_path_for(dest_root: Path, skill: str) -> Path:
    return dest_root / f".{skill}.lock"


def _open_lock_file(lock_path: Path) -> int:
    if lock_path.is_dir():
        # A directory-format lock from a version of this module before it switched to an OS
        # advisory lock (it held `pid`/`acquired_at` files, reclaimed by staleness guesswork --
        # see docs/adr/0007-shared-install-engine.md). Nothing ever held an OS-level lock on
        # that directory under either scheme, so a leftover one is always safe to clear and
        # replace with the plain file this version locks at the same path.
        shutil.rmtree(lock_path, ignore_errors=True)
    return os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)


def _try_lock(fd: int) -> bool:
    """Attempt to claim the OS's own advisory lock on `fd` without blocking. True on success.

    POSIX: `flock(LOCK_EX | LOCK_NB)` -- held for as long as `fd` (or any dup of it) stays
    open, and released by the kernel the instant every such fd is gone, including on a crash:
    it is not a file on disk with content to interpret, so there is nothing to reclaim, age, or
    misjudge the identity of. Windows: `msvcrt.locking()` on a one-byte region of the same file,
    the closest stdlib equivalent -- released the same way, by handle closure or process exit.
    """
    if sys.platform == "win32":
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(fd: int) -> None:
    """Explicit release, best-effort. POSIX's flock needs no counterpart -- closing `fd` (which
    the caller always does right after this) releases it implicitly, including under a signal
    or a crash between here and the close -- but Windows' documentation asks a locked region be
    unlocked before its handle closes, so this does that where it matters and is a harmless
    no-op everywhere else."""
    if sys.platform == "win32":
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass


def _write_holder_pid(fd: int) -> None:
    """Diagnostics only: never read back to decide anything, only to name a holder in a
    LockTimeoutError message. A failure here must not fail the acquisition itself."""
    try:
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode("ascii"))
    except OSError:
        pass


def _read_holder_pid(fd: int) -> str:
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        return os.read(fd, 32).decode("ascii", errors="replace").strip() or "unknown"
    except OSError:
        return "unknown"


def _terminate_signal() -> int | None:
    """The graceful-terminate signal a supervisor can actually deliver and Python can actually
    catch: SIGTERM on POSIX. On Windows, `os.kill(pid, signal.SIGTERM)` bypasses Python's
    signal module entirely (CPython calls TerminateProcess() there -- an unconditional kill,
    same as SIGKILL) -- SIGBREAK (CTRL_BREAK_EVENT) is the one a process-group supervisor can
    actually deliver, so that's used there instead. None if neither is available, or if this
    isn't the main thread: `signal.signal()` only works there (it raises ValueError anywhere
    else), and a signal is delivered to the main thread regardless, so a caller running from a
    worker thread can't install a handler at all and is better off unprotected than crashing.
    """
    if threading.current_thread() is not threading.main_thread():
        return None
    if sys.platform == "win32":
        return getattr(signal, "SIGBREAK", None)
    return signal.SIGTERM


def _stop_signals() -> list[int]:
    """Every signal that means "stop": the graceful-terminate signal, plus SIGHUP on POSIX (a
    closed terminal or dropped ssh session). Left at its default, SIGHUP killed the process
    with 129 mid-install and stranded a staging directory holding a SKILL.md. Empty off the main
    thread, where no handler can be installed."""
    stop = []
    terminate = _terminate_signal()
    if terminate is not None:
        stop.append(terminate)
        hangup = getattr(signal, "SIGHUP", None)
        if hangup is not None:
            stop.append(hangup)
    return stop


@contextmanager
def _sigterm_as_system_exit() -> Iterator[None]:
    """Turns the first stop signal (SIGINT, SIGTERM, SIGHUP; SIGBREAK on Windows) into an
    exception -- KeyboardInterrupt for SIGINT, SystemExit(130) for the rest -- so it reaches the
    caller's cleanup handler. Python's default disposition for the terminate signals kills the
    process at once, bypassing try/finally, so a supervisor kill or CI timeout would otherwise
    skip install_skill()'s own cleanup entirely.

    Two-phase on purpose: once the first signal has fired, every later one is *absorbed* for the
    rest of the block, not raised. The block is meant to contain the caller's cleanup handler as
    well as the work it guards, so a second, closely-timed signal can neither interrupt that
    cleanup nor land in the gap between leaving the work and entering a separate deferral (the
    handler stays installed the whole time; the process is already exiting 130). For cleanup that
    runs after the block, see `_defer_interrupts()`.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    stopping = False

    def _on_stop(signum: int, frame: object) -> None:
        nonlocal stopping
        if stopping:
            return
        stopping = True
        if signum == signal.SIGINT:
            raise KeyboardInterrupt
        sys.exit(130)

    previous: dict[int, object] = {}
    try:
        for sig in [signal.SIGINT, *_stop_signals()]:
            handler = signal.getsignal(sig)
            if handler == signal.SIG_IGN:
                # An ignored signal (nohup, an async child of a non-interactive shell) is the
                # caller's explicit choice; converting it into an abort would override that.
                continue
            previous[sig] = handler
            signal.signal(sig, _on_stop)
        yield
    finally:
        for sig, handler in previous.items():
            # getsignal() returns None when the previous handler was installed outside Python's
            # signal module (e.g. by native/embedding-host code) -- there's no handler value to
            # hand back to signal.signal() in that case, and passing None raises TypeError,
            # which would mask whatever exception is already propagating through here.
            if handler is not None:
                signal.signal(sig, handler)  # type: ignore[arg-type]


@contextmanager
def _defer_interrupts() -> Iterator[None]:
    """For cleanup that must run to completion: an interrupt arriving during the block --
    SIGINT (Ctrl-C) or the graceful-terminate signal -- is recorded, not acted on. The block
    finishes, and only then is it re-raised as SystemExit(130), the same clean exit
    `_sigterm_as_system_exit()` produces.

    Distinct from `_sigterm_as_system_exit()` on purpose. Converting a second signal into
    SystemExit *inside* a rollback would interrupt the rollback itself partway, leaving
    exactly the un-swept `.{skill}.staging.*`/`.{skill}.backup.*` directory the rollback
    exists to prevent (nothing later sweeps one). Deferring instead means the cleanup still
    finishes and the process still exits 130 afterward. SIGINT is deferred too, not just the
    terminate signal: an interactive Ctrl-C mid-rollback is at least as likely as a supervisor
    kill, and Python's default would raise KeyboardInterrupt straight through the rollback.

    A recorded interrupt is never silently lost: it is raised after the block whether the
    block returned or raised, superseding an in-flight exception (chained, so the original is
    still visible as `__context__`). Otherwise a rollback that itself failed -- say the restore
    `os.replace` raised OSError -- would swallow the interrupt, and `sb install a b c` would
    carry on to the next skill after being told to stop.

    Off the main thread `signal.signal()` can't be used, so this is a no-op there.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    sigs = [signal.SIGINT, *_stop_signals()]
    received = False
    failure: BaseException | None = None
    signal_count = 0

    def _record(signum: int, frame: object) -> None:
        nonlocal received, signal_count
        received = True
        signal_count += 1
        if signal_count >= _FORCE_QUIT_SIGNAL_COUNT:
            # An uninterruptible cleanup (a hung rmtree, a stalled NFS mount) has no other exit:
            # bypassing every try/finally is the point, on the user's third explicit request to
            # stop. A hard kill from here is safe: _sweep_leftovers()/_recover_leftover_backups()
            # repair whatever this leaves on the next run, same as any other hard kill.
            print("warning: repeated interrupt -- forcing exit without finishing cleanup", file=sys.stderr)
            os._exit(130)

    previous: dict[int, object] = {}
    try:
        for sig in sigs:
            handler = signal.getsignal(sig)
            if handler == signal.SIG_IGN:
                # Ignored on purpose by the caller (nohup, async child of a non-interactive
                # shell): leave it ignored rather than turning it into an abort.
                continue
            # Recorded before it is replaced, inside the try, so a signal landing at any
            # point between two installs still restores every handler that was replaced.
            previous[sig] = handler
            signal.signal(sig, _record)
        yield
    except BaseException as exc:
        failure = exc
        raise
    finally:
        for sig, handler in previous.items():
            # getsignal() returns None when the previous handler was installed outside
            # Python's signal module. Unlike _sigterm_as_system_exit()'s leftover handler
            # (which at least exits), leaving `_record` installed would swallow every later
            # signal for the life of the process -- so fall back to the interpreter's own
            # default for that signal instead.
            if handler is None:
                handler = signal.default_int_handler if sig == signal.SIGINT else signal.SIG_DFL
            signal.signal(sig, handler)  # type: ignore[arg-type]
        if received:
            if isinstance(failure, Exception):
                # The exit below supersedes this; without a word the user would never learn
                # the cleanup itself failed (e.g. a previous install stranded in a backup dir).
                print(f"warning: cleanup failed while handling an interrupt: {failure}", file=sys.stderr)
            sys.exit(130)


@contextmanager
def held_lock(
    dest_root: Path,
    skill: str,
    *,
    wait_timeout: float = DEFAULT_LOCK_WAIT_TIMEOUT_SECONDS,
) -> Iterator[None]:
    """Hold an exclusive, cross-process lock on (dest_root, skill) for the duration of the
    `with` block, via the operating system's own advisory file lock rather than a lock file or
    directory this module tracks the identity, age, or liveness of itself (see `_try_lock()`).

    The OS releases the lock the moment the holding process is gone, by any means -- a clean
    return, an uncaught exception, SIGKILL, power loss to the machine underneath a remote
    holder. There is no "stale lock" for this module to reclaim, no PID to check the liveness
    of, no age to weigh against a configurable threshold: acquiring simply blocks (bounded by
    `wait_timeout`, polled at `_LOCK_POLL_INTERVAL_SECONDS`) until the OS itself reports the
    lock free. This replaces the previous design's atomic-directory acquisition, its rename-
    based stale-lock reclaim, and the pid-liveness/wall-clock-age fallbacks that reclaim needed
    -- along with the one residual race that design's own ADR 0007 entry documented (a third
    holder acquiring in the microseconds between a reclaim judging a lock stale and moving it
    aside): there is no reclaim step left to race.

    `flock()` is scoped to the *open file description*, not the process: a second, nested
    `held_lock()` call for the same (dest_root, skill) from the same process (or from a second
    thread in it) does not self-deadlock silently or succeed by mistake -- it blocks like any
    other contender, for up to `wait_timeout`, and then raises `LockTimeoutError` naming this
    process's own pid as the holder. Not expected in normal use (nothing in this module calls
    `held_lock()` reentrantly), but worth knowing if you're debugging a hang.

    Known, accepted tradeoff: `flock()` is unreliable over NFS -- some client/server
    combinations (particularly NFSv3 without a running lock daemon) silently no-op it, so two
    hosts sharing an NFS-mounted home directory could both believe they hold the lock. Accepted
    for a single-machine, ordinarily-local-disk install target; see ADR 0007.

    Releasing is just closing `fd` (`_unlock()` plus `os.close()`) -- not meaningfully
    interruptible partway the way the previous design's directory removal was, so unlike that
    design this needs no `_defer_interrupts()` around it for signal safety: even a signal
    landing mid-release leaves nothing worse than a closed-on-process-exit fd, and the OS's own
    lock release guarantee already covers a harder kill than any signal this process could
    still be running to handle. `os.close()` can still *raise* on a slow filesystem (it is one
    of the syscalls PEP 475 deliberately excludes from automatic EINTR retry, since retrying a
    close risks closing an unrelated fd number reused in the meantime) -- caught below rather
    than left to escape as a raw, unhandled exception, since there is nothing more to do about
    a failed close of a lock file: the fd (and whatever lock it held) is gone either way.
    """
    lock_path = _lock_path_for(dest_root, skill)
    fd = _open_lock_file(lock_path)
    try:
        # Waiting must be stoppable by a supervisor's SIGTERM the same as the work under the
        # lock: unconverted, the process dies with the raw 143 install.sh does not recognise.
        with _sigterm_as_system_exit():
            waited = 0.0
            while not _try_lock(fd):
                if waited >= wait_timeout:
                    raise LockTimeoutError(
                        f"timed out waiting for lock on {skill} at {lock_path} "
                        f"(held by pid {_read_holder_pid(fd)})"
                    )
                time.sleep(_LOCK_POLL_INTERVAL_SECONDS)
                waited += _LOCK_POLL_INTERVAL_SECONDS
            _write_holder_pid(fd)
        yield
    finally:
        try:
            _unlock(fd)
            os.close(fd)
        except OSError:
            pass



# tempfile.mkdtemp() appends exactly 8 characters from this alphabet. Matching *exactly* that, not
# just the prefix, is what keeps one skill's cleanup off another skill's directories: with a prefix
# match, skill `x` swept `.x.staging.y.staging.q1` (the working directory of a skill called
# `x.staging.y`) and treated a user's own `.x.backup.mine` as a backup of `x`.
_MKDTEMP_SUFFIX = r"[a-z0-9_]{8}"


def _leftover_entries(dest_root: Path, skill: str, kind: str) -> list[os.DirEntry[str]]:
    """This skill's own `.{skill}.{kind}.<mkdtemp suffix>` directories in dest_root (real
    directories only: a symlink is never followed or matched)."""
    pattern = re.compile(re.escape(f".{skill}.{kind}.") + _MKDTEMP_SUFFIX)
    try:
        return [
            e for e in os.scandir(dest_root) if pattern.fullmatch(e.name) and e.is_dir(follow_symlinks=False)
        ]
    except OSError:
        return []


def _recover_leftover_backups(dest_root: Path, skill: str, skill_dest: Path) -> None:
    """Undo what a hard kill (SIGKILL, power loss) left half-done, under the lock.

    A `.{skill}.backup.*` directory is the previous install, moved aside while its replacement was
    put in place. If the process died before the rollback or the final cleanup ran, either:
    - the destination is absent -> the previous install was displaced and never restored: put the
      NEWEST backup back (otherwise the user's skill has silently vanished), then discard the older
      ones; or
    - the destination is a complete software-builder-owned install -> the replacement finished
      (`os.replace` is atomic) and the backups are just old copies: delete them.
    A backup is only ever moved or deleted if its `skill/` really is an install of *this* skill (its
    manifest names it), and never discarded unless the install it protects is demonstrably in
    place; anything else (an unowned or symlinked destination, a lookalike directory) is left."""
    entries = _leftover_entries(dest_root, skill, "backup")
    if not entries:
        return
    # Newest first: scandir order is arbitrary, and restoring an older backup while deleting the
    # newer one would silently roll the user back a version.
    def _mtime(entry: os.DirEntry[str]) -> float:
        try:
            return entry.stat(follow_symlinks=False).st_mtime
        except OSError:
            return 0.0

    entries.sort(key=_mtime, reverse=True)
    for entry in entries:
        previous = Path(entry.path) / "skill"
        try:
            if classify_install_destination(previous, skill_id=skill) != OWNERSHIP_SOFTWARE_BUILDER_OWNED:
                continue  # not demonstrably a previous install of this skill: not ours to touch
            if not skill_dest.exists() and not skill_dest.is_symlink():
                os.replace(previous, skill_dest)
                print(
                    f"warning: restored the previous install of {skill} at {skill_dest} "
                    "after an interrupted replacement",
                    file=sys.stderr,
                )
                shutil.rmtree(entry.path, ignore_errors=True)
            elif classify_install_destination(skill_dest, skill_id=skill) == OWNERSHIP_SOFTWARE_BUILDER_OWNED:
                shutil.rmtree(entry.path, ignore_errors=True)
        except OSError:
            continue


def _sweep_leftovers(dest_root: Path, skill: str) -> None:
    """Delete this skill's `.{skill}.removing.<suffix>` and `.{skill}.staging.<suffix>`
    directories. Called with the lock held, so no other run of this skill can own one. They are
    garbage by construction -- the skill was already uninstalled, or the staged copy never went
    live -- and used to be orphaned by a failed deletion or a hard kill and never swept. A
    `.removing.*` is only deleted if it holds nothing but the `skill` entry the uninstall moved
    into it. `.backup.*` is NOT swept here: after a rollback cut short it can hold the only copy
    of the user's previous install (see `_recover_leftover_backups`, which restores or discards
    it only when safe). There is no `.lock.tmp.*` to sweep any more -- the OS-held lock this
    module now uses has nothing analogous; see `held_lock()`."""
    for entry in _leftover_entries(dest_root, skill, "removing"):
        try:
            contents = os.listdir(entry.path)
        except OSError:
            continue
        if set(contents) <= {"skill"}:
            shutil.rmtree(entry.path, ignore_errors=True)
    for entry in _leftover_entries(dest_root, skill, "staging"):
        shutil.rmtree(entry.path, ignore_errors=True)


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
    """Discard the failed staging attempt, and
    if a previous install was moved aside into backup_dir and nothing currently occupies
    skill_dest, restore it.

    Interrupt-deferred (SIGINT and SIGTERM), so a signal arriving mid-rollback can't abandon it partway: two of this
    function's three call sites (the `except` handlers in install_skill()) run after the
    `with _sigterm_as_system_exit()` block that wrapped the primary staged work has already
    exited -- the original failure, whether an ordinary exception or a caught SIGTERM, has
    already propagated past it -- so a second, closely-timed SIGTERM here would otherwise
    terminate the process mid-rollback and leave a real, un-swept orphaned
    `.{skill}.staging.*`/`.{skill}.backup.*` directory behind (unlike held_lock()'s own
    cleanup, this one is not self-healing). Deferring, not converting to SystemExit, is what
    actually prevents that: a converted signal would just interrupt the rollback itself. The
    third call site (the dedicated backup-failure early return) is still *inside* that outer
    block, so this nests -- safe: each entry saves whatever handler is current and its exit
    restores exactly that, LIFO. A signal deferred here surfaces as SystemExit(130) when this
    function returns (or raises), into the outer block's own handling.
    """
    with _defer_interrupts():
        if stage_dir is not None and stage_dir.exists():
            shutil.rmtree(stage_dir, ignore_errors=True)
        if backup_dir is not None and backup_dir.exists():
            backed_up_skill = backup_dir / "skill"
            if not skill_dest.exists() and backed_up_skill.exists():
                os.replace(backed_up_skill, skill_dest)
                # install.sh golden-tests this exact line (test_install_legacy_golden.py /
                # test_install_rollback.py): a rollback restore is worth surfacing to the
                # caller even though this function otherwise just returns results.
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
        with held_lock(dest_root, skill_id, wait_timeout=wait_timeout):
            # Unprotected otherwise: a signal landing here (after the lock's own conversion has
            # exited, before the primary work's) hit the default disposition instead of the
            # engine's clean exit 130. Both calls are safe to interrupt and retry -- the next run
            # repairs whatever they leave, same as any other hard kill.
            with _sigterm_as_system_exit():
                _sweep_leftovers(dest_root, skill_id)
                _recover_leftover_backups(dest_root, skill_id, skill_dest)
            stage_dir: Path | None = None
            backup_dir: Path | None = None
            # SIGTERM (a supervisor kill, CI timeout) must reach the same cleanup path as
            # SIGINT/KeyboardInterrupt below -- Python has no built-in conversion for it.
            with _sigterm_as_system_exit():
                try:
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
                    # An interrupt terminates the whole run (exit 130) rather than falling through
                    # to per-skill failure bookkeeping the way an ordinary validation failure does
                    # (which returns 1 and lets a multi-skill loop continue to the next skill).
                    # Re-raising after cleanup propagates it out through this `with held_lock(...)` block --
                    # whose own `finally` still releases the lock on the way out, same as any other
                    # exit path -- instead of being swallowed into a normal InstallOutcome that a
                    # future multi-skill caller could mistake for just one more failed skill.
                    try:
                        _cleanup_failed_install(stage_dir, backup_dir, skill_dest)
                    except Exception as cleanup_exc:
                        # Best-effort: the interrupt is what must propagate. Letting an OSError
                        # from a failed rollback escape here would reach the outer
                        # `except (LockTimeoutError, OSError)`, turn into a "failed" outcome, and
                        # let a multi-skill run carry on after being told to stop.
                        print(f"warning: cleanup after interrupt failed: {cleanup_exc}", file=sys.stderr)
                    raise
                except Exception as exc:
                    _cleanup_failed_install(stage_dir, backup_dir, skill_dest)
                    message = str(exc) if str(exc) else f"{type(exc).__name__} during install"
                    return InstallOutcome(skill_id, skill_dest, "failed", message)

            if backup_dir is not None:
                with _defer_interrupts():
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
        if dry_run:
            # Read-only, so no dest_root creation and no lock (install's dry run returns before
            # its lock too): a dry run must not touch the disk at all.
            classification = classify_install_destination(skill_dest, skill_id=skill_id)
            if classification == OWNERSHIP_ABSENT:
                return UninstallOutcome(skill_id, skill_dest, "absent", f"not installed: {skill_dest}")
            if classification in _BLOCKING_OWNERSHIP_STATES:
                message = _UNINSTALL_BLOCK_MESSAGES[classification].format(dest=skill_dest)
                return UninstallOutcome(skill_id, skill_dest, "failed", message)
            return UninstallOutcome(skill_id, skill_dest, "dry_run", f"would remove {skill_dest}")

        dest_root.mkdir(parents=True, exist_ok=True)
        with held_lock(dest_root, skill_id, wait_timeout=wait_timeout):
            with _sigterm_as_system_exit():
                _sweep_leftovers(dest_root, skill_id)
                _recover_leftover_backups(dest_root, skill_id, skill_dest)
            classification = classify_install_destination(skill_dest, skill_id=skill_id)
            if classification == OWNERSHIP_ABSENT:
                return UninstallOutcome(skill_id, skill_dest, "absent", f"not installed: {skill_dest}")
            if classification in _BLOCKING_OWNERSHIP_STATES:
                message = _UNINSTALL_BLOCK_MESSAGES[classification].format(dest=skill_dest)
                return UninstallOutcome(skill_id, skill_dest, "failed", message)

            removing_dir: Path | None = None
            try:
                # Renamed aside first and deleted from there, so the destination is atomically
                # either the intact install or absent. An in-place rmtree that failed or was
                # interrupted partway left a half-deleted directory whose manifest was already
                # gone -- classified "unowned", so neither uninstall nor install would touch it
                # again and only a manual `rm -rf` recovered.
                with _sigterm_as_system_exit():
                    try:
                        removing_dir = Path(tempfile.mkdtemp(dir=dest_root, prefix=f".{skill_id}.removing."))
                        os.replace(skill_dest, removing_dir / "skill")
                    except BaseException:
                        if removing_dir is not None:
                            # Deferred: a second signal here would otherwise interrupt the
                            # restore itself and strand the install in the hidden directory.
                            with _defer_interrupts():
                                if (removing_dir / "skill").exists() and not skill_dest.exists():
                                    os.replace(removing_dir / "skill", skill_dest)
                                shutil.rmtree(removing_dir, ignore_errors=True)
                        raise
                # The skill is gone from its destination; finishing the deletion of what was
                # moved aside must not be abandoned by a second signal (nothing sweeps it).
                with _defer_interrupts():
                    shutil.rmtree(removing_dir)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as exc:
                message = str(exc) if str(exc) else f"{type(exc).__name__} during uninstall"
                if removing_dir is not None and not skill_dest.exists() and removing_dir.exists():
                    message = f"removed {skill_dest} but could not delete the leftover at {removing_dir}: {message}"
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
    "installed": ("", "stdout"),
    "uninstalled": ("", "stdout"),
    "dry_run": ("dry-run: ", "stdout"),
    "absent": ("warning: ", "stderr"),
    "failed": ("error: ", "stderr"),
}


def print_outcome(outcome: InstallOutcome | UninstallOutcome) -> None:
    # The stream is looked up at print time, not captured at import: a caller that has
    # redirected sys.stdout/sys.stderr (contextlib.redirect_stdout, a test's capture) must see
    # the output.
    prefix, stream_name = _PRESENTATION[outcome.status]
    print(f"{prefix}{outcome.message}", file=getattr(sys, stream_name))


def _env_float(name: str, default: float) -> float:
    # An empty value falls back to the default exactly like an unset one (bash's
    # `${VAR:-default}` semantics, which the old bash lock used for these two env vars), rather
    # than failing float() with an empty string.
    value = os.environ.get(name, "")
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"{name} must be a number, got {value!r}") from None


def _lock_timing_from_env() -> float:
    # scripts/tests/test_install_concurrency.py sets this to exercise the timeout behavior
    # without waiting out a real-world-sized delay.
    wait_timeout = _env_float("LOCK_WAIT_TIMEOUT_SECONDS", DEFAULT_LOCK_WAIT_TIMEOUT_SECONDS)
    # float() accepts "nan"/"inf"/negatives; nan or inf here would wait forever.
    if not (math.isfinite(wait_timeout) and wait_timeout >= 0):
        raise ValueError(f"LOCK_WAIT_TIMEOUT_SECONDS must be a finite number >= 0, got {wait_timeout!r}")
    return wait_timeout


def _start_parent_watch(expected_parent: int, poll_seconds: float = _PARENT_POLL_SECONDS) -> None:
    """Stop this process (SIGTERM to itself, so the normal rollback runs) once it is no longer a
    child of `expected_parent`. `install.sh` runs the engine as a child; if bash is SIGKILLed the
    engine is reparented to init and used to carry on to completion unsupervised, holding the
    lock. `expected_parent` is `install.sh`'s own pid, passed by it (`INSTALL_ENGINE_EXIT_WITH_
    PARENT=$$`) rather than read from `os.getppid()` here: reading it here would only catch a
    kill *after* this process finished starting up, missing one landing during interpreter
    start-up and imports (already reparented to init by the time a late snapshot ran) -- the
    caller's own pid is known before the child even exists, so the check covers the whole
    lifetime. Checked once immediately (a kill that raced the fork itself) and then on the poll.
    Opt-in because a user who backgrounds the engine directly and closes their shell has not
    asked for it to be stopped. POSIX only: Windows has no reparenting to detect."""
    if sys.platform == "win32":
        return

    def _stop_if_orphaned() -> bool:
        if os.getppid() != expected_parent:
            os.kill(os.getpid(), signal.SIGTERM)
            return True
        return False

    if _stop_if_orphaned():
        return

    def _watch() -> None:
        while True:
            time.sleep(poll_seconds)
            if _stop_if_orphaned():
                return

    threading.Thread(target=_watch, name="install-engine-parent-watch", daemon=True).start()


def _cli_install(args: argparse.Namespace) -> int:
    wait_timeout = _lock_timing_from_env()
    try:
        outcome = install_skill(
            args.skill_id,
            repo_root=args.repo_root,
            dest_root=args.dest_root,
            host_label=args.host_label,
            dry_run=args.dry_run,
            wait_timeout=wait_timeout,
        )
    except (KeyboardInterrupt, SystemExit):
        # install_skill() already ran its own cleanup before re-raising (see the
        # (KeyboardInterrupt, SystemExit) handler inside it -- SystemExit is how
        # _sigterm_as_system_exit() converts a SIGTERM into the same cleanup path); 130 is
        # what install.sh's run_engine and sb's batch loop key on, and they must treat it as a
        # whole-run abort, not a per-skill failure to continue past.
        return 130
    print_outcome(outcome)
    return 1 if outcome.status == "failed" else 0


def _cli_uninstall(args: argparse.Namespace) -> int:
    wait_timeout = _lock_timing_from_env()
    try:
        outcome = uninstall_skill(
            args.skill_id,
            dest_root=args.dest_root,
            dry_run=args.dry_run,
            wait_timeout=wait_timeout,
        )
    except (KeyboardInterrupt, SystemExit):
        return 130
    print_outcome(outcome)
    return 1 if outcome.status == "failed" else 0


def main(argv: list[str] | None = None) -> int:
    # Outcome messages contain non-ASCII characters (the U+2192 arrow, matching install.sh's
    # own historical bash `echo` text byte-for-byte -- bash's echo writes raw bytes regardless
    # of locale, but Python's print() is locale-aware and raises UnicodeEncodeError under a
    # restrictive locale like LC_ALL=C. Force UTF-8 output so a successful install can't crash
    # on its own success message and get misreported as failed.
    for stream in (sys.stdout, sys.stderr):
        # Not every stream has it (an in-process caller may have swapped in a StringIO).
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

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
    expected_parent_raw = os.environ.get(_EXIT_WITH_PARENT_ENV)
    if expected_parent_raw:
        try:
            _start_parent_watch(int(expected_parent_raw))
        except ValueError:
            pass  # malformed env value: not this process's job to fail the run over
    try:
        return args.func(args)
    except Exception as exc:
        # A catch-all clean-failure net: install_skill()/uninstall_skill() already convert
        # their own realistic failures into a clean InstallOutcome/UninstallOutcome, but a
        # few things run before either is even called (_lock_timing_from_env() reading a
        # malformed, non-empty LOCK_WAIT_TIMEOUT_SECONDS, for example) --
        # this must not surface as a raw traceback. Returns 1, not a new exit code, so
        # install.sh's existing {0, 1, 130} handling doesn't need to learn a fourth case.
        # Doesn't catch KeyboardInterrupt/SystemExit (both are BaseException, not Exception);
        # args.func's own handlers already cover those.
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
