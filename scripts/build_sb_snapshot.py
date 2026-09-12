#!/usr/bin/env python3
"""Populate cli/sb/_vendored/ (code) and cli/sb/_registry_snapshot/ (data) from this checkout's
git-tracked files, so the `sb` package can run doctor/list/explain/compatibility logic unforked
against an installed skill with no software-builder checkout present.

Git-tracked only (same reasoning as scripts/package_release.py: untracked local cruft -- caches,
build output, local secrets -- can never leak into what ships), and pathspec-driven rather than a
hand-maintained file list, so a new scripts/*.py module, a new registry YAML, or a new skill is
picked up automatically. Does NOT reuse scripts/package_release.py's private _tracked_files --
that function returns tar-specific metadata (mode, blob hash) for a different artifact (the
checksummed skill-distribution tarball, which deliberately EXCLUDES scripts/ dev tooling); this
script's bundle has the opposite inclusion (scripts/ IS what this bundle ships), so it uses its
own minimal `git ls-files` invocation instead.

The exact file set here was verified empirically during planning, not assumed: cmd_list,
cmd_explain, cmd_doctor, and compatibility_resolver.resolve were each run directly against a
directory containing only this set (and separately, against a vendored copy of only this code
set) and confirmed to succeed -- see
docs/superpowers/specs/2026-09-12-sb-cli-diagnostics-design.md.

Run before `python -m build` in cli/. The two output directories are gitignored build inputs,
rebuilt from scratch on every run, never committed.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI_ROOT = ROOT / "cli"
VENDORED_ROOT = CLI_ROOT / "sb" / "_vendored"
SNAPSHOT_ROOT = CLI_ROOT / "sb" / "_registry_snapshot"

# `git ls-files "scripts/*.py"` matches recursively in this repo's git pathspec behavior (`*`
# crosses `/`) -- verified directly, not assumed -- so this one pattern already covers
# scripts/registry/*.py and scripts/evals/*.py (both needed transitively) without listing them
# separately. scripts/tests/ is filtered out below in Python (simpler and more robust than a
# git exclude pathspec, and confirmed sufficient: nothing doctor.py/registry/cli.py imports
# lives under scripts/tests/).
_CODE_PATHSPEC = "scripts/*.py"
_CODE_EXCLUDE_PREFIX = "scripts/tests/"

# Every data file the four target commands read, verified empirically (see module docstring).
# scripts/registry/*.yaml also pulls in scripts/registry/skills.d/*.yaml's ~50 source fragments
# alongside the ~11 real config files -- harmless (small, unused by any of the four commands,
# which read the already-materialized skills.yaml instead) and not filtered out, since excluding
# them would need extra logic for no functional benefit.
_DATA_PATHSPECS = (
    "skills.yaml",
    "agent-hosts.yaml",
    "VERSION",
    "scripts/registry/*.yaml",
    "skills/**",
    "docs/skill-framework/**",
)


def _tracked_files(repo_root: Path, *pathspecs: str) -> list[str]:
    """Git-tracked file paths (relative to repo_root) matching any of pathspecs."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z", "--", *pathspecs],
        check=True,
        capture_output=True,
        text=True,
    )
    return [rel for rel in result.stdout.split("\0") if rel]


def _copy_files(repo_root: Path, rel_paths: list[str], dest_root: Path) -> None:
    for rel in rel_paths:
        src = repo_root / rel
        dest = dest_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def build_snapshot(repo_root: Path = ROOT) -> tuple[int, int]:
    """Rebuild both output directories from scratch. Returns (code file count, data file count)."""
    if VENDORED_ROOT.exists():
        shutil.rmtree(VENDORED_ROOT)
    if SNAPSHOT_ROOT.exists():
        shutil.rmtree(SNAPSHOT_ROOT)

    code_files = [
        rel
        for rel in _tracked_files(repo_root, _CODE_PATHSPEC)
        if not rel.startswith(_CODE_EXCLUDE_PREFIX)
    ]
    _copy_files(repo_root, code_files, VENDORED_ROOT)

    data_files = _tracked_files(repo_root, *_DATA_PATHSPECS)
    _copy_files(repo_root, data_files, SNAPSHOT_ROOT)

    return len(code_files), len(data_files)


def main(argv: list[str] | None = None) -> int:
    code_count, data_count = build_snapshot()
    print(f"ok: vendored {code_count} code files into {VENDORED_ROOT}")
    print(f"ok: snapshotted {data_count} data files into {SNAPSHOT_ROOT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
