"""Shared fixtures for cli/tests/.

Every test here shells out to `python -m sb ...`, which needs cli/sb/_vendored/ and
cli/sb/_registry_snapshot/ to already exist on disk (see scripts/build_sb_snapshot.py). Build
them once per session before any test runs, so this suite passes from a fresh clone instead of
depending on scripts/tests/test_build_sb_snapshot.py having already populated them earlier.
"""

from __future__ import annotations

import fcntl
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_sb_snapshot import build_snapshot  # noqa: E402

# scripts/tests/ also rebuilds and reads cli/sb/_vendored/ and cli/sb/_registry_snapshot/
# (test_build_sb_snapshot.py, test_sb_wheel_smoke.py), serialized against each other there
# via a flock in scripts/tests/conftest.py. This suite runs `cd cli && pytest tests/` as a
# *separate process* under CI's `make -j lint-suites`, so it never observes that lock unless
# it takes it too. Reuse the exact same fixed lock-file path (there's no import link between
# the two conftest.py files, only this shared path) and hold it exclusively for the whole
# session, so no scripts/tests/ test can run while this suite's snapshot exists mid-rebuild or
# mid-read, and vice versa.
_LOCK_PATH = Path(tempfile.gettempdir()) / "software-builder-pytest-registry-root.lock"


def _open_lock_fd() -> int:
    """Open (creating if needed) the lock file, refusing to follow a symlink at that path.

    The lock path is predictable (a fixed name under the shared system temp directory), so
    another local account could pre-create it as a symlink before this suite runs; a plain
    `open()` would then transparently lock whatever it points at instead. `O_NOFOLLOW` makes
    the `open` syscall itself fail closed on that final path component -- race-free, unlike a
    separate `Path.is_symlink()` check-then-open (see package_skill.py's dest-symlink guard for
    the same distinction: a static pre-check on this kind of path is known to be racy).
    """
    return os.open(_LOCK_PATH, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)


@pytest.fixture(scope="session", autouse=True)
def _build_snapshot() -> None:
    fd = _open_lock_fd()
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            build_snapshot(ROOT)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
