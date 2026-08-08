"""Tests for install rollback on validation failure."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_install_restores_previous_package_when_validation_fails(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    skill_dir = repo / "broken-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "See [missing](reference/missing.md)\n",
        encoding="utf-8",
    )
    shutil.copytree(ROOT / "scripts", repo / "scripts")

    dest = home / ".cursor" / "skills" / "broken-skill"
    dest.parent.mkdir(parents=True)
    dest.mkdir()
    marker = dest / "KEEP_ME.txt"
    marker.write_text("previous install\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(repo / "scripts" / "install.sh"), "--agent", "cursor", "broken-skill"],
        cwd=repo,
        env={"HOME": str(home), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert marker.is_file()
    assert marker.read_text(encoding="utf-8") == "previous install\n"
    assert "dangling link" in result.stderr or "missing.md" in result.stderr


def test_package_skill_writes_manifest(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    shutil.copytree(ROOT / "unit-test-creator", repo / "unit-test-creator")
    shutil.copytree(ROOT / "docs" / "skill-framework", repo / "docs" / "skill-framework")
    dest = tmp_path / "installed"

    subprocess.run(
        [
            "python3",
            str(ROOT / "scripts" / "package_skill.py"),
            "--skill",
            "unit-test-creator",
            "--dest",
            str(dest),
            "--repo-root",
            str(repo),
            "--host",
            "cursor",
        ],
        check=True,
    )

    manifest = json.loads((dest / ".software-builder-manifest.json").read_text(encoding="utf-8"))
    assert manifest["skill"] == "unit-test-creator"
    assert "SKILL.md" in manifest["files"]
