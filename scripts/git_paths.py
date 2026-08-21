"""Small, byte-safe helpers for reading Git path lists."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Iterable


def _pathspec_chunks(command_prefix: list[str], paths: Iterable[str] | None) -> list[list[str] | None]:
    path_list = list(paths) if paths is not None else None
    if path_list == []:
        return []
    if path_list is None:
        return [None]

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
    return chunks


def _ls_files_records(
    root: Path,
    *,
    options: list[str],
    paths: Iterable[str] | None = None,
    env: Mapping[str, str] | None = None,
    git_executable: str = "git",
) -> tuple[list[bytes], str | None]:
    command_prefix = [git_executable, "-C", str(root), "ls-files", *options, "-z"]
    chunks = _pathspec_chunks(command_prefix, paths)
    if chunks == []:
        return [], None

    records: list[bytes] = []
    for pathspecs in chunks:
        command = [*command_prefix, "--"]
        if pathspecs is not None:
            command.extend(pathspecs)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                env=dict(env) if env is not None else None,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return [], f"git ls-files failed: {exc}"
        if completed.returncode != 0:
            detail = os.fsdecode(completed.stderr or completed.stdout).strip()
            return [], f"git ls-files failed: {detail or 'unknown error'}"
        records.extend(record for record in completed.stdout.split(b"\0") if record)
    return records, None


def tracked_relative_paths(
    root: Path,
    paths: Iterable[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    git_executable: str = "git",
) -> tuple[set[str], str | None]:
    """Return tracked paths relative to ``root``.

    ``git -C`` makes ``ls-files`` emit paths relative to the supplied working
    directory, which is important when ``root`` is a nested project inside a
    larger worktree. NUL delimiters preserve filenames containing whitespace
    or newlines. ``git_executable`` lets security-sensitive callers pin an
    already-resolved Git binary while ordinary callers keep the historical
    PATH-based default.
    """

    records, error = _ls_files_records(
        root,
        options=["--cached"],
        paths=paths,
        env=env,
        git_executable=git_executable,
    )
    if error:
        return set(), error
    return {os.fsdecode(record) for record in records}, None


def protected_index_relative_paths(
    root: Path,
    paths: Iterable[str],
    *,
    env: Mapping[str, str] | None = None,
    git_executable: str = "git",
) -> tuple[set[str], str | None]:
    """Return planned paths whose index flags can hide worktree drift.

    ``git status`` deliberately trusts assume-unchanged / skip-worktree hints,
    so local modifications on those paths may be invisible to the ordinary
    porcelain snapshot. ``git ls-files -v`` exposes the flags: a lowercase
    status letter means assume-unchanged and ``S`` means skip-worktree.
    """

    records, error = _ls_files_records(
        root,
        options=["--cached", "-v"],
        paths=paths,
        env=env,
        git_executable=git_executable,
    )
    if error:
        return set(), error

    protected: set[str] = set()
    for record in records:
        if len(record) < 3 or record[1:2] != b" ":
            return set(), "git ls-files returned an unparseable index-flag record"
        tag = record[:1]
        if tag == b"S" or tag.islower():
            protected.add(os.fsdecode(record[2:]))
    return protected, None
