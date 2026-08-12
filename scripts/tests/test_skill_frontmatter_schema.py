"""Tests for SKILL.md frontmatter schema validation."""
from __future__ import annotations

from scripts.registry.skill_frontmatter_schema import (
    automation_only_guard_errors,
    validate_skill_frontmatter_fields,
)


def test_unknown_key_rejected():
    errors = validate_skill_frontmatter_fields(
        "pr-review",
        {"name": "pr-review", "description": "ok", "extra": True},
    )
    assert any("unknown" in e for e in errors)


def test_skill_version_accepts_float():
    assert not validate_skill_frontmatter_fields(
        "api-test-creator",
        {"name": "api-test-creator", "description": "ok", "skill_version": 1.0},
    )


def test_disable_model_invocation_must_be_bool():
    errors = validate_skill_frontmatter_fields(
        "pr-gatekeeper",
        {"name": "pr-gatekeeper", "description": "ok", "disable-model-invocation": "true"},
    )
    assert any("boolean" in e for e in errors)


def test_automation_only_guard_allows_consistent_pairs():
    assert automation_only_guard_errors("automation-only", {"disable-model-invocation": True}) == []
    assert automation_only_guard_errors("ambient", {}) == []


def test_automation_only_guard_flags_automation_only_missing_disable():
    errors = automation_only_guard_errors("automation-only", {})
    assert errors == ["disable-model-invocation=False but invocation='automation-only'"]


def test_automation_only_guard_flags_disable_without_automation_only():
    errors = automation_only_guard_errors("ambient", {"disable-model-invocation": True})
    assert errors == ["disable-model-invocation=True but invocation='ambient'"]
