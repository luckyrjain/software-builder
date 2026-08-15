from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from scripts.registry.generic_package import _tracked_files


def test_tracked_symlink_is_rejected_before_resolution(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symlinks unsupported")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    target = tmp_path / "target.md"
    target.write_text("# Target\n", encoding="utf-8")
    link = tmp_path / "link.md"
    link.symlink_to(target.name)
    subprocess.run(["git", "-C", str(tmp_path), "add", "link.md"], check=True)

    with pytest.raises(ValueError, match="tracked symlink"):
        _tracked_files(tmp_path.resolve())
