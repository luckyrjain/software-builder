"""Tests for the shared MANIFEST_NAME reader (scripts/reference_utils.py)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from scripts.reference_utils import MANIFEST_NAME, ManifestError, read_manifest_file


def test_read_manifest_file_parses_valid_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / MANIFEST_NAME
    manifest_path.write_text('{"skill": "demo", "source_sha": "abc123"}', encoding="utf-8")

    manifest = read_manifest_file(manifest_path)

    assert manifest == {"skill": "demo", "source_sha": "abc123"}


def test_read_manifest_file_missing_raises_with_path(tmp_path: Path) -> None:
    manifest_path = tmp_path / MANIFEST_NAME

    with pytest.raises(ManifestError, match=f"missing manifest: {manifest_path}"):
        read_manifest_file(manifest_path)


def test_read_manifest_file_invalid_json_raises(tmp_path: Path) -> None:
    manifest_path = tmp_path / MANIFEST_NAME
    manifest_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ManifestError, match="invalid manifest JSON"):
        read_manifest_file(manifest_path)


def test_read_manifest_file_non_object_root_raises(tmp_path: Path) -> None:
    manifest_path = tmp_path / MANIFEST_NAME
    manifest_path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(ManifestError, match="manifest is not a JSON object"):
        read_manifest_file(manifest_path)


def test_read_manifest_file_directory_at_path_raises_missing(tmp_path: Path) -> None:
    # Path.is_file() returns False for a directory too, so a directory
    # sitting at the manifest path (e.g. from some other tooling bug) falls
    # into the same "missing manifest" branch as a genuinely absent path --
    # confirm that degrades the same way rather than raising something else.
    manifest_path = tmp_path / MANIFEST_NAME
    manifest_path.mkdir()

    with pytest.raises(ManifestError, match=f"missing manifest: {manifest_path}"):
        read_manifest_file(manifest_path)


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="chmod 0o000 doesn't block reads for root or on Windows",
)
def test_read_manifest_file_unreadable_raises_manifest_error(tmp_path: Path) -> None:
    # A manifest that exists but can't be read (permissions, a transient FS
    # error) used to escape as a raw OSError/PermissionError -- neither
    # caller catches anything but ManifestError, so doctor.py would crash
    # its whole run instead of degrading that one skill, and install_support
    # verify would crash instead of its clean "error: ..." + exit 1.
    manifest_path = tmp_path / MANIFEST_NAME
    manifest_path.write_text("{}", encoding="utf-8")
    manifest_path.chmod(0o000)
    try:
        with pytest.raises(ManifestError, match="cannot read manifest"):
            read_manifest_file(manifest_path)
    finally:
        manifest_path.chmod(0o644)


def test_manifest_error_is_a_value_error(tmp_path: Path) -> None:
    # doctor.py's _installed_manifest catches ManifestError specifically and
    # degrades to None; confirm it also satisfies any broader `except
    # ValueError` a caller might use.
    assert issubclass(ManifestError, ValueError)
