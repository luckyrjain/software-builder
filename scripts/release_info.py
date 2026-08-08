#!/usr/bin/env python3
"""Read distribution version and source identity for manifests and release tooling."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"


def read_distribution_version(root: Path | None = None) -> str:
    version_path = (root or ROOT) / "VERSION"
    if not version_path.is_file():
        return "0.0.0"
    version = version_path.read_text(encoding="utf-8").strip()
    return version or "0.0.0"


def git_source_sha(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
