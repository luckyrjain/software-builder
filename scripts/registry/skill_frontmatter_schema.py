"""SKILL.md YAML frontmatter schema (v1).

Platform facts live in skills.yaml; SKILL.md frontmatter is agent-discovery prose only.
"""

from __future__ import annotations

from typing import Any

ALLOWED_FRONTMATTER_KEYS = frozenset(
    {
        "name",
        "description",
        "skill_version",
        "disable-model-invocation",
    },
)


def validate_skill_frontmatter_fields(skill_id: str, frontmatter: dict[str, Any]) -> list[str]:
    """Return human-readable errors for invalid or unknown SKILL.md frontmatter keys."""
    errors: list[str] = []

    for key in frontmatter:
        if key not in ALLOWED_FRONTMATTER_KEYS:
            errors.append(f"error: {skill_id}: unknown SKILL.md frontmatter key {key!r}")

    if "skill_version" in frontmatter:
        version = frontmatter["skill_version"]
        if not isinstance(version, (int, float)):
            errors.append(
                f"error: {skill_id}: skill_version must be a number, got {type(version).__name__}",
            )

    if "disable-model-invocation" in frontmatter:
        disable = frontmatter["disable-model-invocation"]
        if not isinstance(disable, bool):
            errors.append(
                f"error: {skill_id}: disable-model-invocation must be a boolean, got {type(disable).__name__}",
            )

    return errors
