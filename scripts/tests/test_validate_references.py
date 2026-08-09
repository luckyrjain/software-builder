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


def test_strip_fenced_code_blocks_tracks_delimiter_length() -> None:
    from reference_utils import strip_fenced_code_blocks

    # A 4-backtick fence containing a legitimately nested 3-backtick fenced excerpt: the
    # inner ``` line must not be treated as closing the outer fence (a naive boolean toggle
    # would exit the outer fence there, leaking the tail content — including a fake link
    # target — as unfenced text).
    text = (
        "Before [real](./real.md).\n"
        "````text\n"
        "outer content\n"
        "```python\n"
        "inner content [fake](./fake.md)\n"
        "```\n"
        "outer tail [also-fake](./also-fake.md)\n"
        "````\n"
        "After [real2](./real2.md).\n"
    )
    stripped = strip_fenced_code_blocks(text)
    assert "[real]" in stripped
    assert "[real2]" in stripped
    assert "[fake]" not in stripped
    assert "[also-fake]" not in stripped


def test_strip_fenced_code_blocks_handles_indented_list_fence() -> None:
    from reference_utils import strip_fenced_code_blocks

    # A fence indented up to 3 spaces (nested inside a numbered-list step, the shape used
    # throughout this repo's workflow/*.md files) is still a real CommonMark fence — its
    # content must be stripped, not treated as ordinary indented prose.
    text = (
        "1. Step one:\n"
        "   ```bash\n"
        "   echo [fake](./fake.md)\n"
        "   ```\n"
        "   After the fence, still list prose.\n"
        "\n"
        "After [real](./real.md).\n"
    )
    stripped = strip_fenced_code_blocks(text)
    assert "[fake]" not in stripped
    assert "[real]" in stripped
    assert "still list prose" in stripped
