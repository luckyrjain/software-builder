"""Fail-closed pre-write guard shared by the five test-creator skills.

The skills are prompt-driven, so this module deliberately has no write API.  It
only answers whether a caller may begin a planned write batch.  Callers must
run it again before a later batch because repository state can change while a
run is in progress.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class WriteGuardResult:
    """Machine-readable decision for one pre-write check."""

    allowed: bool
    status: str
    planned_paths: tuple[str, ...]
    dirty_paths_before: tuple[str, ...]
    status_snapshot: tuple[str, ...]
    conflicting_paths: tuple[str, ...]
    writes_started: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for field in ("planned_paths", "dirty_paths_before", "status_snapshot", "conflicting_paths"):
            payload[field] = list(payload[field])
        return payload


def _blocked(
    *,
    planned_paths: Iterable[str] = (),
    dirty_paths_before: Iterable[str] = (),
    status_snapshot: Iterable[str] = (),
    conflicting_paths: Iterable[str] = (),
    writes_started: bool = False,
    reason: str,
) -> WriteGuardResult:
    return WriteGuardResult(
        allowed=False,
        status="BLOCKED",
        planned_paths=tuple(sorted(set(planned_paths))),
        dirty_paths_before=tuple(sorted(set(dirty_paths_before))),
        status_snapshot=tuple(status_snapshot),
        conflicting_paths=tuple(sorted(set(conflicting_paths))),
        writes_started=writes_started,
        reason=reason,
    )


def _normalise_repo_root(repo_root: Path) -> tuple[Path | None, str | None]:
    try:
        resolved = Path(repo_root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        return None, f"repo_root cannot be resolved: {exc}"
    if not resolved.is_dir():
        return None, "repo_root is not a directory"
    return resolved, None


def _normalise_planned_paths(
    repo_root: Path,
    planned_paths: Iterable[str | Path],
) -> tuple[tuple[str, ...], str | None]:
    raw_paths = list(planned_paths)
    if not raw_paths:
        return (), "planned write set is empty"

    normalised: set[str] = set()
    for raw in raw_paths:
        if not isinstance(raw, (str, Path)) or not str(raw).strip():
            return (), "planned write set contains an empty or non-path value"
        candidate = Path(raw)
        try:
            lexical = Path(os.path.abspath(str(candidate if candidate.is_absolute() else repo_root / candidate)))
            lexical_relative = lexical.relative_to(repo_root)
            current = repo_root
            for part in lexical_relative.parts:
                current /= part
                if current.is_symlink():
                    return (), f"planned path {raw!r} traverses a symlink; refusing to write"
            resolved = lexical.resolve(strict=False)
            relative = resolved.relative_to(repo_root)
        except (OSError, RuntimeError, ValueError) as exc:
            return (), f"planned path {raw!r} is outside repository or cannot be resolved: {exc}"
        if not relative.parts:
            return (), "planned write set cannot contain the repository root"
        normalised.add(relative.as_posix())
    return tuple(sorted(normalised)), None


def _git_status(repo_root: Path) -> tuple[tuple[str, ...], tuple[str, ...], str | None]:
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "-z",
            ],
            capture_output=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return (), (), f"git status failed: {exc}"
    if completed.returncode != 0:
        detail = os.fsdecode(completed.stderr or completed.stdout).strip()
        return (), (), f"git status failed: {detail or 'unknown error'}"

    paths: set[str] = set()
    records = completed.stdout.split(b"\0")
    snapshot = tuple(os.fsdecode(record) for record in records if record)
    index = 0
    while index < len(records):
        record = records[index]
        if not record:
            index += 1
            continue
        if len(record) < 4 or record[2:3] != b" ":
            return (), snapshot, "git status returned an unparseable porcelain record"
        code = record[:2]
        paths.add(os.fsdecode(record[3:]))
        if b"R" in code or b"C" in code:
            index += 1
            if index >= len(records) or not records[index]:
                return (), snapshot, "git status returned an incomplete rename/copy record"
            paths.add(os.fsdecode(records[index]))
        index += 1
    return tuple(sorted(paths)), snapshot, None


def _tracked_paths(repo_root: Path) -> tuple[set[str], str | None]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "--cached", "-z", "--", "."],
            capture_output=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return set(), f"git ls-files failed: {exc}"
    if completed.returncode != 0:
        detail = os.fsdecode(completed.stderr or completed.stdout).strip()
        return set(), f"git ls-files failed: {detail or 'unknown error'}"
    return {os.fsdecode(path) for path in completed.stdout.split(b"\0") if path}, None


def check_write_safety(repo_root: Path, planned_paths: Iterable[str | Path]) -> WriteGuardResult:
    """Capture current Git state and decide whether ``planned_paths`` are safe.

    A clean tracked target may be modified because it is part of the declared
    plan.  Any dirty target, existing untracked target, or unsafe path blocks
    the whole batch.  Dirty paths outside the plan are reported but allowed.
    """

    resolved_root, root_error = _normalise_repo_root(repo_root)
    if root_error or resolved_root is None:
        return _blocked(reason=root_error or "repo_root is invalid")

    normalised, path_error = _normalise_planned_paths(resolved_root, planned_paths)
    if path_error:
        return _blocked(reason=path_error)

    dirty_paths, status_snapshot, status_error = _git_status(resolved_root)
    if status_error:
        return _blocked(planned_paths=normalised, status_snapshot=status_snapshot, reason=status_error)

    tracked_paths, tracked_error = _tracked_paths(resolved_root)
    if tracked_error:
        return _blocked(
            planned_paths=normalised,
            dirty_paths_before=dirty_paths,
            status_snapshot=status_snapshot,
            reason=tracked_error,
        )

    conflicts = {
        planned
        for planned in normalised
        for dirty in dirty_paths
        if planned == dirty or planned.startswith(f"{dirty}/") or dirty.startswith(f"{planned}/")
    }
    for planned in normalised:
        candidate = resolved_root / planned
        if candidate.exists() and planned not in tracked_paths:
            conflicts.add(planned)
        if candidate.is_dir():
            conflicts.add(planned)
        if candidate.exists() and candidate.is_file() and candidate.stat().st_nlink > 1:
            conflicts.add(planned)

    if conflicts:
        return _blocked(
            planned_paths=normalised,
            dirty_paths_before=dirty_paths,
            status_snapshot=status_snapshot,
            conflicting_paths=conflicts,
            reason=(
                "planned write overlaps existing dirty, untracked, or hard link paths: "
                + ", ".join(sorted(conflicts))
            ),
        )

    return WriteGuardResult(
        allowed=True,
        status="ALLOWED",
        planned_paths=normalised,
        dirty_paths_before=dirty_paths,
        status_snapshot=status_snapshot,
        conflicting_paths=(),
        writes_started=False,
        reason="pre-write repository state is safe",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--planned-file", action="append", dest="planned_paths", default=[])
    args = parser.parse_args(argv)
    result = check_write_safety(args.repo_root, args.planned_paths)
    print(json.dumps(result.to_dict(), sort_keys=True))
    return 0 if result.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
