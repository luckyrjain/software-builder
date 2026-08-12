"""SKILL.md YAML frontmatter schema (v1).

Platform facts live in skills.yaml; SKILL.md frontmatter is agent-discovery prose
only -- except automation_only_guard_errors below, which exists specifically to
check one frontmatter field against its skills.yaml counterpart. That's the one
sanctioned exception, not a precedent: a check that's purely about frontmatter
shape belongs in validate_skill_frontmatter_fields; a check that needs a second
platform fact from skills.yaml belongs here only if it's checking frontmatter
against that fact, not deriving new facts from skills.yaml alone.
"""

from __future__ import annotations

from typing import Any

from scripts.registry.schema import AUTOMATION_ONLY_INVOCATION

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


def automation_only_guard_errors(invocation: str, frontmatter: dict[str, Any]) -> list[str]:
    """Check SKILL.md's disable-model-invocation agrees with skills.yaml's invocation.

    Both directions: an automation-only skill must set disable-model-invocation,
    and setting disable-model-invocation implies the skill must be automation-only.

    Returns raw, unprefixed messages (unlike validate_skill_frontmatter_fields
    above) -- crosscheck.py and evals/__main__.py format them into their own
    house styles rather than sharing one "error: {skill_id}: ..." convention.
    """
    disable = frontmatter.get("disable-model-invocation") is True
    automation_only = invocation == AUTOMATION_ONLY_INVOCATION
    if disable == automation_only:
        return []
    return [f"disable-model-invocation={disable} but invocation={invocation!r}"]
