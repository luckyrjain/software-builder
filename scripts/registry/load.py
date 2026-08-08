from __future__ import annotations

from pathlib import Path

from scripts.registry.frontmatter import load_skill_frontmatter
from scripts.registry.models import Registry
from scripts.registry.schema import parse_registry


def load_descriptions(root: Path, registry: Registry) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for skill_id, entry in registry.skills.items():
        frontmatter = load_skill_frontmatter(root / entry.path / "SKILL.md")
        description = frontmatter.get("description", "")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"error: {skill_id}: description must be a non-empty string")
        descriptions[skill_id] = description
    return descriptions


def load_registry(root: Path) -> Registry:
    return parse_registry(root / "skills.yaml")
