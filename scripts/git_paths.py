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

    path_list = list(paths) if paths is not None else None
    if path_list == []:
        return set(), None
    command_prefix = ["git", "-C", str(root), "ls-files", "--cached", "-z"]
    if path_list is None:
        pathspec_chunks = [None]
    else:
        # Older Git versions do not support --pathspec-from-file for ls-files.
        # Bound argv size instead of passing one unbounded batch to Git.
        try:
            arg_max = int(os.sysconf("SC_ARG_MAX"))
        except (AttributeError, OSError, ValueError):
            arg_max = 131072
        budget = max(16384, arg_max // 2)
        chunks: list[list[str]] = []
        current: list[str] = []
        current_size = sum(len(os.fsencode(part)) + 1 for part in command_prefix)
        for path in path_list:
            pathspec = f":(literal){path}"
            path_size = len(os.fsencode(pathspec)) + 1
            if current and current_size + path_size > budget:
                chunks.append(current)
                current = []
                current_size = sum(len(os.fsencode(part)) + 1 for part in command_prefix)
            current.append(pathspec)
            current_size += path_size
        if current:
            chunks.append(current)
        pathspec_chunks = chunks

    tracked: set[str] = set()
    for pathspecs in pathspec_chunks:
        command = [*command_prefix, "--"]
        if pathspecs is not None:
            command.extend(pathspecs)
        try:
            completed = subprocess.run(command, capture_output=True, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            return set(), f"git ls-files failed: {exc}"
        if completed.returncode != 0:
            detail = os.fsdecode(completed.stderr or completed.stdout).strip()
            return set(), f"git ls-files failed: {detail or 'unknown error'}"
        tracked.update(
            os.fsdecode(path)
            for path in completed.stdout.split(b"\0")
            if path
        )
    return tracked, None
