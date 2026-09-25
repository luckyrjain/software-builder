"""Durable, locked, atomic on-disk backing for one plan's ``plan_execution_state`` (gap-backlog A5).

``plan_execution_state`` has always been an in-memory, host/runtime-held checkpoint: the CAS
reconciliation logic (``scripts/implementation_plan.py``'s ``advance_plan_execution_state``,
``initial_plan_execution_state``, ``reconcile_plan_execution_state``) is already implemented and
already tested, but nothing in the repository ever wrote that state to disk. A Builder or
Orchestrator process that died mid-task lost every bit of in-flight plan progress, recoverable only
by restarting the whole task from scratch (see the A5 architecture review and system design at
``docs/superpowers/specs/2026-09-25-a5-durable-state-checkpoint-*.md``). This module closes that
gap by wrapping the existing in-memory CAS functions with a locked, atomic file backend — it never
re-implements plan/task reconciliation itself, only persists whatever that logic already produces.

**Why keyed by ``plan_id``, not ``run_id``.** A run can be resumed (``orchestrator.md``'s
``run_resumed`` event) across what is logically the same plan but a new run identity — the run log
is per-*run*, but plan progress must survive a run boundary, so the durable file this module owns is
keyed by the plan's own stable identity instead.

**Why this mirrors, rather than imports, ``run_log.py``'s directory/permission/lock conventions.**
``run_log.py``'s directory-resolution, private-directory, and lock-timeout helpers
(``resolve_log_dir``, ``_private_dir``, ``_locked``) are correct, already-hardened building blocks —
but they are underscore-prefixed internals of a heavily-reviewed module (11 rounds of prior review),
not a published API, and importing them here would couple two independently evolving stores through
a private surface neither owns. The architecture review's own Open Questions section explicitly
defers extracting a shared module to a future ticket, for the same reason: refactoring `run_log.py`
inside the same change that introduces new functionality risks regressing something already correct.
So this module duplicates the same shape in miniature — same ``<home>/.software-builder/...``
convention, same ``0700``/``0600`` permissions, same repository-exclusion check, same
``flock``-with-timeout pattern (``LOCK_TIMEOUT_SECONDS = 30.0``) — matching the precedent
``skills/pr-gatekeeper/scripts/idempotency_store.py`` already set for a simpler, timeout-less
version of the same "one JSON file + sibling lock file" shape.

**Why ``cas_advance`` is the only write entry point.** There is no separate bare "write" function, so
a caller can never bypass the generation-based compare-and-swap ``advance_plan_execution_state``
already enforces. Every failure path here fails closed: a lock the caller cannot acquire within
``timeout`` raises rather than blocking forever or silently proceeding unlocked
(:class:`PlanStateLockTimeoutError`); a stale ``expected_generation`` raises rather than silently
discarding the caller's write (:class:`PlanStateCasError`); a malformed or hand-edited existing state
file raises rather than being treated as "no state yet" (:class:`PlanStateStoreError`, the same
fail-closed doctrine ``scripts/sensitive_path_match.py``'s ``SensitivePathListError`` already
establishes for this repository); and a ``completed_evidence_refs`` merge that would exceed
``MAX_COMPLETED_EVIDENCE_REFS`` raises rather than silently truncating audit evidence or growing the
file unboundedly.

POSIX only (Linux, macOS): it needs ``flock``, matching ``run_log.py``'s own POSIX-only scope.

**Retention.** This module has no cleanup/expiry logic by design (Condition 3 of the architecture
review): an abandoned plan's state file is left in place indefinitely. The repository owner
periodically removes state files under ``~/.software-builder/plan-state/`` for plans with no
``COMPLETE``/``ESCALATED`` resolution and no activity in N days — a simple manual policy, consistent
with this repository's existing operability posture (no scheduled cleanup job exists for
``run_log.py``'s own directory either).
"""

from __future__ import annotations

import json
import os
import re
import stat
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

try:  # POSIX
    import fcntl
except ImportError:  # pragma: no cover - not POSIX
    fcntl = None  # type: ignore[assignment]

from scripts.atomic_write import atomic_write_text
from scripts.implementation_plan import (
    EXECUTION_STATE_FIELDS,
    advance_plan_execution_state,
    initial_plan_execution_state,
)

# Mirrors run_log.py's LOCK_TIMEOUT_SECONDS/_LOCK_POLL_SECONDS values exactly (Condition 1 of the
# architecture review) -- kept as an independent constant rather than imported, per this module's
# docstring on why the two stores duplicate this shape instead of sharing a private module.
LOCK_TIMEOUT_SECONDS = 30.0
_LOCK_POLL_SECONDS = 0.05

# A generous safety valve, not a realistic normal-use ceiling (design doc's Capacity section): this
# repository's own plans (e.g. F1's 9-task and 6-task plans) accumulate single-digit evidence-ref
# counts. Reaching this cap indicates something pathological (a runaway resume loop), not normal
# operation, and should escalate to a human rather than be silently absorbed.
MAX_COMPLETED_EVIDENCE_REFS = 1000

_PLAN_ID_RE = re.compile(r"[A-Za-z0-9._][A-Za-z0-9._-]{0,127}")


class PlanStateStoreError(ValueError):
    """Base error for this module: something about the durable store could not be trusted.

    Callers MUST treat this as "cannot determine the durable state", never as "there is no
    state yet" -- see this module's docstring on fail-closed error handling.
    """


class PlanStateLockTimeoutError(PlanStateStoreError):
    """Raised when the plan-state lock for one ``plan_id`` could not be acquired within ``timeout``
    seconds. A crashed holder must not be able to wedge every future caller against that plan
    forever; this is the bounded alternative to an unbounded ``flock()`` block."""


class PlanStateCasError(PlanStateStoreError):
    """Raised when ``cas_advance``'s generation-based compare-and-swap failed -- ``expected_generation``
    did not match the durable file's current ``state_generation``, meaning a concurrent writer already
    advanced it. The caller must re-read the current state (:func:`read_state`) and retry with the new
    generation; this mirrors the existing signal ``advance_plan_execution_state`` already returns via
    its ``errors`` list, surfaced here as an exception at the durable-store boundary."""


# --- directory/path resolution (mirrors run_log.py's own conventions; see module docstring) ---------


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
    """Refuse a directory that sits inside any git repository, whatever the current directory is
    (Condition 2 of the architecture review). A Builder edits its own working tree; if the plan-state
    directory sat inside a repo (or inside a Builder's worktree), Builder-authored content could
    tamper with Orchestrator state it must never touch -- the same reason ``run_log.py`` refuses this
    for the run log."""
    chain = [Path(os.path.realpath(directory))]
    chain.extend(chain[0].parents)
    for ancestor in chain:
        if _is_repo_root(ancestor):
            raise PlanStateStoreError(
                f"the plan-state directory must be outside any git repository (found one at {ancestor})"
            )
    known = [repo for repo in (_enclosing_repo(Path.cwd().resolve()),) if repo is not None]
    known += [Path(value) for value in (os.environ.get("GIT_DIR"), os.environ.get("GIT_WORK_TREE")) if value]
    if os.environ.get("GIT_DIR") and not os.environ.get("GIT_WORK_TREE"):
        known.append(Path.cwd())  # git treats the current directory as the work tree in that case
    for repo in known:
        for ancestor in chain:
            try:
                if ancestor.exists() and repo.exists() and os.path.samefile(ancestor, repo):
                    raise PlanStateStoreError(f"the plan-state directory must be outside the repository at {repo}")
            except OSError:
                continue


def resolve_state_dir(explicit: str | os.PathLike[str] | None) -> Path:
    """The directory the store may live in: absolute, no ``..``, and outside every git repository.

    Defaults to ``<home>/.software-builder/plan-state``, mirroring ``run_log.py``'s
    ``resolve_log_dir`` exactly (same ``~``/``~/...`` handling, same repository-exclusion check).
    """
    if explicit is not None and str(explicit) == "":
        raise PlanStateStoreError("state_dir must not be empty")
    raw = str(explicit) if explicit else ""
    if raw.startswith("~") and raw != "~" and not raw.startswith("~/"):
        raise PlanStateStoreError("only a plain '~' (this account's home) is supported in state_dir, not ~user")
    directory = (
        _home_dir() / raw[2:] if raw.startswith("~/") else _home_dir() if raw == "~"
        else Path(raw) if raw else _home_dir() / ".software-builder" / "plan-state"
    )
    if not directory.is_absolute():
        raise PlanStateStoreError(f"the plan-state directory must be an absolute path, got {str(directory)!r}")
    if ".." in directory.parts:
        raise PlanStateStoreError("the plan-state directory must not contain '..'")
    _refuse_repository(directory)
    return directory


def _validate_plan_id(plan_id: object) -> str:
    if not isinstance(plan_id, str) or not _PLAN_ID_RE.fullmatch(plan_id) or plan_id in {".", ".."}:
        raise PlanStateStoreError("plan_id must be 1-128 characters of [A-Za-z0-9._-], not starting with '-'")
    return plan_id


def state_path(state_dir: Path, plan_id: str) -> Path:
    """The JSON state file for ``plan_id`` inside ``state_dir``; validates ``plan_id`` is a safe
    identifier (mirrors ``run_log.py``'s ``validate_run_id``/``log_path`` escape check) so it can
    never be used to escape ``state_dir``."""
    plan_id = _validate_plan_id(plan_id)
    directory = Path(state_dir)
    path = directory / f"{plan_id}.json"
    if not _within(str(path), str(directory)) or os.path.realpath(path.parent) != os.path.realpath(directory):
        raise PlanStateStoreError("the plan-state path escapes its directory")
    return path


def _lock_path(state_dir: Path, plan_id: str) -> Path:
    plan_id = _validate_plan_id(plan_id)
    return Path(state_dir) / f"{plan_id}.lock"


def _private_dir(directory: Path) -> None:
    """Create ``directory`` (and the missing parents) private to this user; refuse one that already
    exists and is reachable by others, is not ours, or is the home directory (it is not ours to
    chmod) -- mirrors ``run_log.py``'s ``_private_dir`` exactly (Condition 2)."""
    if directory.is_symlink():
        raise PlanStateStoreError(f"refusing to use a symlinked plan-state directory: {directory}")
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
        raise PlanStateStoreError(f"not a directory: {directory}")
    info = os.lstat(directory)
    if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
        raise PlanStateStoreError(f"refusing to use a plan-state directory owned by another user: {directory}")
    if info.st_mode & 0o077:
        # Not ours to chmod: a directory that already exists may hold other things, and tightening
        # it would change who can reach them. Only directories this call created are 0700.
        raise PlanStateStoreError(
            f"the plan-state directory is accessible to others; do not change its permissions; "
            f"ask the caller for a private state_dir: {directory}"
        )
    try:
        is_home = os.path.samefile(directory, _home_dir())
    except OSError:  # an account whose home directory was never created cannot be the state directory
        is_home = False
    if is_home:
        raise PlanStateStoreError("refusing to use the home directory itself as the plan-state directory")


# --- locking (mirrors run_log.py's _locked, plus a cheap PID diagnostic like install_engine.py's) ----


def _open_lock(path: Path) -> int:
    fd = os.open(
        path,
        os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        0o600,
    )
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise PlanStateStoreError(f"the plan-state lock path is not a regular file: {path}")
        if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
            raise PlanStateStoreError(f"refusing to use a plan-state lock owned by another user: {path}")
        if info.st_mode & 0o077:
            os.fchmod(fd, 0o600)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _write_holder_pid(fd: int) -> None:
    """Diagnostics only: never read back to decide anything, only to name a holder in a
    ``PlanStateLockTimeoutError`` message (install_engine.py's ``_write_holder_pid`` precedent). A
    failure here must not fail the acquisition itself."""
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode("ascii"))
    except OSError:
        pass


def _read_holder_pid(path: Path) -> str:
    """Best-effort: reading a file's bytes needs no lock of our own (``flock`` only blocks other
    ``flock`` attempts, not plain reads), so this is safe to call while another process holds the
    lock exclusively."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return "unknown"
    try:
        data = os.pread(fd, 32, 0)
        return data.decode("ascii", errors="replace").strip() or "unknown"
    except OSError:
        return "unknown"
    finally:
        os.close(fd)


@contextmanager
def _locked(fd: int, lock_path: Path, *, exclusive: bool, timeout: float) -> Iterator[None]:
    if fcntl is None:  # pragma: no cover - not POSIX
        raise PlanStateStoreError("plan_state_store requires a POSIX platform (flock)")
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
            break
        except OSError:
            if time.monotonic() >= deadline:
                holder = _read_holder_pid(lock_path)
                raise PlanStateLockTimeoutError(
                    f"timed out after {timeout:.0f}s waiting for the plan-state lock at {lock_path} "
                    f"(held by pid {holder})"
                ) from None
            time.sleep(_LOCK_POLL_SECONDS)
    if exclusive:
        _write_holder_pid(fd)
    try:
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)


# --- state file parsing --------------------------------------------------------------------------


def _parse_state_file(raw: str, path: Path) -> dict[str, Any]:
    """Fail closed on anything that is not a well-formed ``plan_execution_state`` shape: a JSON parse
    failure, a non-object top level, an undeclared/missing field, or an invalid ``state_generation`` --
    never silently treated as "no state" (Failure strategy table in the design doc)."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PlanStateStoreError(f"the plan-state file at {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise PlanStateStoreError(f"the plan-state file at {path} must contain a JSON object")
    unknown = sorted(set(data) - EXECUTION_STATE_FIELDS)
    missing = sorted(EXECUTION_STATE_FIELDS - set(data))
    if unknown or missing:
        raise PlanStateStoreError(
            f"the plan-state file at {path} does not match the plan_execution_state schema "
            f"(unknown fields: {unknown}, missing fields: {missing})"
        )
    if type(data.get("state_generation")) is not int or data["state_generation"] < 0:
        raise PlanStateStoreError(f"the plan-state file at {path} has an invalid state_generation")
    if not isinstance(data.get("completed_evidence_refs"), list):
        raise PlanStateStoreError(f"the plan-state file at {path} has a non-list completed_evidence_refs")
    return data


# --- public API -----------------------------------------------------------------------------------


def read_state(state_dir: Path, plan_id: str) -> dict[str, Any] | None:
    """Return the current durable checkpoint for ``plan_id``, or ``None`` if none exists yet.

    Read-only, still lock-protected (shared lock) against a concurrent writer mid-write, so a reader
    never observes a torn write (structurally impossible anyway, since writes go through
    :func:`atomic_write_text`, but the shared lock also serializes against a writer's read-modify-write
    critical section). Raises :class:`PlanStateStoreError` on a malformed/corrupt existing file, and
    :class:`PlanStateLockTimeoutError` if the lock cannot be acquired within ``LOCK_TIMEOUT_SECONDS``.
    """
    plan_id = _validate_plan_id(plan_id)
    directory = Path(state_dir)
    _private_dir(directory)
    path = state_path(directory, plan_id)
    lock_path = _lock_path(directory, plan_id)
    lock_fd = _open_lock(lock_path)
    try:
        with _locked(lock_fd, lock_path, exclusive=False, timeout=LOCK_TIMEOUT_SECONDS):
            if not path.exists():
                return None
            raw = path.read_text(encoding="utf-8")
    finally:
        os.close(lock_fd)
    return _parse_state_file(raw, path)


def cas_advance(
    state_dir: Path,
    plan: Mapping[str, Any],
    *,
    expected_generation: int,
    authoritative_task_statuses: Mapping[str, str],
    current_head: str | None,
    updated_at: str,
    completed_evidence_refs: list[str] | None = None,
    blocked_reason: str | None = None,
    timeout: float = LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Advance one plan's durable checkpoint by exactly one generation, under a single exclusive-lock
    critical section: read the current file (or synthesize ``initial_plan_execution_state`` if
    absent), merge ``completed_evidence_refs`` with whatever is already durably stored (a union, never
    a replace -- see the design doc's Capacity section for why a caller's partial list must not drop
    evidence already recorded by an earlier resume cycle), call the existing, already-tested
    ``advance_plan_execution_state`` with the merged refs, write the result via
    :func:`atomic_write_text`, and return it.

    Raises :class:`PlanStateCasError` when ``advance_plan_execution_state`` reports a generation
    mismatch (a concurrent writer already advanced past ``expected_generation``); the caller must
    :func:`read_state` again and retry with the new generation. Raises
    :class:`PlanStateStoreError` if the merged ``completed_evidence_refs`` would exceed
    :data:`MAX_COMPLETED_EVIDENCE_REFS` -- never silently truncated. Raises
    :class:`PlanStateLockTimeoutError` if the lock cannot be acquired within ``timeout`` seconds.
    Nothing is written to disk unless every check above passes.
    """
    plan_id = _validate_plan_id(plan.get("plan_id"))
    directory = Path(state_dir)
    _private_dir(directory)
    path = state_path(directory, plan_id)
    lock_path = _lock_path(directory, plan_id)
    lock_fd = _open_lock(lock_path)
    try:
        with _locked(lock_fd, lock_path, exclusive=True, timeout=timeout):
            current: dict[str, Any] | None = None
            if path.exists():
                current = _parse_state_file(path.read_text(encoding="utf-8"), path)
            if current is None:
                current = initial_plan_execution_state(plan, current_head=current_head, updated_at=updated_at)

            durable_refs = current.get("completed_evidence_refs", [])
            merged_refs = sorted({*durable_refs, *(completed_evidence_refs or [])})
            if len(merged_refs) > MAX_COMPLETED_EVIDENCE_REFS:
                raise PlanStateStoreError(
                    f"plan {plan_id}: merging completed_evidence_refs would grow the durable list to "
                    f"{len(merged_refs)} entries, exceeding the {MAX_COMPLETED_EVIDENCE_REFS}-entry cap; "
                    "refusing to truncate audit evidence -- escalate instead of retrying silently"
                )

            normalized, errors = advance_plan_execution_state(
                current,
                plan,
                expected_generation=expected_generation,
                authoritative_task_statuses=authoritative_task_statuses,
                current_head=current_head,
                updated_at=updated_at,
                completed_evidence_refs=merged_refs,
                blocked_reason=blocked_reason,
            )
            if errors or normalized is None:
                raise PlanStateCasError(
                    f"plan {plan_id}: compare-and-swap from generation {expected_generation} failed: "
                    + "; ".join(errors or ["advance_plan_execution_state returned no state"])
                )
            atomic_write_text(path, json.dumps(normalized, indent=2, sort_keys=True) + "\n")
            return normalized
    finally:
        os.close(lock_fd)
