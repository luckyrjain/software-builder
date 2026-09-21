"""Tests for install.sh safety checks."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_install_rejects_path_traversal_skill_name(tmp_path: Path) -> None:
    env = {"HOME": str(tmp_path / "home")}
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "install.sh"), "--agent", "cursor", "../pr-review"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "invalid skill name" in result.stderr


def test_package_skill_rejects_invalid_name(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            "python3",
            str(ROOT / "scripts" / "package_skill.py"),
            "--skill",
            "a/b",
            "--dest",
            str(tmp_path / "dest"),
            "--repo-root",
            str(ROOT),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "invalid skill name" in result.stderr
