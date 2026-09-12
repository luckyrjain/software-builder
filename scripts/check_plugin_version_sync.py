#!/usr/bin/env python3
"""Fail when a native-plugin manifest's version has drifted from the repo's distribution VERSION.

`.codex-plugin/plugin.json` (and any future `.claude-plugin/plugin.json`) carries its own
`"version"` field, independent of the root `VERSION` file `scripts/release_info.py` treats as
canonical. Nothing enforced the two stay equal, so `.codex-plugin/plugin.json` drifted to
`0.1.0` while `VERSION` moved on to `1.4.0` — this script closes that gap the same way
`scripts/check_pinned_actions.py` closes its own drift risk: a hard-fail, not a silent gate.

`cli/pyproject.toml`'s `[project].version` (the standalone `sb` CLI package) needs the same
guarantee, in a different file format (`tomllib.load` needs a binary-mode file, not
`json.loads` on decoded text) -- it gets its own manifest list and check function rather than a
strained shared abstraction over two unrelated parsers.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.release_info import read_distribution_version  # noqa: E402

# Every native-plugin manifest whose "version" field must track VERSION. Add a path here
# (not a second, hand-copied check) when a future plugin bundle (e.g. .claude-plugin) gains
# its own versioned manifest.
PLUGIN_MANIFESTS: tuple[str, ...] = (".codex-plugin/plugin.json",)

# TOML manifests whose [project].version must track VERSION -- same rationale as
# PLUGIN_MANIFESTS, a different file format so it gets its own tuple and check function.
TOML_MANIFESTS: tuple[str, ...] = ("cli/pyproject.toml",)


def _drifted_json_versions(repo_root: Path, distribution_version: str) -> list[str]:
    errors: list[str] = []
    for relpath in PLUGIN_MANIFESTS:
        manifest_path = repo_root / relpath
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{relpath}: invalid JSON ({exc})")
            continue
        plugin_version = manifest.get("version")
        if plugin_version != distribution_version:
            errors.append(
                f"{relpath}: version {plugin_version!r} does not match VERSION "
                f"{distribution_version!r} -- bump {relpath} to match on every release"
            )
    return errors


def _drifted_toml_versions(repo_root: Path, distribution_version: str) -> list[str]:
    errors: list[str] = []
    for relpath in TOML_MANIFESTS:
        manifest_path = repo_root / relpath
        if not manifest_path.is_file():
            continue
        try:
            with manifest_path.open("rb") as handle:
                manifest = tomllib.load(handle)
        except tomllib.TOMLDecodeError as exc:
            errors.append(f"{relpath}: invalid TOML ({exc})")
            continue
        project_version = manifest.get("project", {}).get("version")
        if project_version != distribution_version:
            errors.append(
                f"{relpath}: version {project_version!r} does not match VERSION "
                f"{distribution_version!r} -- bump {relpath} to match on every release"
            )
    return errors


def drifted_plugin_versions(repo_root: Path) -> list[str]:
    """One message per plugin/CLI manifest whose version does not match VERSION.

    A manifest that does not exist yet is skipped, not an error -- this check guards drift in
    manifests that exist, it does not mandate that every listed path be present (that's
    scripts/check_platform_files.py's job for load-bearing files).
    """
    try:
        distribution_version = read_distribution_version(repo_root)
    except (OSError, ValueError) as exc:
        # OSError (not just ValueError) so a VERSION file that exists but isn't readable
        # (e.g. a permission error) prints a clean error instead of an uncaught traceback.
        # Not pre-prefixed with "error:" here -- main()'s print loop is the single place
        # that adds that prefix, uniformly, for every message this function can return.
        return [str(exc)]
    errors = _drifted_json_versions(repo_root, distribution_version)
    errors.extend(_drifted_toml_versions(repo_root, distribution_version))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_plugin_version_sync")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    errors = drifted_plugin_versions(args.repo_root)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
