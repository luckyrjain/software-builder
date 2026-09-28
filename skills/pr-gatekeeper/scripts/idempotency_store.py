#!/usr/bin/env python3
"""Reference file-based idempotency store + per-MR lock for pr-gatekeeper integrators.

Not invoked by the skill itself — webhook handlers call this (or equivalent) before
dispatching pr-gatekeeper. See reference/idempotency.md.

Hardening (see docs/superpowers/specs/2026-09-27-f4-idempotency-hardening-design.md,
revision 4): an optional bounded lock-wait (``--lock-wait-timeout``, exit 3 on timeout,
naming the current holder's pid), an fsync step before the atomic record replace, and
signal forwarding to ``run-if-new``'s child subprocess (exit 4 when interrupted). Every
flag/exit-code addition here is additive — codes 0/1/2 and every existing caller's
behavior when the new flag is omitted are byte-for-byte unchanged.

Platform support (see docs/superpowers/specs/2026-09-27-f2-platform-support-design.md): this
file requires ``fcntl`` (POSIX only). The import is guarded (mirroring
``scripts/plan_state_store.py``/``scripts/task_lease.py``'s own independently-duplicated
convention, not a shared helper) so a Windows import doesn't crash with a raw
``ModuleNotFoundError`` — ``mr_lock()`` itself raises ``UnsupportedPlatformError`` the moment
it's actually invoked on a platform where the import failed, since this file's documented
"Python handler" integration style (reference/idempotency.md) calls ``mr_lock()``/
``should_process()``/``mark_processed()`` directly, bypassing ``main()``. ``main()`` catches it
and exits ``5`` (codes 0-4 are already spoken for) with a clean message; a direct caller sees
the exception itself.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import signal
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

try:  # POSIX
    import fcntl
except ImportError:  # pragma: no cover - not POSIX
    fcntl = None  # type: ignore[assignment]

_SLUG_MAX_LENGTH = 128

# Mirrors install_engine.py's own poll-and-timeout philosophy (see held_lock()), but at a
# finer interval: this file's expected wait_timeout values are seconds, not the tens of
# seconds install_engine.py's DEFAULT_LOCK_WAIT_TIMEOUT_SECONDS=30 assumes, so a 1.0s poll
# there would leave a short bounded wait here with too few samples to time out promptly.
_LOCK_POLL_INTERVAL_SECONDS = 0.05

# Byte 0 is reserved, unused on this POSIX/fcntl-only file, purely to mirror
# install_engine.py's cross-platform layout (where it holds the mandatory Windows
# byte-range lock). The pid-diagnostic text lives at this offset instead, matching
# install_engine.py's own _PID_TEXT_OFFSET convention exactly.
_PID_TEXT_OFFSET = 1


class LockTimeoutError(RuntimeError):
    """Raised when mr_lock's optional wait_timeout elapses before the lock is acquired."""


class UnsupportedPlatformError(RuntimeError):
    """Raised by ``mr_lock()`` when the guarded ``import fcntl`` failed (this platform has no
    ``fcntl``, i.e. not POSIX). Raised inside ``mr_lock()`` itself, not just ``main()``, since a
    "Python handler" integrator (reference/idempotency.md) calls ``mr_lock()``/
    ``should_process()``/``mark_processed()`` directly, bypassing ``main()`` entirely — ``main()``
    catches this and exits ``5`` with a clean message; a direct caller sees this exception."""


def _safe_slug(value: str) -> str:
    """Sanitize an untrusted string for use as a filename/path segment.

    Follows docs/skill-framework/shared/safe-output.md Rule 1: keep only
    ``[A-Za-z0-9._-]`` (replacing every other character, including path
    separators and null bytes, with ``_``), collapse a result that is empty
    or all dots, neutralize a leading ``-``, and cap the length.
    """
    slug = re.sub(r"[^A-Za-z0-9._-]", "_", value)
    if not slug or set(slug) == {"."}:
        slug = "_"
    elif slug.startswith("-"):
        slug = "_" + slug[1:]
    return slug[:_SLUG_MAX_LENGTH]


def _store_path(root: Path, project: str, merge_request_iid: int) -> Path:
    safe_project = _safe_slug(project)
    return root / safe_project / f"mr-{merge_request_iid}.json"


def _open_lock_file(lock_path: Path) -> int:
    """Non-truncating open, matching install_engine.py's own ``_open_lock_file`` exactly.

    The previous ``open(lock_path, "w", ...)`` truncated on *every* open, including a
    losing contender's — corrupting whatever pid-diagnostic bytes the current holder had
    already written there. ``O_CREAT`` without ``O_TRUNC`` lets the file's content survive
    every open after the first.
    """
    return os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)


def _try_lock(fd: int) -> bool:
    """Non-blocking attempt at the OS's own exclusive lock on ``fd``. True on success."""
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _write_holder_pid(fd: int) -> None:
    """Diagnostics only: never read back to decide anything, only to name a holder in a
    LockTimeoutError message. A failure here must not fail the acquisition itself. Writes at
    ``_PID_TEXT_OFFSET``, past the reserved byte 0 — see that constant's comment. Truncates the
    diagnostic region first (matching install_engine.py's ``_write_holder_pid``) so a shorter
    new pid never leaves a stale trailing digit from a longer previous one.
    """
    try:
        os.ftruncate(fd, 0)
        os.lseek(fd, _PID_TEXT_OFFSET, os.SEEK_SET)
        os.write(fd, str(os.getpid()).encode("ascii"))
    except OSError:
        pass


def _read_holder_pid(fd: int) -> str:
    try:
        os.lseek(fd, _PID_TEXT_OFFSET, os.SEEK_SET)
        return os.read(fd, 32).decode("ascii", errors="replace").strip() or "unknown"
    except OSError:
        return "unknown"


def _fsync(fd: int) -> None:
    """Flush to the device: macOS `fsync` only reaches the drive's cache, `F_FULLFSYNC` goes
    further. Adapted from skills/loop-task-implementer/scripts/run_log.py's own ``_fsync`` —
    copied rather than imported so this reference file has no runtime dependency on
    loop-task-implementer's own, independently-versioned script."""
    full = getattr(fcntl, "F_FULLFSYNC", None)
    if full is not None:
        try:
            fcntl.fcntl(fd, full)
            return
        except OSError:
            pass
    os.fsync(fd)


def _fsync_dir(directory: Path) -> None:
    """Adapted from run_log.py's own ``_fsync_dir`` — see ``_fsync``'s docstring."""
    try:
        dir_fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:  # pragma: no cover - some filesystems refuse it
        pass
    finally:
        os.close(dir_fd)


@contextmanager
def mr_lock(
    root: Path,
    project: str,
    merge_request_iid: int,
    *,
    wait_timeout: float | None = None,
) -> Iterator[None]:
    """Acquire the per-(project, merge_request_iid) exclusive lock for the ``with`` block.

    ``wait_timeout=None`` (the default — every existing caller gets this since none pass it)
    waits genuinely unbounded via a single blocking ``fcntl.flock(fd, fcntl.LOCK_EX)`` call,
    byte-for-byte the same call this lock has always made. Passing a numeric ``wait_timeout``
    instead polls with ``LOCK_EX | LOCK_NB`` (mirroring install_engine.py's ``held_lock()``),
    raising ``LockTimeoutError`` naming the current holder's pid once the timeout elapses.

    The pid-diagnostic bytes are (re)written on every successful acquisition — ``check``,
    ``mark``, and ``run-if-new`` alike, bounded or unbounded — not only when a bounded wait was
    requested, so a concurrently-waiting bounded caller's timeout error always names the real
    current holder rather than a stale one.

    Raises :class:`UnsupportedPlatformError` immediately, before touching the filesystem, if the
    guarded ``import fcntl`` at module load failed — this platform has no ``fcntl`` (not POSIX).
    """
    if fcntl is None:
        raise UnsupportedPlatformError(
            "idempotency_store requires a POSIX platform (fcntl); this platform is not supported"
        )
    lock_dir = root / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    safe_project = _safe_slug(project)
    lock_path = lock_dir / f"{safe_project}-mr-{merge_request_iid}.lock"
    fd = _open_lock_file(lock_path)
    try:
        if wait_timeout is None:
            fcntl.flock(fd, fcntl.LOCK_EX)
        else:
            waited = 0.0
            while not _try_lock(fd):
                if waited >= wait_timeout:
                    raise LockTimeoutError(
                        f"timed out after {wait_timeout}s waiting for the lock on project "
                        f"{project!r} mr {merge_request_iid} at {lock_path} "
                        f"(held by pid {_read_holder_pid(fd)})"
                    )
                time.sleep(_LOCK_POLL_INTERVAL_SECONDS)
                waited += _LOCK_POLL_INTERVAL_SECONDS
        _write_holder_pid(fd)
        try:
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        os.close(fd)


def load_record(root: Path, project: str, merge_request_iid: int) -> dict[str, Any]:
    path = _store_path(root, project, merge_request_iid)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_record(root: Path, project: str, merge_request_iid: int, record: dict[str, Any]) -> None:
    path = _store_path(root, project, merge_request_iid)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
            fh.flush()
            _fsync(fh.fileno())
        os.replace(tmp, path)
        _fsync_dir(path.parent)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def should_process(root: Path, project: str, merge_request_iid: int, head_sha: str) -> bool:
    """Double-checked locking helper: True when head_sha is new."""
    record = load_record(root, project, merge_request_iid)
    return record.get("last_processed_head_sha") != head_sha


def mark_processed(root: Path, project: str, merge_request_iid: int, head_sha: str) -> None:
    save_record(
        root,
        project,
        merge_request_iid,
        {"last_processed_head_sha": head_sha},
    )


def _forwardable_signals() -> list[int]:
    sigs = [signal.SIGINT, signal.SIGTERM]
    hangup = getattr(signal, "SIGHUP", None)
    if hangup is not None:
        sigs.append(hangup)
    return sigs


@contextmanager
def _forward_signals_to_child(proc: subprocess.Popen[Any]) -> Iterator[Callable[[], bool]]:
    """Install SIGINT/SIGTERM/SIGHUP handlers for the lifetime of this block only — from the
    moment the child (``proc``) exists until its ``wait()`` completes. Each forwards the
    received signal to the direct child only (``proc.send_signal()`` — no process groups, no
    ``os.killpg``), then lets the wrapper's own, already-in-flight ``proc.wait()`` continue
    exactly as it would today. Idempotent: a signal arriving while one is already in flight is a
    no-op, not a second forward.

    Scope is the whole point (see docs/superpowers/specs/2026-09-27-f4-idempotency-hardening-
    change-impact.md): this must never wrap ``mr_lock``'s lock-wait phase. Before a child
    exists, every signal's default disposition applies exactly as it did before this ticket —
    an uncaught SIGTERM/SIGHUP kills the process immediately, SIGINT's default handler raises
    KeyboardInterrupt — so the deliberately-preserved unbounded default lock-wait remains as
    interruptible as it always was.

    Main-thread only, matching install_engine.py's own established guard
    (``threading.current_thread() is not threading.main_thread()``): ``signal.signal()`` raises
    off the main thread, and a signal is delivered to the main thread regardless, so a caller
    running ``run_if_new`` from a worker thread is left with Python's default disposition
    instead of crashing.

    Yields a zero-argument callable returning whether a signal was actually forwarded, which the
    caller uses to unconditionally skip ``mark_processed`` for an interrupted run.
    """
    if threading.current_thread() is not threading.main_thread():
        yield lambda: False
        return

    signalled = False

    def _on_signal(signum: int, frame: object) -> None:
        nonlocal signalled
        if signalled:
            return
        signalled = True
        try:
            proc.send_signal(signum)
        except ProcessLookupError:
            pass

    previous: dict[int, Any] = {}
    try:
        for sig in _forwardable_signals():
            handler = signal.getsignal(sig)
            if handler == signal.SIG_IGN:
                # An ignored signal (nohup, an async child of a non-interactive shell) is the
                # caller's explicit choice; forwarding it anyway would override that.
                continue
            previous[sig] = handler
            signal.signal(sig, _on_signal)
        yield lambda: signalled
    finally:
        for sig, handler in previous.items():
            if handler is not None:
                signal.signal(sig, handler)  # type: ignore[arg-type]


def run_if_new(
    root: Path,
    project: str,
    merge_request_iid: int,
    head_sha: str,
    command: list[str],
    *,
    wait_timeout: float | None = None,
) -> int:
    """Acquire lock, skip when head_sha is duplicate, else run command and mark on success.

    Uses ``subprocess.Popen`` + an explicit ``.wait()`` (rather than ``subprocess.run``) so a
    stop signal (SIGINT/SIGTERM/SIGHUP) arriving while the child runs can be forwarded to it
    instead of silently orphaning it — see ``_forward_signals_to_child``. An interrupted run
    returns 4 and never calls ``mark_processed``, even if the child happened to exit 0 after the
    signal was forwarded to it.

    Disclosed trade-off, not a hidden regression (see reference/idempotency.md): a child that
    ignores the forwarded signal now makes this block in ``.wait()`` exactly as long as it
    already would today, requiring an operator-issued SIGKILL of the wrapper to reclaim the
    lock — whereas ``subprocess.run()``'s own internal exception handling previously killed an
    unresponsive child on SIGINT/an uncaught SIGTERM without any wait.
    """
    with mr_lock(root, project, merge_request_iid, wait_timeout=wait_timeout):
        if not should_process(root, project, merge_request_iid, head_sha):
            return 1
        proc = subprocess.Popen(command)
        with _forward_signals_to_child(proc) as was_signalled:
            returncode = proc.wait()
        if was_signalled():
            return 4
        if returncode == 0:
            mark_processed(root, project, merge_request_iid, head_sha)
        return returncode


def _validate_lock_wait_timeout(value: float | None) -> bool:
    """True when ``value`` is acceptable: ``None`` (unbounded) or a finite, non-negative
    number. A ``nan`` timeout would otherwise silently defeat its own bound, since ``waited >=
    nan`` is always false."""
    if value is None:
        return True
    return not (math.isnan(value) or math.isinf(value)) and value >= 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store-root", required=True, type=Path)
    parser.add_argument("--project", required=True)
    parser.add_argument("--merge-request-iid", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument(
        "--lock-wait-timeout",
        type=float,
        default=None,
        help=(
            "Seconds to wait for the per-MR lock before giving up with exit 3 (error names the "
            "current holder's pid). Applies to check/mark/run-if-new alike. Omit for the "
            "previous, unbounded wait. Must be finite and non-negative."
        ),
    )
    parser.add_argument(
        "action",
        choices=("check", "mark", "run-if-new"),
        help=(
            "check: exit 0 when new head, 1 when duplicate, 3 on an opted-in lock-wait timeout "
            "(lock held only for the check — use run-if-new for the full gatekeeper invocation); "
            "mark: persist head after successful run (under lock), 3 on an opted-in lock-wait "
            "timeout; "
            "run-if-new: hold lock (3 on timeout), skip duplicate heads (1), run trailing "
            "command, mark on exit 0, 4 if interrupted by a forwarded signal"
        ),
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command for run-if-new (prefix with -- before the command)",
    )
    args = parser.parse_args(argv)

    if not _validate_lock_wait_timeout(args.lock_wait_timeout):
        print(
            "error: --lock-wait-timeout must be a finite, non-negative number of seconds",
            file=sys.stderr,
        )
        return 2

    if args.action == "run-if-new":
        if not args.command or args.command[0] == "":
            print("error: run-if-new requires a command after --", file=sys.stderr)
            return 2
        cmd = args.command[1:] if args.command[0] == "--" else args.command
        if not cmd:
            print("error: run-if-new requires a command after --", file=sys.stderr)
            return 2
        try:
            return run_if_new(
                args.store_root,
                args.project,
                args.merge_request_iid,
                args.head_sha,
                cmd,
                wait_timeout=args.lock_wait_timeout,
            )
        except LockTimeoutError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 3
        except UnsupportedPlatformError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 5

    try:
        with mr_lock(
            args.store_root,
            args.project,
            args.merge_request_iid,
            wait_timeout=args.lock_wait_timeout,
        ):
            if args.action == "check":
                return 0 if should_process(args.store_root, args.project, args.merge_request_iid, args.head_sha) else 1
            mark_processed(args.store_root, args.project, args.merge_request_iid, args.head_sha)
            return 0
    except LockTimeoutError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except UnsupportedPlatformError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
