"""Tests for installed-package reference validation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_references import validate_tree  # noqa: E402


def test_installed_package_flags_missing_skill_local_link(tmp_path: Path) -> None:
    package = tmp_path / "skill"
    package.mkdir()
    (package / "SKILL.md").write_text(
        "Broken: [missing](reference/missing.md)\n",
        encoding="utf-8",
    )

    errors = validate_tree(package, check_anchors=False, installed_package=True)
    assert any("reference/missing.md" in error for error in errors)


def test_installed_package_ignores_optional_external_link(tmp_path: Path) -> None:
    package = tmp_path / "skill"
    framework = package / "docs" / "skill-framework" / "shared"
    framework.mkdir(parents=True)
    (framework / "routing.md").write_text(
        "Optional: [other-skill](../../pr-review/SETUP.md)\n",
        encoding="utf-8",
    )

    errors = validate_tree(package, check_anchors=False, installed_package=True)
    assert errors == []


def test_installed_package_flags_missing_framework_link(tmp_path: Path) -> None:
    package = tmp_path / "skill"
    package.mkdir()
    (package / "SKILL.md").write_text(
        "Broken: [routing](docs/skill-framework/shared/routing.md)\n",
        encoding="utf-8",
    )
    (package / "docs" / "skill-framework" / "shared").mkdir(parents=True)

    errors = validate_tree(package, check_anchors=False, installed_package=True)
    assert any("routing.md" in error for error in errors)
