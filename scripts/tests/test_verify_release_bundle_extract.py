"""_safe_extract refuses every tar member that could write outside the extraction directory."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from scripts.verify_release_bundle import _safe_extract


def _bundle(path: Path, members: list) -> Path:
    with tarfile.open(path, "w:gz") as tar:
        for member in members:
            if isinstance(member, tuple):
                name, data = member
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            else:
                tar.addfile(member)
    return path


def test_safe_extract_writes_plain_files_and_directories(tmp_path: Path) -> None:
    directory = tarfile.TarInfo("pkg")
    directory.type = tarfile.DIRTYPE
    archive = _bundle(tmp_path / "ok.tar.gz", [directory, ("pkg/SKILL.md", b"# skill\n")])
    dest = tmp_path / "out"
    dest.mkdir()

    _safe_extract(archive, dest)

    assert (dest / "pkg" / "SKILL.md").read_bytes() == b"# skill\n"


@pytest.mark.parametrize("name", ["../escape.txt", "pkg/../../escape.txt", "/abs/escape.txt"])
def test_safe_extract_refuses_members_that_escape_dest(tmp_path: Path, name: str) -> None:
    archive = _bundle(tmp_path / "bad.tar.gz", [(name, b"x")])
    dest = tmp_path / "out"
    dest.mkdir()

    with pytest.raises(ValueError, match="escapes the extraction directory"):
        _safe_extract(archive, dest)

    assert not (tmp_path / "escape.txt").exists()
    assert not list(dest.iterdir())


@pytest.mark.parametrize(
    "member_type", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE]
)
def test_safe_extract_refuses_non_regular_members(tmp_path: Path, member_type: bytes) -> None:
    link = tarfile.TarInfo("pkg/link")
    link.type = member_type
    link.linkname = "/etc/passwd"
    archive = _bundle(tmp_path / "link.tar.gz", [link])
    dest = tmp_path / "out"
    dest.mkdir()

    with pytest.raises(ValueError, match="not a regular file or directory"):
        _safe_extract(archive, dest)

    assert not list(dest.iterdir())


def test_safe_extract_refuses_oversized_bundles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.verify_release_bundle as module

    monkeypatch.setattr(module, "_MAX_EXTRACTED_BYTES", 4)
    archive = _bundle(tmp_path / "big.tar.gz", [("pkg/a", b"12345")])
    dest = tmp_path / "out"
    dest.mkdir()

    with pytest.raises(ValueError, match="byte limit"):
        _safe_extract(archive, dest)
