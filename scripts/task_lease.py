"""Non-blocking, flock-based mutual exclusion over a deterministic ``(repo, base_branch, task_id)``
identity (gap-backlog A6) -- answers "is anyone already working this task on this machine" before
the Orchestrator dispatches a Builder.

**Why ``try_acquire``, not ``acquire``.** Every other lock this repository ships --
``install_engine.py``'s ``held_lock()``, ``run_log.py``'s ``_locked``, ``plan_state_store.py``'s
``cas_advance`` -- blocks, bounded by a timeout, until the OS reports the lock free. Naming this
primitive ``acquire`` would read as one more of those. It is not: it attempts
``fcntl.flock(fd, LOCK_EX | LOCK_NB)`` exactly once and returns immediately either way. The name says
so on sight, and the ``None`` return (rather than raising) is the correspondingly explicit signal
for the expected, common case -- a peer already working this task -- as opposed to an infrastructure
failure (see :class:`TaskLeaseError` below).

**Why non-blocking rather than timeout-bounded.** The ticket's own acceptance criterion is "no double
execution," not "queue and wait": a Builder dispatch is expensive, and the useful response to
contention is for the Orchestrator to immediately select a different task (or escalate), not to sit
idle hoping the peer finishes first. A blocking, timeout-bounded lease would additionally need to
answer "how long is reasonable to wait for someone else's task," a question this design does not need
to answer at all by staying strictly fail-fast.

**Why deterministic, unlike ``run_id``.** ``run_log.py``'s ``run-id`` is deliberately time-seeded, so
that resuming the same task later is a *new* run with its own audit trail -- see that module's own
rationale. A lease identity needs the opposite property: the same ``(repo, base_branch, task_id)``
triple must always derive the same lease id, on this invocation and on any later one, so that two
Orchestrator processes racing for the same task actually contend for the same lock file rather than
each getting their own. :func:`derive_lease_id` therefore takes no timestamp, unlike
``run_log.derive_run_id``, even though the two functions otherwise hash a very similar tuple of
inputs.

**Consistency model, stated plainly (mirrors the design doc's own Consistency section).** A held
lease answers "is anyone actively working this task *right now*, from a process still alive on this
machine" -- it is process-lifetime scoped, single-machine only, and says nothing about the durable,
survives-a-restart status a plan's own checkpoint (``plan_state_store.py``) already tracks. The two
are independent mechanisms, not layered: a crashed Builder can leave ``task_statuses[task_id] ==
"BUILDING"`` in the durable store with no lease currently held (the OS released the flock the instant
the crashed process's fd closed) -- a successful :func:`try_acquire` on that same task's lease id is
the concrete, checkable signal that the prior claimant is actually gone, not a license to skip the
Orchestrator's own independent SCM re-verification before resuming it.

**Directory/file conventions** mirror ``scripts/plan_state_store.py``'s own ``resolve_state_dir``/
``_private_dir`` exactly -- same ``<home>/.software-builder/...`` layout (default
``~/.software-builder/task-leases/``), same ``0700``/``0600`` permissions, same repository-exclusion
and symlink/ownership refusal, same duplicated-rather-than-imported shape (``plan_state_store.py``'s
own docstring explains why: these are underscore-prefixed internals of independently evolving,
individually hardened modules, not a published shared API).

**Failure-mode separation, made structural, not just documented.** A denied lease (:func:`try_acquire`
returning ``None``) and an infrastructure failure (disk full, permission error, a filesystem that
cannot be written to) are different outcomes with different required responses -- the first is
ordinary, expected contention the caller should route around by picking a different task; the second
is a systemic problem that must escalate, and silently treating it as "task already claimed" would
incorrectly stop all progress on every task while masking the real fault. :func:`try_acquire`
therefore raises :class:`TaskLeaseError` for the second case and never returns ``None`` for it, so a
caller that only checks ``is None`` can never conflate the two.

**Lock state machine, deliberately minimal** (matching ``install_engine.py``'s ``held_lock()`` and
``run_log.py``'s own repeatedly-reaffirmed philosophy): ``unheld -> held`` on a successful
:func:`try_acquire`; ``held -> unheld`` on :meth:`LeaseHandle.release` or simply the holding process
exiting, which closes the fd and lets the OS release the flock immediately. There is no "stale," no
"expired," no "reclaimed" state, and no stale-lease reclaim logic to get wrong: a hung-but-alive
holder correctly keeps the lease held (that is mutual exclusion working as intended, not a bug), and a
crashed holder's lease is released the instant its fd closes, by the kernel, with nothing this module
needs to detect, age, or judge the liveness of.

POSIX only (Linux, macOS): it needs ``flock``, matching ``run_log.py``'s and ``plan_state_store.py``'s
own POSIX-only scope.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path
from types import TracebackType

try:  # POSIX
    import fcntl
except ImportError:  # pragma: no cover - not POSIX
    fcntl = None  # type: ignore[assignment]


_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9._][A-Za-z0-9._-]{0,127}")


class TaskLeaseError(ValueError):
    """Base error for this module: an infrastructure failure while preparing or opening a lease --
    a directory or lock file that could not be created, opened, or trusted (disk full, permission
    error, a filesystem that refuses the write, a symlinked or other-user-owned lease directory).

    This is a **different** outcome from :func:`try_acquire` returning ``None`` for an ordinary
    contended lease, and callers MUST treat it as "cannot determine whether this task is leased,"
    never as "someone else has it" -- see this module's docstring on why the two must never be
    conflated.
    """


# --- directory/path resolution (mirrors plan_state_store.py's own conventions; see module docstring) --


def _home_dir() -> Path:
    """The account's home directory, not $HOME: the environment is not a place to take a store
    location from."""
    try:
        import pwd

        return Path(pwd.getpwuid(os.geteuid()).pw_dir)
    except (ImportError, KeyError):  # pragma: no cover - Windows / odd accounts
        return Path.home()


def _within(child: str, parent: str) -> bool:
    child_real, parent_real = os.path.realpath(child), os.path.realpath(parent)
    try:
        return os.path.commonpath([child_real, parent_real]) == parent_real
    except ValueError:
        return False


def _is_repo_root(path: Path) -> bool:
    """A real git repository root, not a stub ``.git`` an attacker planted to make the check misfire."""
    git = path / ".git"
    try:
        if git.is_file():
            return git.read_text(encoding="utf-8", errors="ignore").startswith("gitdir:")
        if git.is_dir():
            return (git / "HEAD").is_file()
        return (path / "HEAD").is_file() and (path / "objects").is_dir() and (path / "refs").is_dir()  # bare
    except OSError:
        return False


def _enclosing_repo(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if _is_repo_root(candidate):
            return candidate
    return None


def _refuse_repository(directory: Path) -> None:
    """Refuse a directory that sits inside any git repository, whatever the current directory is. A
    Builder edits its own working tree; if the lease directory sat inside a repo (or inside a
    Builder's worktree), Builder-authored content could tamper with lease state it must never touch
    -- the same reason ``run_log.py``/``plan_state_store.py`` refuse this for their own directories."""
    chain = [Path(os.path.realpath(directory))]
    chain.extend(chain[0].parents)
    for ancestor in chain:
        if _is_repo_root(ancestor):
            raise TaskLeaseError(
                f"the task-lease directory must be outside any git repository (found one at {ancestor})"
            )
    known = [repo for repo in (_enclosing_repo(Path.cwd().resolve()),) if repo is not None]
    known += [Path(value) for value in (os.environ.get("GIT_DIR"), os.environ.get("GIT_WORK_TREE")) if value]
    if os.environ.get("GIT_DIR") and not os.environ.get("GIT_WORK_TREE"):
        known.append(Path.cwd())  # git treats the current directory as the work tree in that case
    for repo in known:
        for ancestor in chain:
            try:
                if ancestor.exists() and repo.exists() and os.path.samefile(ancestor, repo):
                    raise TaskLeaseError(f"the task-lease directory must be outside the repository at {repo}")
            except OSError:
                continue


def resolve_lease_dir(explicit: str | os.PathLike[str] | None) -> Path:
    """The directory leases may live in: absolute, no ``..``, and outside every git repository.

    Defaults to ``<home>/.software-builder/task-leases``, mirroring ``plan_state_store.py``'s
    ``resolve_state_dir`` exactly (same ``~``/``~/...`` handling, same repository-exclusion check).
    """
    if explicit is not None and str(explicit) == "":
        raise TaskLeaseError("lease_dir must not be empty")
    raw = str(explicit) if explicit else ""
    if raw.startswith("~") and raw != "~" and not raw.startswith("~/"):
        raise TaskLeaseError("only a plain '~' (this account's home) is supported in lease_dir, not ~user")
    directory = (
        _home_dir() / raw[2:] if raw.startswith("~/") else _home_dir() if raw == "~"
        else Path(raw) if raw else _home_dir() / ".software-builder" / "task-leases"
    )
    if not directory.is_absolute():
        raise TaskLeaseError(f"the task-lease directory must be an absolute path, got {str(directory)!r}")
    if ".." in directory.parts:
        raise TaskLeaseError("the task-lease directory must not contain '..'")
    _refuse_repository(directory)
    return directory


def _validate_lease_id(lease_id: object) -> str:
    if not isinstance(lease_id, str) or not _IDENTIFIER_RE.fullmatch(lease_id) or lease_id in {".", ".."}:
        raise TaskLeaseError("lease_id must be 1-128 characters of [A-Za-z0-9._-], not starting with '-'")
    return lease_id


def _lease_path(lease_dir: Path, lease_id: str) -> Path:
    lease_id = _validate_lease_id(lease_id)
    directory = Path(lease_dir)
    path = directory / f"{lease_id}.lock"
    if not _within(str(path), str(directory)) or os.path.realpath(path.parent) != os.path.realpath(directory):
        raise TaskLeaseError("the task-lease path escapes its directory")
    return path


def _private_dir(directory: Path) -> None:
    """Create ``directory`` (and the missing parents) private to this user; refuse one that already
    exists and is reachable by others, is not ours, or is the home directory (it is not ours to
    chmod) -- mirrors ``plan_state_store.py``'s ``_private_dir`` exactly."""
    if directory.is_symlink():
        raise TaskLeaseError(f"refusing to use a symlinked task-lease directory: {directory}")
    missing: list[Path] = []
    probe = directory
    while not probe.exists() and probe != probe.parent:
        missing.append(probe)
        probe = probe.parent
    for created in reversed(missing):  # makedirs(mode=) only applies to the leaf, so do each level
        try:
            os.mkdir(created, 0o700)
        except FileExistsError:
            pass
    if not os.path.isdir(directory) or directory.is_symlink():
        raise TaskLeaseError(f"not a directory: {directory}")
    info = os.lstat(directory)
    if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
        raise TaskLeaseError(f"refusing to use a task-lease directory owned by another user: {directory}")
    if info.st_mode & 0o077:
        # Not ours to chmod: a directory that already exists may hold other things, and tightening
        # it would change who can reach them. Only directories this call created are 0700.
        raise TaskLeaseError(
            f"the task-lease directory is accessible to others; do not change its permissions; "
            f"ask the caller for a private lease_dir: {directory}"
        )
    try:
        is_home = os.path.samefile(directory, _home_dir())
    except OSError:  # an account whose home directory was never created cannot be the lease directory
        is_home = False
    if is_home:
        raise TaskLeaseError("refusing to use the home directory itself as the task-lease directory")


def _open_lock(path: Path) -> int:
    fd = os.open(
        path,
        os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        0o600,
    )
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise TaskLeaseError(f"the task-lease lock path is not a regular file: {path}")
        if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
            raise TaskLeaseError(f"refusing to use a task-lease lock owned by another user: {path}")
        if info.st_mode & 0o077:
            os.fchmod(fd, 0o600)
    except BaseException:
        os.close(fd)
        raise
    return fd


# --- derived identity -------------------------------------------------------------------------


def derive_lease_id(repo: str, base_branch: str, task_id: str) -> str:
    """The deterministic lease id for a ``(repo, base_branch, task_id)`` triple: ``"lease-" +
    SHA256(f"{repo}|{base_branch}|{task_id}")[:16]``. No timestamp -- see this module's docstring
    on why that is the one deliberate structural difference from ``run_log.derive_run_id``. The
    same three inputs always produce the same id, on this call and any later one, which is what
    makes it usable as a mutual-exclusion identity rather than an audit-trail one."""
    digest = hashlib.sha256(f"{repo}|{base_branch}|{task_id}".encode("utf-8")).hexdigest()
    return f"lease-{digest[:16]}"


# --- public API --------------------------------------------------------------------------------


class LeaseHandle:
    """A held lease, wrapping the open fd whose flock is the lease. Usable as a context manager
    (``with task_lease.try_acquire(...) as handle:``) for the common case where the lease should be
    held for exactly one ``with`` block's scope; :meth:`release` is idempotent, matching
    ``plan_state_store``'s own release pattern -- closing an already-closed fd is a no-op, not an
    error, so a caller does not need to track whether it already released."""

    __slots__ = ("_fd",)

    def __init__(self, fd: int) -> None:
        self._fd: int | None = fd

    def release(self) -> None:
        """Close the held fd. The OS releases the flock the instant the fd (and every dup of it)
        closes -- there is nothing else to undo. Safe to call more than once."""
        fd, self._fd = self._fd, None
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass

    def __enter__(self) -> "LeaseHandle":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()


def try_acquire(lease_dir: Path, lease_id: str) -> LeaseHandle | None:
    """Attempt to claim the lease for ``lease_id`` inside ``lease_dir``, once, without blocking.

    Opens (creating if absent) ``<lease_dir>/<lease_id>.lock`` -- the directory is created and
    validated with the same private-directory conventions as ``plan_state_store.py``'s
    ``_private_dir`` (outside any git repository, ``0700``/``0600``, symlink/ownership refusal) --
    then attempts ``fcntl.flock(fd, LOCK_EX | LOCK_NB)`` exactly once.

    Returns a :class:`LeaseHandle` wrapping the open fd on success. Returns ``None`` immediately
    when the lease is already held by another open file description -- including, deliberately, a
    second call from *this same process*: ``flock`` binds to the open-file-description a call opens
    fresh each time, not to the process, so a same-process double :func:`try_acquire` for the same
    ``lease_id`` correctly contends with the first call's still-held lock rather than self-deadlocking
    or silently succeeding a second time.

    Raises :class:`TaskLeaseError` -- never returns ``None`` -- when the lease directory or lock
    file could not be created, opened, or trusted (disk full, permission error, a filesystem that
    refuses the write, a symlinked or other-user-owned lease directory/file). This is a structurally
    different code path from the plain-contention ``None`` case: a caller must never treat an
    infrastructure failure as "task already claimed," which would incorrectly halt all progress on
    every task while masking a systemic fault.
    """
    if fcntl is None:  # pragma: no cover - not POSIX
        raise TaskLeaseError("task_lease requires a POSIX platform (flock)")
    lease_id = _validate_lease_id(lease_id)
    directory = Path(lease_dir)
    try:
        _private_dir(directory)
        path = _lease_path(directory, lease_id)
        fd = _open_lock(path)
    except TaskLeaseError:
        raise
    except OSError as exc:
        raise TaskLeaseError(
            f"could not prepare the task-lease directory/file for {lease_id!r} under {directory}: {exc}"
        ) from exc

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        # Contention, the expected/common outcome, not an infrastructure failure: another open file
        # description (this process's own earlier call, or a peer's) already holds the lock.
        os.close(fd)
        return None
    return LeaseHandle(fd)
