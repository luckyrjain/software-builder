"""Tests for composition contract validation."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_composition_contracts_cover_all_skills() -> None:
    from scripts.registry.composition_contracts import validate_catalog_covers_registry
    from scripts.registry.schema import parse_registry

    registry = parse_registry(ROOT / "skills.yaml")
    assert validate_catalog_covers_registry(registry) == []


def test_composition_contracts_validate_on_real_repo() -> None:
    from scripts.registry.composition import validate_composition_file

    errors = validate_composition_file(ROOT)
    assert errors == [], "\n".join(errors)


def test_write_authority_escalation_detected() -> None:
    from scripts.registry.composition_contracts import CompositionContract, validate_composition_contracts
    from scripts.registry.models import (
        CompositionSpec,
        HostClaude,
        HostCursor,
        HostKiro,
        Hosts,
        InstallSpec,
        LintSpec,
        Registry,
        SkillEntry,
    )

    child = SkillEntry(
        path="child",
        category="testing",
        invocation="ambient",
        hosts=Hosts(
            cursor=HostCursor("rule"),
            claude=HostClaude(),
            kiro=HostKiro("manual"),
        ),
        install=InstallSpec(requires=[]),
        lint=LintSpec(180, "child"),
        composition=CompositionSpec(invokes=[]),
    )
    parent = SkillEntry(
        path="parent",
        category="testing",
        invocation="ambient",
        hosts=Hosts(
            cursor=HostCursor("rule"),
            claude=HostClaude(),
            kiro=HostKiro("manual"),
        ),
        install=InstallSpec(requires=[]),
        lint=LintSpec(180, "parent"),
        composition=CompositionSpec(invokes=["child"]),
    )
    registry = Registry(schema_version=1, skills={"child": child, "parent": parent})

    contracts = {
        "child": CompositionContract([], [], "read-only"),
        "parent": CompositionContract([], [], "repository-write"),
    }
    authority_levels = {"read-only": 0, "comment": 1, "repository-write": 2, "automation-unattended": 3}

    errors: list[str] = []

    for skill_id, entry in registry.skills.items():
        contract = contracts[skill_id]
        if entry.composition.invokes:
            max_child = max(authority_levels[contracts[c].write_authority] for c in entry.composition.invokes)
            if authority_levels[contract.write_authority] > max_child:
                errors.append(skill_id)

    assert errors == ["parent"]
