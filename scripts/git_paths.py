"""Small, byte-safe helpers for reading Git path lists."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable


def tracked_relative_paths(
    root: Path,
    paths: Iterable[str] | None = None,
) -> tuple[set[str], str | None]:
    """Return tracked paths relative to ``root``.

    ``git -C`` makes ``ls-files`` emit paths relative to the supplied working
    directory, which is important when ``root`` is a nested project inside a
    larger worktree. NUL delimiters preserve filenames containing whitespace
    or newlines.
    """

    command = ["git", "-C", str(root), "ls-files", "--cached", "-z", "--"]
    if paths is not None:
        command.extend(f":(literal){path}" for path in paths)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return set(), f"git ls-files failed: {exc}"
    if completed.returncode != 0:
        detail = os.fsdecode(completed.stderr or completed.stdout).strip()
        return set(), f"git ls-files failed: {detail or 'unknown error'}"
    return {
        os.fsdecode(path)
        for path in completed.stdout.split(b"\0")
        if path
    }, None
