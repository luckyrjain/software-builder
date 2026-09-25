"""Tests for scripts/task_lease.py: non-blocking, flock-based mutual exclusion over a deterministic
``(repo, base_branch, task_id)`` lease identity (gap-backlog A6).

The cross-process test mirrors scripts/tests/install_lock_test_helpers.py's ``spawn_lock_holder``
pattern: ``flock`` is scoped to the open-file-description, so there is no lock-file *content* a test
can fake to simulate "held" -- the only way to make a second, real ``try_acquire`` genuinely contend
is to have another process actually hold the OS lock. This is the design's own Rollout Phase 0
acceptance criterion (a genuine cross-process test, not a same-process simulation).
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

import scripts.task_lease as task_lease
from scripts.task_lease import LeaseHandle, TaskLeaseError, derive_lease_id, resolve_lease_dir, try_acquire

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX flock semantics")

ROOT = Path(__file__).resolve().parents[2]

REPO = "acme/checkout"
BASE_BRANCH = "main"
TASK_ID = "TASK-001"


def _lease_id() -> str:
    return derive_lease_id(REPO, BASE_BRANCH, TASK_ID)


# --- derive_lease_id: deterministic, no timestamp -----------------------------------------------


def test_derive_lease_id_is_deterministic_and_shaped_like_the_design_says() -> None:
    first = derive_lease_id(REPO, BASE_BRANCH, TASK_ID)
    second = derive_lease_id(REPO, BASE_BRANCH, TASK_ID)
    assert first == second
    assert first.startswith("lease-")
    assert len(first) == len("lease-") + 16
    assert all(ch in "0123456789abcdef" for ch in first[len("lease-") :])


def test_derive_lease_id_differs_when_any_single_input_differs() -> None:
    base = derive_lease_id(REPO, BASE_BRANCH, TASK_ID)
    assert derive_lease_id("acme/other-repo", BASE_BRANCH, TASK_ID) != base
    assert derive_lease_id(REPO, "develop", TASK_ID) != base
    assert derive_lease_id(REPO, BASE_BRANCH, "TASK-002") != base


# --- single-process acquire/release --------------------------------------------------------------


@posix_only
def test_try_acquire_succeeds_and_release_frees_it_for_a_later_attempt(tmp_path: Path) -> None:
    lease_dir = tmp_path / "leases"
    lease_id = _lease_id()

    handle = try_acquire(lease_dir, lease_id)
    assert handle is not None
    assert isinstance(handle, LeaseHandle)
    handle.release()

    again = try_acquire(lease_dir, lease_id)
    assert again is not None
    again.release()


@posix_only
def test_try_acquire_is_usable_as_a_context_manager(tmp_path: Path) -> None:
    lease_dir = tmp_path / "leases"
    lease_id = _lease_id()

    with try_acquire(lease_dir, lease_id) as handle:
        assert isinstance(handle, LeaseHandle)
        # Held for the duration of the block: a fresh attempt from this same process contends.
        assert try_acquire(lease_dir, lease_id) is None

    # The `with` block released it on exit.
    after = try_acquire(lease_dir, lease_id)
    assert after is not None
    after.release()


@posix_only
def test_release_is_idempotent(tmp_path: Path) -> None:
    lease_dir = tmp_path / "leases"
    lease_id = _lease_id()

    handle = try_acquire(lease_dir, lease_id)
    assert handle is not None
    handle.release()
    handle.release()  # closing an already-closed fd is a no-op, not an error

    # Not stuck "held" by the double release: a fresh attempt still succeeds.
    again = try_acquire(lease_dir, lease_id)
    assert again is not None
    again.release()


# --- same-process double try_acquire fails immediately (no self-deadlock, no false success) ------


@posix_only
def test_same_process_double_try_acquire_fails_immediately_not_after_a_wait(tmp_path: Path) -> None:
    """flock binds to the open-file-description, not the process: a fresh fd from a second
    try_acquire call contends with this same process's own already-held lock. Must return None at
    once, never block waiting for itself to let go."""
    lease_dir = tmp_path / "leases"
    lease_id = _lease_id()

    first = try_acquire(lease_dir, lease_id)
    assert first is not None
    try:
        started = time.monotonic()
        second = try_acquire(lease_dir, lease_id)
        elapsed = time.monotonic() - started
        assert second is None
        assert elapsed < 1.0
    finally:
        first.release()

    third = try_acquire(lease_dir, lease_id)
    assert third is not None
    third.release()


# --- infrastructure failure is a distinct, structural code path from a denied lease --------------


def test_try_acquire_raises_task_lease_error_not_none_when_the_directory_cannot_be_created(
    tmp_path: Path,
) -> None:
    """Point lease_dir at a path that can never be created: a regular file sits where a directory
    component would need to go, so os.mkdir fails with a real filesystem error (not a permission
    quirk that root could bypass) -- this must surface as TaskLeaseError, never as a plain None a
    caller could mistake for ordinary contention."""
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x", encoding="utf-8")
    lease_dir = blocker / "leases"

    with pytest.raises(TaskLeaseError):
        try_acquire(lease_dir, _lease_id())


@pytest.mark.parametrize("bad", ["../escape", "", "a/b", ".", ".."])
def test_try_acquire_rejects_an_unsafe_lease_id(tmp_path: Path, bad: str) -> None:
    with pytest.raises(TaskLeaseError):
        try_acquire(tmp_path / "leases", bad)


# --- directory resolution mirrors plan_state_store.py's own conventions --------------------------


def test_resolve_lease_dir_refuses_a_path_inside_a_git_repository() -> None:
    assert (ROOT / ".git").exists(), "this test assumes it runs inside a git checkout"
    with pytest.raises(TaskLeaseError):
        resolve_lease_dir(str(ROOT / "scratch-task-lease-dir"))


def test_resolve_lease_dir_defaults_under_the_home_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(task_lease, "_home_dir", lambda: tmp_path)
    assert resolve_lease_dir(None) == tmp_path / ".software-builder" / "task-leases"


# --- genuine cross-process contest: the actual "no double execution" acceptance criterion --------

_HOLD_LEASE_CODE = """
import sys, time
from pathlib import Path
sys.path.insert(0, {root!r})
from scripts.task_lease import try_acquire

handle = try_acquire(Path({lease_dir!r}), {lease_id!r})
assert handle is not None, "lease holder failed to acquire the lease"
print("locked", flush=True)
time.sleep({duration})
"""


def _spawn_lease_holder(lease_dir: Path, lease_id: str, duration: float = 60.0) -> "subprocess.Popen[str]":
    """Start a real subprocess that acquires the real OS lock for ``lease_id`` and holds it for
    ``duration`` seconds (or until killed) -- mirrors
    scripts/tests/install_lock_test_helpers.py's ``spawn_lock_holder``. Blocks until the subprocess
    reports it has actually acquired the lease, so the caller's own attempt never races this one
    still starting up."""
    code = _HOLD_LEASE_CODE.format(root=str(ROOT), lease_dir=str(lease_dir), lease_id=lease_id, duration=duration)
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    assert proc.stdout is not None
    line = proc.stdout.readline()
    assert line.strip() == "locked", f"lease holder failed to start: {line!r}"
    return proc


@posix_only
def test_a_real_second_process_holding_the_lease_makes_try_acquire_return_none_immediately(
    tmp_path: Path,
) -> None:
    lease_dir = tmp_path / "leases"
    lease_id = _lease_id()

    holder = _spawn_lease_holder(lease_dir, lease_id)
    try:
        started = time.monotonic()
        result = try_acquire(lease_dir, lease_id)
        elapsed = time.monotonic() - started
        assert result is None
        assert elapsed < 1.0  # non-blocking: must not wait for the holder to finish
    finally:
        holder.kill()
        holder.wait()

    # The OS releases the holder's flock the instant its process (and fd) is gone: a fresh attempt
    # from this process now succeeds, with no stale-lease reclaim logic involved.
    after = try_acquire(lease_dir, lease_id)
    assert after is not None
    after.release()
