"""SKILL.md YAML frontmatter schema (v1).

Platform facts live in skills.yaml; SKILL.md frontmatter is agent-discovery prose
only, plus automation invocation guards and lifecycle metadata.
"""

from __future__ import annotations

from typing import Any

from scripts.registry.schema import AUTOMATION_ONLY_INVOCATION

ALLOWED_FRONTMATTER_KEYS = frozenset(
    {
        "name",
        "description",
        "disable-model-invocation",
        "status",
        "deprecated",
        "deprecation",
    },
)


def validate_skill_frontmatter_fields(skill_id: str, frontmatter: dict[str, Any]) -> list[str]:
    """Return human-readable errors for invalid or unknown SKILL.md frontmatter keys."""
    errors: list[str] = []
    for key in frontmatter:
        if key not in ALLOWED_FRONTMATTER_KEYS:
            errors.append(f"error: {skill_id}: unknown SKILL.md frontmatter key {key!r}")

    if "disable-model-invocation" in frontmatter:
        disable = frontmatter["disable-model-invocation"]
        if not isinstance(disable, bool):
            errors.append(
                f"error: {skill_id}: disable-model-invocation must be a boolean, got {type(disable).__name__}",
            )

    if "status" in frontmatter and not isinstance(frontmatter["status"], str):
        errors.append(f"error: {skill_id}: status must be a string")
    if "deprecated" in frontmatter and not isinstance(frontmatter["deprecated"], bool):
        errors.append(f"error: {skill_id}: deprecated must be a boolean")
    if "deprecation" in frontmatter and not isinstance(frontmatter["deprecation"], dict):
        errors.append(f"error: {skill_id}: deprecation must be a mapping")
    return errors


def automation_only_guard_errors(invocation: str, frontmatter: dict[str, Any]) -> list[str]:
    """Check SKILL.md's disable-model-invocation agrees with skills.yaml's invocation."""
    disable = frontmatter.get("disable-model-invocation") is True
    automation_only = invocation == AUTOMATION_ONLY_INVOCATION
    if disable == automation_only:
        return []
    return [f"disable-model-invocation={disable} but invocation={invocation!r}"]

