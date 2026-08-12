"""Shared subprocess-env builder for tests that spawn install.sh."""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

_python3_bin_dir: str | None = None


def _python3_shim_dir() -> str:
    """A directory containing a `python3` name that resolves to sys.executable.

    A directory holding sys.executable is NOT guaranteed to contain a binary
    or symlink literally named `python3` -- CPython only guarantees
    `pythonX.Y` next to itself; a bare `python3` alias is a packaging
    convention (present on Homebrew/venv layouts, not guaranteed on every
    pyenv/container layout). install.sh hardcodes the literal command
    `python3` (scripts/install.sh:7), so a directory without that exact name
    would silently fall through to the next PATH entry -- reintroducing the
    same class of bug this helper exists to fix, just for a narrower set of
    interpreter layouts. Symlinking guarantees it regardless of layout.
    """
    global _python3_bin_dir
    if _python3_bin_dir is None:
        shim_dir = tempfile.mkdtemp(prefix="install-test-python3-")
        atexit.register(shutil.rmtree, shim_dir, ignore_errors=True)
        os.symlink(sys.executable, os.path.join(shim_dir, "python3"))
        _python3_bin_dir = shim_dir
    return _python3_bin_dir


def install_subprocess_env(home: Path, *, repo: Path | None = None) -> dict[str, str]:
    """Environment for spawning install.sh under test.

    install.sh shells out to plain `python3` (scripts/install.sh:7), resolved
    via PATH. A from-scratch env with no PATH at all falls back to the OS
    default search path, which can land on a system python3 that lacks this
    repo's dependencies (PyYAML) -- install.sh then fails with
    ModuleNotFoundError before ever reaching the behavior under test.

    Deliberately not the full host PATH: os.environ.get("PATH", "") degrades
    to an empty string (worse than omitting the key -- an empty PATH makes
    `bash` itself unresolvable) when PATH is genuinely unset, and even a
    present host PATH doesn't guarantee `python3` on it is the same
    interpreter pytest is running under. Prepending a directory with a
    `python3` symlinked to sys.executable guarantees install.sh's `python3`
    resolves to that exact interpreter (and its installed dependencies); the
    rest is a fixed, minimal set of standard system dirs for bash/coreutils --
    not whatever happens to be on the host's real PATH.

    `repo`, when given, sets PYTHONPATH to it. Only load-bearing for a test
    that invokes a script directly (e.g. via `python3 -m scripts...`);
    install.sh's own `run_python` (scripts/install.sh:6-8) always overrides
    PYTHONPATH itself from a REPO_ROOT it computes from $0, so for tests that
    spawn `bash install.sh` this is redundant with what install.sh would set
    on its own -- harmless to pass, just not the thing actually fixing
    anything on that path.
    """
    python_bin_dir = _python3_shim_dir()
    minimal_path = os.pathsep.join([python_bin_dir, "/usr/bin", "/bin", "/usr/sbin", "/sbin"])
    env = {
        "HOME": str(home),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PATH": minimal_path,
    }
    if repo is not None:
        env["PYTHONPATH"] = str(repo)
    return env
