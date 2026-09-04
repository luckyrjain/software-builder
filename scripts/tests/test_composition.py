"""Tests for composition graph validation."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_composition_graph_valid_on_real_repo() -> None:
    from scripts.registry.composition import validate_composition_graph
    from scripts.registry.schema import parse_registry

    errors = validate_composition_graph(parse_registry(ROOT / "skills.yaml"))
    assert errors == [], errors


def test_composition_detects_cycle(tmp_path: Path) -> None:
    from scripts.registry.composition import validate_composition_graph
    from scripts.registry.models import (
        CompositionSpec,
        HostDiscoverySpec,
        InstallSpec,
        LintSpec,
        Registry,
        SkillEntry,
    )

    minimal_hosts = {
        "cursor": HostDiscoverySpec(discovery="rule"),
        "claude": HostDiscoverySpec(install=True),
        "kiro": HostDiscoverySpec(discovery="manual"),
    }
    entry = SkillEntry(
        path="a",
        category="testing",
        invocation="ambient",
        hosts=minimal_hosts,
        install=InstallSpec(requires=[]),
        lint=LintSpec(skill_md_max_lines=180, target="a"),
        composition=CompositionSpec(invokes=["b"]),
    )
    entry_b = SkillEntry(
        path="b",
        category="testing",
        invocation="ambient",
        hosts=minimal_hosts,
        install=InstallSpec(requires=[]),
        lint=LintSpec(skill_md_max_lines=180, target="b"),
        composition=CompositionSpec(invokes=["a"]),
    )
    registry = Registry(schema_version=1, skills={"a": entry, "b": entry_b})
    errors = validate_composition_graph(registry)
    assert any("cycle detected" in error for error in errors)
