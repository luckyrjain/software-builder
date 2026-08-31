"""Portable Agent Skills frontmatter conformance validation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from scripts.registry.frontmatter import load_skill_frontmatter
from scripts.registry.load import load_registry
from scripts.registry.skill_frontmatter_schema import validate_skill_frontmatter_fields

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
KEBAB_CASE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _error(skill_dir: Path, message: str) -> str:
    return f"error: {skill_dir.name}/SKILL.md: {message}"


def _validate_name(skill_dir: Path, frontmatter: dict[str, Any]) -> list[str]:
    if "name" not in frontmatter:
        return [_error(skill_dir, "missing name")]

    name = frontmatter["name"]
    if not isinstance(name, str):
        return [_error(skill_dir, "name must be a string")]
    if len(name) > MAX_NAME_LENGTH:
        return [_error(skill_dir, f"name exceeds {MAX_NAME_LENGTH} characters")]
    if name.startswith("-") or name.endswith("-"):
        return [_error(skill_dir, "name must not have leading or trailing hyphens")]
    if "--" in name:
        return [_error(skill_dir, "name must not contain consecutive hyphens")]
    if not KEBAB_CASE_RE.fullmatch(name):
        return [_error(skill_dir, "name must be lowercase kebab-case")]
    if name != skill_dir.name:
        return [_error(skill_dir, f"name {name!r} does not match directory {skill_dir.name!r}")]
    return []


def _validate_description(skill_dir: Path, frontmatter: dict[str, Any]) -> list[str]:
    if "description" not in frontmatter:
        return [_error(skill_dir, "missing description")]

    description = frontmatter["description"]
    if not isinstance(description, str):
        return [_error(skill_dir, "description must be a string")]
    if not description.strip():
        return [_error(skill_dir, "description must be non-empty")]
    if len(description) > MAX_DESCRIPTION_LENGTH:
        return [_error(skill_dir, f"description exceeds {MAX_DESCRIPTION_LENGTH} characters")]
    return []


def _validate_schema(skill_dir: Path, frontmatter: dict[str, Any]) -> list[str]:
    schema_prefix = f"error: {skill_dir.name}: "
    return [
        _error(skill_dir, error.removeprefix(schema_prefix))
        for error in validate_skill_frontmatter_fields(skill_dir.name, frontmatter)
    ]


def validate_skill(skill_dir: Path) -> list[str]:
    """Validate one skill directory's portable Agent Skills frontmatter."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return [_error(skill_dir, "missing SKILL.md")]

    try:
        frontmatter = load_skill_frontmatter(skill_md)
    except yaml.YAMLError as exc:
        return [_error(skill_dir, f"invalid YAML frontmatter: {exc}")]
    except ValueError as exc:
        if str(exc).startswith("missing YAML frontmatter:"):
            return [_error(skill_dir, "missing YAML frontmatter")]
        return [_error(skill_dir, f"invalid YAML frontmatter: {exc}")]
    except OSError as exc:
        return [_error(skill_dir, f"unable to read SKILL.md: {exc}")]

    return (
        _validate_name(skill_dir, frontmatter)
        + _validate_description(skill_dir, frontmatter)
        + _validate_schema(skill_dir, frontmatter)
    )


def validate_agent_skills(root: Path) -> list[str]:
    """Validate the SKILL.md files for every canonical registered skill."""
    registry = load_registry(root)
    errors: list[str] = []
    for _skill_id, entry in sorted(registry.skills.items()):
        errors.extend(validate_skill(root / entry.path))
    return errors
