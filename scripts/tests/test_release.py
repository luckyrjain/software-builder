"""Tests for release packaging."""

from __future__ import annotations

import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_package_release_writes_checksums(tmp_path: Path) -> None:
    from scripts.package_release import package_release

    archive_path, checksum_path = package_release(ROOT, tmp_path)
    assert archive_path.is_file()
    assert checksum_path.is_file()
    assert "software-builder-" in archive_path.name

    with tarfile.open(archive_path, "r:gz") as tar:
        names = tar.getnames()
    assert any(name.endswith("VERSION") for name in names)
    assert any(name.endswith("skills.yaml") for name in names)
