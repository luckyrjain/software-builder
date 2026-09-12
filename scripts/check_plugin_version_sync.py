"""Validate that plugin/CLI version fields stay in sync with the root VERSION file."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from scripts.release_info import read_distribution_version

# JSON manifests whose version field must track VERSION -- a guard against
# forgetting to bump these files during releases, caught early by a pre-commit
# or CI validator rather than discovered as a mismatch after release.
PLUGIN_MANIFESTS: tuple[str, ...] = (".codex-plugin/plugin.json",)

# TOML manifests whose [project].version must track VERSION -- same rationale as
# PLUGIN_MANIFESTS, a different file format (tomllib.load needs a binary-mode file, not
# json.loads on decoded text) so it gets its own tuple and check function rather than a
# strained shared abstraction over two unrelated parsers.
TOML_MANIFESTS: tuple[str, ...] = ("cli/pyproject.toml",)


def _drifted_json_versions(repo_root: Path, distribution_version: str) -> list[str]:
    errors: list[str] = []
    for relpath in PLUGIN_MANIFESTS:
        manifest_path = repo_root / relpath
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{relpath}: invalid JSON ({exc})")
            continue
        manifest_version = manifest.get("version")
        if manifest_version != distribution_version:
            errors.append(
                f"{relpath}: version {manifest_version!r} does not match VERSION "
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
    """Check that all version fields in plugin manifests match the root VERSION file.

    Returns a list of error messages (one per drift detected). Empty list means all
    manifests are in sync.
    """
    distribution_version = read_distribution_version(repo_root)
    errors = _drifted_json_versions(repo_root, distribution_version)
    errors.extend(_drifted_toml_versions(repo_root, distribution_version))
    return errors


def main() -> int:
    """CLI entrypoint: validate version sync, print errors, exit 1 if any drift found."""
    import sys

    repo_root = Path.cwd()
    errors = drifted_plugin_versions(repo_root)
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
