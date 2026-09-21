"""Shared fixtures for scripts/tests/.

Most of this suite's tests read the real repository's live registry/manifest state directly
from ROOT (``parse_registry(ROOT / "skills.yaml")``, ``load_canonical_manifest(ROOT)``, and
friends) by design -- an isolated tmp_path fixture would need to mirror the entire skill tree
(every registered skill's SKILL.md/reference files, every declared host) for checks like
``validate_canonical_manifest`` to mean anything, which is far more than most of these tests
need. One test (test_platform_manifest.py's
``test_validate_manifest_reports_new_fragment_missing_from_composition_contracts_cleanly``)
exploits that same real-tree requirement in the other direction: it briefly writes a throwaway
skill fragment onto the *real* repository root to exercise a real-tree code path, and removes it
in a ``finally``. Under pytest-xdist's parallel workers, a reader on another worker can observe
that fragment mid-window -- seen in CI as a stray ``orphan-test-skill`` entry leaking into a
sibling test's expected skill list.

Rather than harden every one of those ~40 call sites against a transient extra registry entry,
route every test through one shared/exclusive file lock: a test marked
``@pytest.mark.mutates_repository_root`` holds it exclusively for its whole run (so nothing else
in the suite can be mid-test while the real tree is mutated); every other test holds it
non-exclusively (readers never block each other, only the one mutator). The lock file lives
outside the repository so it never needs a .gitignore entry or shows up in `git status`.
"""

from __future__ import annotations

import os
import signal
import sys

import pytest

from scripts.tests.registry_root_lock import LOCK_PATH

if sys.platform != "win32":
    import fcntl

_LOCK_PATH = LOCK_PATH


def _open_lock_fd() -> int:
    """Open (creating if needed) the lock file, refusing to follow a symlink at that path.

    The lock path is predictable (a fixed name under the shared system temp directory), so
    another local account could pre-create it as a symlink before this suite runs; a plain
    `open()` would then transparently lock whatever it points at instead. `O_NOFOLLOW` makes
    the `open` syscall itself fail closed on that final path component -- race-free, unlike a
    separate `Path.is_symlink()` check-then-open (see package_skill.py's dest-symlink guard for
    the same distinction: a static pre-check on this kind of path is known to be racy).
    """
    return os.open(_LOCK_PATH, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)  # POSIX-only flag


@pytest.fixture(autouse=True)
def _serialize_against_repository_root_mutation(request: pytest.FixtureRequest):
    if sys.platform == "win32":
        # No flock (or O_NOFOLLOW) on Windows. The Windows CI job runs its pytest steps one after
        # another (no xdist, no `make -j`), so there is nothing concurrent to serialize against.
        yield
        return
    exclusive = request.node.get_closest_marker("mutates_repository_root") is not None
    fd = _open_lock_fd()
    try:
        fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


@pytest.fixture
def signal_sentinels():
    """Replace SIGINT/SIGTERM's disposition with handlers that fail the test.

    The interrupt-protection tests deliver a real signal with `os.kill(os.getpid(), ...)`. If
    the protection under test is missing or broken, the signal reaches whatever handler was
    installed before -- normally the default, which for SIGTERM kills the whole pytest process
    (no report, a crashed worker under xdist) rather than failing one test. With these
    installed, the code under test saves and restores them like any previous handler, and a
    regression surfaces as an ordinary assertion failure. Yields the sentinels' `(sigint,
    sigterm)` handlers so a test can assert they were restored.
    """

    def _sigterm_reached_default(signum, frame):
        raise AssertionError("SIGTERM reached the default disposition -- protection missing")

    def _sigint_reached_default(signum, frame):
        raise AssertionError("SIGINT reached the default disposition -- protection missing")

    def _sighup_reached_default(signum, frame):
        raise AssertionError("SIGHUP reached the default disposition -- protection missing")

    previous_int = signal.signal(signal.SIGINT, _sigint_reached_default)
    previous_term = signal.signal(signal.SIGTERM, _sigterm_reached_default)
    hangup = getattr(signal, "SIGHUP", None)
    previous_hup = signal.signal(hangup, _sighup_reached_default) if hangup is not None else None
    try:
        yield _sigint_reached_default, _sigterm_reached_default
    finally:
        signal.signal(signal.SIGINT, previous_int)
        signal.signal(signal.SIGTERM, previous_term)
        if hangup is not None:
            signal.signal(hangup, previous_hup)
