"""Tests for install.sh safety checks."""

from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.tests.install_test_helpers import install_subprocess_env

ROOT = Path(__file__).resolve().parents[2]


def test_install_rejects_path_traversal_skill_name(tmp_path: Path) -> None:
    env = install_subprocess_env(tmp_path / "home", repo=ROOT)
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
