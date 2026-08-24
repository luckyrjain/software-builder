"""Tests for skills.yaml risk_class metadata."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_all_skills_declare_risk_class() -> None:
    from scripts.registry.schema import parse_registry

    registry = parse_registry(ROOT / "skills.yaml")
    for skill_id, entry in registry.skills.items():
        assert entry.risk_class, f"{skill_id} missing risk_class"


def test_automation_only_skills_are_unattended() -> None:
    from scripts.registry.crosscheck import validate_registry

    errors = validate_registry(ROOT)
    assert errors == [], "\n".join(errors)
