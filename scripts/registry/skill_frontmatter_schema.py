"""SKILL.md YAML frontmatter schema (v1).

Platform facts live in skills.yaml; SKILL.md frontmatter is agent-discovery prose
only -- except for explicit cross-check markers such as ``platform_contract`` and
automation invocation guards. The detailed platform policy remains centralized;
frontmatter only declares which contract a skill inherits.
"""

from __future__ import annotations

from typing import Any

from scripts.registry.schema import AUTOMATION_ONLY_INVOCATION

PLATFORM_CONTRACT = "skill-platform-v1"

ALLOWED_FRONTMATTER_KEYS = frozenset(
    {
        "name",
        "description",
        "skill_version",
        "platform_contract",
        "disable-model-invocation",
    },
)


def validate_skill_frontmatter_fields(skill_id: str, frontmatter: dict[str, Any]) -> list[str]:
    """Return human-readable errors for invalid or unknown SKILL.md frontmatter keys.

    This shape validator accepts a missing ``platform_contract`` so isolated/minimal
    repositories can use the generic registry tooling without installing the P1
    platform layer. When that layer is installed, ``validate_p1_contracts`` requires
    the marker on every registered skill.
    """
    errors: list[str] = []

    for key in frontmatter:
        if key not in ALLOWED_FRONTMATTER_KEYS:
            errors.append(f"error: {skill_id}: unknown SKILL.md frontmatter key {key!r}")

    if "platform_contract" in frontmatter:
        platform_contract = frontmatter["platform_contract"]
        if platform_contract != PLATFORM_CONTRACT:
            errors.append(
                f"error: {skill_id}: platform_contract must be {PLATFORM_CONTRACT!r}, "
                f"got {platform_contract!r}",
            )

    if "skill_version" not in frontmatter:
        errors.append(f"error: {skill_id}: skill_version is mandatory")
    else:
        version = frontmatter["skill_version"]
        # Shape check only: a number (legacy `1.0`/`2`) or a string (full
        # semver, e.g. "1.2.3-alpha.1+build.5") -- manifest.py's
        # _normalize_version does the actual semantic validation.
        if isinstance(version, bool) or not isinstance(version, (int, float, str)):
            errors.append(
                f"error: {skill_id}: skill_version must be a number or a semver string, "
                f"got {type(version).__name__}",
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
