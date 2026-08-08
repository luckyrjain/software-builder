"""Tests for self-contained skill packaging."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from package_skill import package_skill  # noqa: E402
from validate_references import validate_tree  # noqa: E402


@pytest.fixture
def isolated_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "software-builder"
    shutil.copytree(ROOT / "unit-test-creator", repo / "unit-test-creator")
    shutil.copytree(ROOT / "docs" / "skill-framework", repo / "docs" / "skill-framework")
    specs = ROOT / "docs" / "superpowers" / "specs"
    if specs.is_dir():
        shutil.copytree(specs, repo / "docs" / "superpowers" / "specs")
    return repo


def test_package_skill_vendors_framework_and_validates(isolated_repo: Path, tmp_path: Path) -> None:
    dest = tmp_path / "installed" / "unit-test-creator"
    package_skill(
        skill="unit-test-creator",
        repo_root=isolated_repo,
        dest=dest,
        host="cursor",
    )

    framework_readme = dest / "docs" / "skill-framework" / "README.md"
    assert framework_readme.is_file()

    skill_md = dest / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    assert "../docs/skill-framework/" not in text
    assert "docs/skill-framework/shared/test-creation-principles.md" in text

    manifest = json.loads((dest / ".software-builder-manifest.json").read_text(encoding="utf-8"))
    assert manifest["skill"] == "unit-test-creator"
    assert manifest["host"] == "cursor"
    assert "shared/test-creation-principles.md" in manifest["framework_files"]

    errors = validate_tree(dest, check_anchors=False, installed_package=True)
    assert errors == []
