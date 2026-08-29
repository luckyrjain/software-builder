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
    from scripts.registry.composition_contracts import CompositionContract
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
        "child": CompositionContract([], [], "read-only", {}, {}),
        "parent": CompositionContract([], [], "repository-write", {}, {}),
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


def test_invoke_schema_matching_detects_missing_fields() -> None:
    from scripts.registry.composition_contracts import validate_composition_contracts
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
        hosts=Hosts(cursor=HostCursor("rule"), claude=HostClaude(), kiro=HostKiro("manual")),
        install=InstallSpec(requires=[]),
        lint=LintSpec(180, "child"),
        composition=CompositionSpec(invokes=[]),
    )
    parent = SkillEntry(
        path="parent",
        category="testing",
        invocation="ambient",
        hosts=Hosts(cursor=HostCursor("rule"), claude=HostClaude(), kiro=HostKiro("manual")),
        install=InstallSpec(requires=[]),
        lint=LintSpec(180, "parent"),
        composition=CompositionSpec(invokes=["child"]),
    )
    registry = Registry(schema_version=1, skills={"child": child, "parent": parent})

    contracts_yaml = ROOT / "scripts/tests/fixtures/composition_schema_matching.yaml"
    errors = validate_composition_contracts(registry, contracts_path=contracts_yaml)
    assert any("consume_fields.mr_review_report" in error for error in errors)


def test_aggregate_schema_matching_passes_for_weekly_digest_contracts() -> None:
    from scripts.registry.composition_contracts import validate_composition_contracts
    from scripts.registry.schema import parse_registry

    registry = parse_registry(ROOT / "skills.yaml")
    errors = validate_composition_contracts(registry)
    assert errors == [], "\n".join(errors)


def test_validate_schema_matching_reports_missing_fields_with_source_label() -> None:
    """Direct unit test of the shared helper, isolated from both invoke/aggregate callers."""
    from scripts.registry.composition_contracts import CompositionContract, _validate_schema_matching

    parent = CompositionContract([], ["artifact"], "read-only", {}, {"artifact": ["a", "b"]})
    child = CompositionContract(["artifact"], [], "read-only", {"artifact": ["a"]}, {})

    errors = _validate_schema_matching(
        "parent",
        ["child"],
        "some-label",
        parent,
        {"child": child},
        artifact_schemas={},
    )

    assert len(errors) == 1
    assert "some-label" in errors[0]
    assert "'b'" in errors[0]
    assert "'a'" not in errors[0].split("expose")[0]  # only the missing field is reported, not the covered one


def test_validate_schema_matching_passes_when_fields_fully_covered() -> None:
    from scripts.registry.composition_contracts import CompositionContract, _validate_schema_matching

    parent = CompositionContract([], ["artifact"], "read-only", {}, {"artifact": ["a", "b"]})
    child = CompositionContract(["artifact"], [], "read-only", {"artifact": ["a", "b"]}, {})

    errors = _validate_schema_matching(
        "parent",
        ["child"],
        "some-label",
        parent,
        {"child": child},
        artifact_schemas={},
    )

    assert errors == []


def test_validate_schema_matching_skips_silently_when_no_producer_found() -> None:
    """No producer for the artifact is not this function's job to flag — the aggregate
    caller has its own explicit 'no producer' pre-check for that; invoke has none by
    design (see the comment in validate_composition_contracts())."""
    from scripts.registry.composition_contracts import CompositionContract, _validate_schema_matching

    parent = CompositionContract([], ["artifact"], "read-only", {}, {"artifact": ["a"]})

    errors = _validate_schema_matching(
        "parent",
        [],  # no producer ids at all
        "some-label",
        parent,
        contracts={},
        artifact_schemas={},
    )

    assert errors == []
