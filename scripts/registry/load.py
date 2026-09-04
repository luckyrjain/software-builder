from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.registry.models import Registry
from scripts.registry.schema import parse_registry
from scripts.yaml_safety import YAML_SAFETY_ERRORS, load_unique_frontmatter


def load_descriptions(root: Path, registry: Registry) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for skill_id, entry in registry.skills.items():
        frontmatter = load_unique_frontmatter(root / entry.path / "SKILL.md")
        description = frontmatter.get("description", "")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"error: {skill_id}: description must be a non-empty string")
        descriptions[skill_id] = description
    return descriptions


def is_deprecated_frontmatter(frontmatter: dict[str, Any]) -> bool:
    """The same is-deprecated test scripts/deprecation_lifecycle.py and
    scripts/operational_upkeep.py use for governed identities: `status: deprecated`
    or `deprecated: true` in a SKILL.md's YAML frontmatter."""
    return frontmatter.get("status") == "deprecated" or frontmatter.get("deprecated") is True


def load_deprecated_skills(root: Path, registry: Registry) -> dict[str, dict[str, Any]]:
    """Registered skill ids whose SKILL.md frontmatter marks them deprecated.

    Maps each deprecated skill id to its `deprecation` metadata mapping (replacement,
    migration_note, remove_after, ...) so generators can surface *why* a skill is
    deprecated without re-parsing frontmatter themselves. Per
    docs/skill-framework/shared/deprecation-policy.md, marking a skill deprecated
    starts its compatibility window -- it does not remove it from the registry --
    so this is deliberately a separate pass over `registry.skills`, not a filter
    applied inside `load_registry`/`parse_registry`.

    A SKILL.md that can't be read or whose frontmatter is malformed is treated
    conservatively as *not* deprecated (kept active/visible), the same policy
    `scripts/registry/crosscheck.py`'s adapter-pruning pass uses: this function
    runs ahead of the registry/frontmatter-shape validation that's the real,
    reporting-capable place to catch and surface that problem (see
    `_validate_skill_frontmatter_shape`) -- it must not itself crash and discard
    every other check's already-accumulated errors over one skill's bad YAML.
    """
    deprecated: dict[str, dict[str, Any]] = {}
    for skill_id, entry in registry.skills.items():
        try:
            frontmatter = load_unique_frontmatter(root / entry.path / "SKILL.md")
        except (OSError, *YAML_SAFETY_ERRORS):
            continue
        if is_deprecated_frontmatter(frontmatter):
            deprecation = frontmatter.get("deprecation")
            deprecated[skill_id] = deprecation if isinstance(deprecation, dict) else {}
    return deprecated


def load_registry(root: Path) -> Registry:
    return parse_registry(root / "skills.yaml")
