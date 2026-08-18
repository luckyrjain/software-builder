from __future__ import annotations

from scripts.deprecation_lifecycle import validate_deprecation_item
from scripts.registry.skill_frontmatter_schema import validate_skill_frontmatter_fields


REQUIRED = {"deprecated_since", "replacement", "remove_after", "migration_note", "aliases"}


def test_skill_frontmatter_accepts_valid_deprecation_metadata() -> None:
    frontmatter = {
        "name": "legacy-skill",
        "description": "Legacy skill.",
        "skill_version": "1.0.0",
        "platform_contract": "skill-platform-v1",
        "status": "deprecated",
        "deprecation": {
            "deprecated_since": "2026-01-01",
            "replacement": "new-skill",
            "remove_after": "2026-04-01",
            "migration_note": "Use new-skill.",
            "aliases": ["legacy-skill"],
        },
    }

    assert validate_skill_frontmatter_fields("legacy-skill", frontmatter) == []
    assert validate_deprecation_item(
        frontmatter,
        "legacy-skill/SKILL.md",
        required_fields=REQUIRED,
        compatibility_window_days=90,
    ) == []


def test_skill_frontmatter_rejects_malformed_lifecycle_field_shapes() -> None:
    frontmatter = {
        "name": "legacy-skill",
        "description": "Legacy skill.",
        "skill_version": "1.0.0",
        "deprecated": "yes",
        "deprecation": [],
    }

    errors = validate_skill_frontmatter_fields("legacy-skill", frontmatter)
    assert any("deprecated must be a boolean" in error for error in errors)
    assert any("deprecation must be a mapping" in error for error in errors)
