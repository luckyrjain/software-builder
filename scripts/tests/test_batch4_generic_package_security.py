from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from scripts.registry.generic_package import _is_safe_file, _tracked_files


def test_tracked_symlink_remains_lexical_and_is_rejected_only_if_packaged(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symlinks unsupported")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    target = tmp_path / "target.md"
    target.write_text("# Target\n", encoding="utf-8")
    link = tmp_path / "link.md"
    link.symlink_to(target.name)
    subprocess.run(["git", "-C", str(tmp_path), "add", "link.md"], check=True)

    tracked = _tracked_files(tmp_path.resolve())
    assert link in tracked
    assert target not in tracked
    with pytest.raises(ValueError, match="refuses symlink"):
        _is_safe_file(tmp_path.resolve(), link)
