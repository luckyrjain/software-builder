"""SKILL.md YAML frontmatter schema (v1)."""

from __future__ import annotations

from typing import Any

from scripts.registry.schema import AUTOMATION_ONLY_INVOCATION

# Compatibility symbol retained for explicit legacy-fixture validation only.
PLATFORM_CONTRACT = "skill-platform-v1"

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
LEGACY_FRONTMATTER_KEYS = frozenset({"skill_version", "platform_contract"})


def validate_skill_frontmatter_fields(
    skill_id: str,
    frontmatter: dict[str, Any],
    *,
    require_legacy_platform_fields: bool = False,
) -> list[str]:
    errors: list[str] = []
    allowed_keys = ALLOWED_FRONTMATTER_KEYS | (
        LEGACY_FRONTMATTER_KEYS if require_legacy_platform_fields else set()
    )
    for key in frontmatter:
        if key not in allowed_keys:
            errors.append(f"error: {skill_id}: unknown SKILL.md frontmatter key {key!r}")

    if require_legacy_platform_fields and "platform_contract" in frontmatter and frontmatter["platform_contract"] != PLATFORM_CONTRACT:
        errors.append(
            f"error: {skill_id}: platform_contract must be {PLATFORM_CONTRACT!r}, "
            f"got {frontmatter['platform_contract']!r}",
        )

    if require_legacy_platform_fields and "skill_version" not in frontmatter:
        errors.append(f"error: {skill_id}: skill_version is mandatory")
    elif require_legacy_platform_fields and "skill_version" in frontmatter:
        version = frontmatter["skill_version"]
        if isinstance(version, bool) or not isinstance(version, (int, float, str)):
            errors.append(
                f"error: {skill_id}: skill_version must be a number or a semver string, "
                f"got {type(version).__name__}",
            )

    if "disable-model-invocation" in frontmatter and not isinstance(
        frontmatter["disable-model-invocation"], bool
    ):
        errors.append(
            f"error: {skill_id}: disable-model-invocation must be a boolean, "
            f"got {type(frontmatter['disable-model-invocation']).__name__}",
        )
    if "status" in frontmatter and not isinstance(frontmatter["status"], str):
        errors.append(f"error: {skill_id}: status must be a string")
    if "deprecated" in frontmatter and not isinstance(frontmatter["deprecated"], bool):
        errors.append(f"error: {skill_id}: deprecated must be a boolean")
    if "deprecation" in frontmatter and not isinstance(frontmatter["deprecation"], dict):
        errors.append(f"error: {skill_id}: deprecation must be a mapping")
    return errors


def automation_only_guard_errors(invocation: str, frontmatter: dict[str, Any]) -> list[str]:
    disable = frontmatter.get("disable-model-invocation") is True
    automation_only = invocation == AUTOMATION_ONLY_INVOCATION
    if disable == automation_only:
        return []
    return [f"disable-model-invocation={disable} but invocation={invocation!r}"]
