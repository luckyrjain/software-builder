#!/usr/bin/env python3
"""Read distribution version and source identity for manifests and release tooling."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
_SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def read_distribution_version(root: Path | None = None) -> str:
    version_path = (root or ROOT) / "VERSION"
    if not version_path.is_file():
        raise ValueError(f"missing distribution VERSION file: {version_path}")
    version = version_path.read_text(encoding="utf-8").strip()
    if not _SEMVER_RE.fullmatch(version):
        raise ValueError(f"VERSION must be MAJOR.MINOR.PATCH semantic version, got {version!r}")
    return version


def git_source_sha(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        sha = result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise ValueError("release provenance requires a readable Git HEAD") from exc
    if not re.fullmatch(r"[0-9a-f]{40,64}", sha):
        raise ValueError(f"unexpected Git source SHA: {sha!r}")
    return sha
