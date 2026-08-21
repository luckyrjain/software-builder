"""Fail-closed pre-write guard shared by the five test-creator skills.

The skills are prompt-driven, so this module deliberately has no write API. It
only answers whether a caller may begin a planned write batch. Callers must run
it again before a later batch because repository state can change while a run
is in progress.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

_TRACKED_PATHS_IMPORT_ERROR: str | None = None
tracked_relative_paths = None
protected_index_relative_paths = None
try:
    helper_path = Path(__file__).resolve().with_name("git_paths.py")
    if not helper_path.is_file():
        raise FileNotFoundError(helper_path)
    spec = importlib.util.spec_from_file_location("_test_creator_git_paths", helper_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {helper_path}")
    helper_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper_module)
    tracked_relative_paths = helper_module.tracked_relative_paths
    protected_index_relative_paths = helper_module.protected_index_relative_paths
except Exception as exc:  # fail closed if the shipped helper cannot be loaded
    _TRACKED_PATHS_IMPORT_ERROR = f"shared Git path helper unavailable: {exc}"


_GIT_REPOSITORY_OVERRIDE_ENV = {
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_SYSTEM",
    "GIT_DIR",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM",
    "GIT_EXEC_PATH",
    "GIT_GRAFT_FILE",
    "GIT_INDEX_FILE",
    "GIT_INTERNAL_SUPER_PREFIX",
    "GIT_OBJECT_DIRECTORY",
    "GIT_OPTIONAL_LOCKS",
    "GIT_PREFIX",
    "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    "GIT_WORK_TREE",
}


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
    reason: str,
) -> WriteGuardResult:
    return WriteGuardResult(
        allowed=False,
        status="BLOCKED",
        planned_paths=tuple(sorted(set(planned_paths))),
        dirty_paths_before=tuple(sorted(set(dirty_paths_before))),
        status_snapshot=tuple(status_snapshot),
        conflicting_paths=tuple(sorted(set(conflicting_paths))),
        writes_started=False,
        reason=reason,
    )


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _filesystem_git_boundary(repo_root: Path) -> Path:
    """Best-effort enclosing worktree root without executing repository code."""

    for candidate in (repo_root, *repo_root.parents):
        marker = candidate / ".git"
        try:
            if marker.exists() or marker.is_symlink():
                return candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
    return repo_root


def _git_environment(execution_boundary: Path, filter_drivers: Iterable[str] = ()) -> dict[str, str]:
    """Return a read-only Git environment isolated from repo-controlled execution."""

    environment = dict(os.environ)
    for key in list(environment):
        if (
            key in _GIT_REPOSITORY_OVERRIDE_ENV
            or key.startswith("GIT_CONFIG_KEY_")
            or key.startswith("GIT_CONFIG_VALUE_")
            or key.startswith("GIT_TRACE")
        ):
            environment.pop(key, None)

    # Remove PATH entries that resolve inside the enclosing worktree. Git itself
    # is later pinned to an absolute executable found in the remaining search
    # path, and this sanitized PATH also protects against an accidental helper
    # subprocess resolving back into repository-controlled binaries.
    raw_path = environment.get("PATH", os.defpath)
    safe_path_entries: list[str] = []
    cwd = Path.cwd()
    for entry in raw_path.split(os.pathsep):
        candidate = Path(entry) if entry else cwd
        if not candidate.is_absolute():
            candidate = cwd / candidate
        try:
            resolved_entry = candidate.resolve(strict=False)
        except (OSError, RuntimeError):
            continue
        if _path_is_within(resolved_entry, execution_boundary):
            continue
        safe_path_entries.append(str(resolved_entry))
    if safe_path_entries:
        environment["PATH"] = os.pathsep.join(safe_path_entries)
    else:
        environment.pop("PATH", None)

    # Ignore ambient user/system Git configuration so HOME/XDG or explicit
    # config-file overrides cannot inject executable behavior into this safety
    # read. Keep repository-local config available for ordinary index/worktree
    # rules, but override the options that can launch helper processes. Optional
    # locks are disabled so status cannot refresh .git/index metadata.
    config_entries: list[tuple[str, str]] = [
        ("core.fsmonitor", "false"),
        ("core.attributesFile", os.devnull),
    ]
    for driver in sorted(set(filter_drivers)):
        config_entries.extend(
            [
                (f"filter.{driver}.clean", ""),
                (f"filter.{driver}.process", ""),
                (f"filter.{driver}.required", "false"),
            ],
        )

    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["GIT_CONFIG_COUNT"] = str(len(config_entries))
    for index, (key, value) in enumerate(config_entries):
        environment[f"GIT_CONFIG_KEY_{index}"] = key
        environment[f"GIT_CONFIG_VALUE_{index}"] = value
    return environment


def _resolve_git_executable(
    execution_boundary: Path,
    git_env: dict[str, str],
) -> tuple[str | None, str | None]:
    """Resolve an executable Git binary from search directories outside the worktree."""

    raw_path = git_env.get("PATH", os.defpath)
    cwd = Path.cwd()
    for entry in raw_path.split(os.pathsep):
        directory = Path(entry) if entry else cwd
        if not directory.is_absolute():
            directory = cwd / directory
        try:
            directory = directory.resolve(strict=False)
        except (OSError, RuntimeError):
            continue
        if _path_is_within(directory, execution_boundary):
            continue
        executable = shutil.which(str(directory / "git"))
        if executable is None:
            continue
        try:
            resolved = Path(executable).resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if _path_is_within(resolved, execution_boundary):
            continue
        return str(resolved), None
    return None, "trusted git executable not found outside enclosing worktree"


def _normalise_repo_root(repo_root: Path) -> tuple[Path | None, str | None]:
    try:
        resolved = Path(repo_root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        return None, f"repo_root cannot be resolved: {exc}"
    if not resolved.is_dir():
        return None, "repo_root is not a directory"
    return resolved, None


def _is_git_metadata_component(part: str) -> bool:
    normalised = part.rstrip(" .") if os.name == "nt" else part
    return normalised.casefold() == ".git"


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
            if any(_is_git_metadata_component(part) for part in lexical_relative.parts):
                return (), f"planned path {raw!r} targets Git metadata; refusing to write"
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
        if any(_is_git_metadata_component(part) for part in relative.parts):
            return (), f"planned path {raw!r} targets Git metadata; refusing to write"
        normalised.add(relative.as_posix())
    return tuple(sorted(normalised)), None


def _git_top_level(
    repo_root: Path,
    git_env: dict[str, str],
    git_executable: str,
) -> tuple[Path | None, str | None]:
    try:
        completed = subprocess.run(
            [git_executable, "-C", str(repo_root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            check=False,
            env=git_env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"git rev-parse failed: {exc}"
    if completed.returncode != 0:
        detail = os.fsdecode(completed.stderr or completed.stdout).strip()
        return None, f"git rev-parse failed: {detail or 'unknown error'}"
    try:
        top_level = Path(os.fsdecode(completed.stdout).strip()).resolve(strict=True)
        repo_root.relative_to(top_level)
    except (OSError, RuntimeError, ValueError) as exc:
        return None, f"git top-level cannot contain repo_root: {exc}"
    return top_level, None


def _repository_filter_drivers(
    root: Path,
    git_env: dict[str, str],
    git_executable: str,
) -> tuple[set[str], str | None]:
    """Resolve filter attributes without running the configured filter commands."""

    if tracked_relative_paths is None:
        return set(), _TRACKED_PATHS_IMPORT_ERROR or "shared Git path helper unavailable"
    tracked, tracked_error = tracked_relative_paths(
        root,
        env=git_env,
        git_executable=git_executable,
    )
    if tracked_error:
        return set(), tracked_error
    if not tracked:
        return set(), None

    path_input = b"".join(os.fsencode(path) + b"\0" for path in sorted(tracked))
    try:
        completed = subprocess.run(
            [git_executable, "-C", str(root), "check-attr", "-z", "--stdin", "filter"],
            input=path_input,
            capture_output=True,
            check=False,
            env=git_env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return set(), f"git check-attr failed: {exc}"
    if completed.returncode != 0:
        detail = os.fsdecode(completed.stderr or completed.stdout).strip()
        return set(), f"git check-attr failed: {detail or 'unknown error'}"

    records = completed.stdout.split(b"\0")
    if records and records[-1] == b"":
        records.pop()
    if len(records) % 3 != 0:
        return set(), "git check-attr returned an unparseable filter record"

    drivers: set[str] = set()
    for index in range(0, len(records), 3):
        _path, attribute, value = records[index : index + 3]
        if attribute != b"filter":
            return set(), "git check-attr returned an unexpected attribute record"
        if value not in {b"unspecified", b"unset"}:
            drivers.add(os.fsdecode(value))
    return drivers, None


def _status_path_relative_to_repo(
    repo_root: Path,
    git_top_level: Path,
    raw_path: bytes,
) -> str | None:
    try:
        absolute = git_top_level / os.fsdecode(raw_path)
        return absolute.relative_to(repo_root).as_posix()
    except (OSError, ValueError):
        return None


def _git_status(
    repo_root: Path,
    git_env: dict[str, str],
    git_executable: str,
) -> tuple[tuple[str, ...], tuple[str, ...], str | None]:
    git_top_level, top_level_error = _git_top_level(repo_root, git_env, git_executable)
    if top_level_error or git_top_level is None:
        return (), (), f"git status failed: {top_level_error or 'git top-level cannot be resolved'}"
    try:
        completed = subprocess.run(
            [
                git_executable,
                "-C",
                str(repo_root),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--ignore-submodules=all",
                "-z",
            ],
            capture_output=True,
            check=False,
            env=git_env,
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
        path = _status_path_relative_to_repo(repo_root, git_top_level, record[3:])
        if path is not None:
            paths.add(path)
        if b"R" in code or b"C" in code:
            index += 1
            if index >= len(records) or not records[index]:
                return (), snapshot, "git status returned an incomplete rename/copy record"
            renamed_path = _status_path_relative_to_repo(repo_root, git_top_level, records[index])
            if renamed_path is not None:
                paths.add(renamed_path)
        index += 1
    return tuple(sorted(paths)), snapshot, None


def _tracked_paths(
    repo_root: Path,
    planned_paths: Iterable[str],
    git_env: dict[str, str],
    git_executable: str,
) -> tuple[set[str], set[str], str | None]:
    if tracked_relative_paths is None or protected_index_relative_paths is None:
        return set(), set(), _TRACKED_PATHS_IMPORT_ERROR or "shared Git path helper unavailable"
    tracked, tracked_error = tracked_relative_paths(
        repo_root,
        planned_paths,
        env=git_env,
        git_executable=git_executable,
    )
    if tracked_error:
        return set(), set(), tracked_error
    protected, protected_error = protected_index_relative_paths(
        repo_root,
        planned_paths,
        env=git_env,
        git_executable=git_executable,
    )
    if protected_error:
        return set(), set(), protected_error
    return tracked, protected, None


def check_write_safety(repo_root: Path, planned_paths: Iterable[str | Path]) -> WriteGuardResult:
    """Capture current Git state and decide whether ``planned_paths`` are safe.

    A clean tracked target may be modified because it is part of the declared
    plan. Any dirty target, existing untracked target, Git index-protected
    target, or unsafe path blocks the whole batch. Dirty paths outside the plan
    are reported but allowed.
    """

    resolved_root, root_error = _normalise_repo_root(repo_root)
    if root_error or resolved_root is None:
        return _blocked(reason=root_error or "repo_root is invalid")

    normalised, path_error = _normalise_planned_paths(resolved_root, planned_paths)
    if path_error:
        return _blocked(reason=path_error)

    execution_boundary = _filesystem_git_boundary(resolved_root)
    base_git_env = _git_environment(execution_boundary)
    git_executable, git_executable_error = _resolve_git_executable(execution_boundary, base_git_env)
    if git_executable_error or git_executable is None:
        return _blocked(planned_paths=normalised, reason=git_executable_error or "trusted git unavailable")

    git_top_level, top_level_error = _git_top_level(resolved_root, base_git_env, git_executable)
    if top_level_error or git_top_level is None:
        return _blocked(
            planned_paths=normalised,
            reason=f"git status failed: {top_level_error or 'git top-level cannot be resolved'}",
        )

    # Status intentionally captures the full enclosing worktree snapshot even
    # when repo_root is nested, while conflicts are normalized back to
    # repo_root. Neutralize filters for every tracked path status may inspect so
    # an out-of-scope sibling cannot gain execution merely by being included in
    # that evidence snapshot.
    filter_drivers, filter_error = _repository_filter_drivers(
        git_top_level,
        base_git_env,
        git_executable,
    )
    if filter_error:
        return _blocked(
            planned_paths=normalised,
            reason=f"git status preparation failed: {filter_error}",
        )
    git_env = _git_environment(execution_boundary, filter_drivers)

    dirty_paths, status_snapshot, status_error = _git_status(resolved_root, git_env, git_executable)
    if status_error:
        return _blocked(planned_paths=normalised, status_snapshot=status_snapshot, reason=status_error)

    tracked_paths, protected_paths, tracked_error = _tracked_paths(
        resolved_root,
        normalised,
        git_env,
        git_executable,
    )
    if tracked_error:
        return _blocked(
            planned_paths=normalised,
            dirty_paths_before=dirty_paths,
            status_snapshot=status_snapshot,
            reason=tracked_error,
        )

    protected_conflicts = set(normalised) & protected_paths
    if protected_conflicts:
        return _blocked(
            planned_paths=normalised,
            dirty_paths_before=dirty_paths,
            status_snapshot=status_snapshot,
            conflicting_paths=protected_conflicts,
            reason=(
                "planned write includes Git index-protected path(s) whose worktree drift may be hidden "
                "from status: " + ", ".join(sorted(protected_conflicts))
            ),
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
                "planned write overlaps existing dirty, untracked, directory, or hard link paths: "
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
