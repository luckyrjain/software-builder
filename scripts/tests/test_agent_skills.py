"""Tests for portable Agent Skills conformance validation."""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from scripts.registry import cli

ROOT = Path(__file__).resolve().parents[2]


def _validator():
    return importlib.import_module("scripts.registry.agent_skills")


def _skill_dir(tmp_path: Path, name: str = "valid-skill") -> Path:
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    return skill_dir


def _write_skill(skill_dir: Path, frontmatter: str | None) -> None:
    content = "# Skill\n"
    if frontmatter is not None:
        content = f"---\n{frontmatter}\n---\n\n{content}"
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


def _errors(skill_dir: Path) -> list[str]:
    return _validator().validate_skill(skill_dir)


def test_rejects_missing_skill_md(tmp_path: Path) -> None:
    skill_dir = _skill_dir(tmp_path)

    assert _errors(skill_dir) == ["error: valid-skill/SKILL.md: missing SKILL.md"]


def test_rejects_missing_frontmatter(tmp_path: Path) -> None:
    skill_dir = _skill_dir(tmp_path)
    _write_skill(skill_dir, None)

    assert _errors(skill_dir) == [
        "error: valid-skill/SKILL.md: missing YAML frontmatter",
    ]


def test_rejects_invalid_yaml_frontmatter(tmp_path: Path) -> None:
    skill_dir = _skill_dir(tmp_path)
    _write_skill(skill_dir, "name: valid-skill\ndescription: [")

    assert any("error: valid-skill/SKILL.md: invalid YAML frontmatter" in error for error in _errors(skill_dir))


def test_rejects_missing_name(tmp_path: Path) -> None:
    skill_dir = _skill_dir(tmp_path)
    _write_skill(skill_dir, "description: A description.")

    assert _errors(skill_dir) == ["error: valid-skill/SKILL.md: missing name"]


@pytest.mark.parametrize("description", [None, ""])
def test_rejects_missing_or_empty_description(tmp_path: Path, description: str | None) -> None:
    skill_dir = _skill_dir(tmp_path)
    field = "" if description is None else f'description: "{description}"\n'
    _write_skill(skill_dir, f"name: valid-skill\n{field}".rstrip())

    expected = "missing description" if description is None else "description must be non-empty"
    assert _errors(skill_dir) == [f"error: valid-skill/SKILL.md: {expected}"]


@pytest.mark.parametrize(
    ("directory", "skill_name", "expected"),
    [
        ("valid-skill", "Valid-skill", "name must be lowercase kebab-case"),
        ("valid-skill", "valid_skill", "name must be lowercase kebab-case"),
        ("valid-skill", "-valid-skill", "name must not have leading or trailing hyphens"),
        ("valid-skill", "valid-skill-", "name must not have leading or trailing hyphens"),
        ("valid-skill", "valid--skill", "name must not contain consecutive hyphens"),
    ],
)
def test_rejects_invalid_skill_name(
    tmp_path: Path,
    directory: str,
    skill_name: str,
    expected: str,
) -> None:
    skill_dir = _skill_dir(tmp_path, directory)
    _write_skill(skill_dir, f"name: {skill_name}\ndescription: A description.")

    assert _errors(skill_dir) == [f"error: {directory}/SKILL.md: {expected}"]


def test_rejects_name_longer_than_64_characters(tmp_path: Path) -> None:
    skill_name = "a" * 65
    skill_dir = _skill_dir(tmp_path, skill_name)
    _write_skill(skill_dir, f"name: {skill_name}\ndescription: A description.")

    assert _errors(skill_dir) == [f"error: {skill_name}/SKILL.md: name exceeds 64 characters"]


def test_rejects_name_that_does_not_match_directory(tmp_path: Path) -> None:
    skill_dir = _skill_dir(tmp_path, "directory-name")
    _write_skill(skill_dir, "name: another-name\ndescription: A description.")

    assert _errors(skill_dir) == [
        "error: directory-name/SKILL.md: name 'another-name' does not match directory 'directory-name'",
    ]


def test_rejects_description_longer_than_1024_characters(tmp_path: Path) -> None:
    skill_dir = _skill_dir(tmp_path)
    _write_skill(skill_dir, f"name: valid-skill\ndescription: {'a' * 1025}")

    assert _errors(skill_dir) == [
        "error: valid-skill/SKILL.md: description exceeds 1024 characters",
    ]


def test_rejects_unknown_frontmatter_key(tmp_path: Path) -> None:
    skill_dir = _skill_dir(tmp_path)
    _write_skill(
        skill_dir,
        "name: valid-skill\ndescription: A description.\nunsupported: true",
    )

    assert _errors(skill_dir) == [
        "error: valid-skill/SKILL.md: unknown SKILL.md frontmatter key 'unsupported'",
    ]


def test_rejects_non_boolean_disable_model_invocation(tmp_path: Path) -> None:
    skill_dir = _skill_dir(tmp_path)
    _write_skill(
        skill_dir,
        'name: valid-skill\ndescription: A description.\ndisable-model-invocation: "true"',
    )

    assert _errors(skill_dir) == [
        "error: valid-skill/SKILL.md: disable-model-invocation must be a boolean, got str",
    ]


def test_accepts_valid_minimal_skill(tmp_path: Path) -> None:
    skill_dir = _skill_dir(tmp_path)
    _write_skill(skill_dir, "name: valid-skill\ndescription: A description.")

    assert _errors(skill_dir) == []


def test_current_canonical_skills_conform() -> None:
    assert _validator().validate_agent_skills(ROOT) == []


def test_registry_cli_validates_agent_skills() -> None:
    assert cli.main(["validate-agent-skills"]) == 0
