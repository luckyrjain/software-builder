"""Locate this package's bundled snapshot directories at runtime."""

from __future__ import annotations

from importlib import resources
from pathlib import Path


def vendored_scripts_root() -> Path:
    """Directory containing the vendored scripts/ package -- add this to sys.path before
    importing anything under `scripts.*`."""
    return Path(str(resources.files("sb") / "_vendored"))


def registry_snapshot_root() -> Path:
    """Directory that stands in for a repository checkout root when calling the vendored
    scripts.doctor / scripts.registry.cli functions' `root`/`repo_root` parameter."""
    return Path(str(resources.files("sb") / "_registry_snapshot"))
