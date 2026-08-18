#!/usr/bin/env python3
"""Read distribution version and source identity for manifests and release tooling."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
# Shared with verify_release_bundle.py, which validates the same-shaped fields
# (distribution_version, source_sha) in a release manifest -- a single source
# of truth keeps the two "is this a valid version/SHA" definitions from drifting.
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
# A real Git commit SHA is always exactly 40 hex chars (SHA-1) or exactly 64
# (SHA-256) -- never anything in between -- so this doesn't accept e.g. a
# 50-char string as "SHA-shaped".
SHA_RE = re.compile(r"^([0-9a-f]{40}|[0-9a-f]{64})$")
# Shared between package_release.py (which writes this file into every release
# archive) and verify_release_bundle.py (which reads it back out) so the two
# never drift to different filenames. Named RELEASE_MANIFEST_NAME (not
# MANIFEST_NAME) to avoid colliding with reference_utils.MANIFEST_NAME, a
# different constant (the *installed-skill* manifest filename,
# ".software-builder-manifest.json") that a caller needing both (e.g.
# package_skill.py) would otherwise have to import under an alias.
RELEASE_MANIFEST_NAME = "RELEASE-MANIFEST.json"
# Shared between package_release.py (which names the bundle directory/archive
# from this) and verify_release_bundle.py (which checks the bundle's
# top-level directory name against this) so the two never drift to different
# project-name prefixes.
PACKAGE_NAME = "software-builder"


def read_distribution_version(root: Path | None = None) -> str:
    version_path = (root or ROOT) / "VERSION"
    if not version_path.is_file():
        raise ValueError(f"missing distribution VERSION file: {version_path}")
    version = version_path.read_text(encoding="utf-8").strip()
    if not SEMVER_RE.fullmatch(version):
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
    if not SHA_RE.fullmatch(sha):
        raise ValueError(f"unexpected Git source SHA: {sha!r}")
    return sha
