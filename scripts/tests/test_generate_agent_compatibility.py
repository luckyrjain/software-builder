"""Tests for generated agent-compatibility documentation (Candidate 11)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def registries():
    from scripts.registry.generate_agent_compatibility import load_host_registry_and_registry

    return load_host_registry_and_registry(ROOT)


def test_render_agent_compatibility_doc_states_every_host(registries) -> None:
    from scripts.registry.generate_agent_compatibility import render_agent_compatibility_doc

    host_registry, registry = registries
    doc = render_agent_compatibility_doc(host_registry, registry)

    assert doc.startswith("# Agent compatibility")
    for host_id in host_registry.hosts:
        assert f"### {host_id}" in doc


def test_render_agent_compatibility_doc_never_states_a_percentage(registries) -> None:
    """Spec Section 43: no invented compatibility percentages."""
    from scripts.registry.generate_agent_compatibility import render_agent_compatibility_doc

    host_registry, registry = registries
    doc = render_agent_compatibility_doc(host_registry, registry)

    assert "%" not in doc


def test_render_agent_compatibility_doc_includes_host_skill_matrix(registries) -> None:
    from scripts.registry.compatibility_resolver import resolve_matrix
    from scripts.registry.generate_agent_compatibility import render_agent_compatibility_doc

    host_registry, registry = registries
    doc = render_agent_compatibility_doc(host_registry, registry)

    matrix = resolve_matrix(host_registry, registry)
    assert len(matrix) > 0
    # Spot-check one real (host, skill) row landed in the rendered table.
    sample = matrix[0]
    assert f"| {sample.host_id} | {sample.skill_id} | {sample.status} |" in doc


def test_render_agent_compatibility_doc_reports_no_evidence_honestly(registries) -> None:
    """agent-hosts.yaml's checked-in hosts currently have zero evidence entries -- the doc must
    say so plainly rather than omitting the field or inventing content."""
    from scripts.registry.generate_agent_compatibility import render_agent_compatibility_doc

    host_registry, registry = registries
    doc = render_agent_compatibility_doc(host_registry, registry)

    assert "**Evidence:** none recorded" in doc


def test_render_readme_section_omits_per_skill_detail(registries) -> None:
    """Spec Section 45: README gets only the concise support table, not per-skill/evidence
    detail -- that's what makes it "concise" versus the full doc."""
    from scripts.registry.generate_agent_compatibility import (
        render_readme_agent_compatibility_section,
    )

    host_registry, _registry = registries
    section = render_readme_agent_compatibility_section(host_registry)

    assert "| Host | Verification | Maintainer support |" in section
    assert "docs/agent-compatibility.md" in section
    assert "Capabilities" not in section
    assert "Evidence" not in section


def test_render_readme_section_lists_every_host(registries) -> None:
    from scripts.registry.generate_agent_compatibility import (
        render_readme_agent_compatibility_section,
    )

    host_registry, _registry = registries
    section = render_readme_agent_compatibility_section(host_registry)

    for host_id in host_registry.hosts:
        assert host_id in section


def test_update_readme_agent_compatibility_section_replaces_marker_block(registries) -> None:
    from scripts.registry.generate_agent_compatibility import (
        README_AGENT_COMPATIBILITY_END,
        README_AGENT_COMPATIBILITY_START,
        update_readme_agent_compatibility_section,
    )

    host_registry, _registry = registries
    readme = f"# Title\n\n{README_AGENT_COMPATIBILITY_START}old content{README_AGENT_COMPATIBILITY_END}\n\nmore"

    updated = update_readme_agent_compatibility_section(readme, host_registry)

    assert "old content" not in updated
    assert README_AGENT_COMPATIBILITY_START in updated
    assert README_AGENT_COMPATIBILITY_END in updated
    assert "more" in updated


def test_update_readme_agent_compatibility_section_raises_without_marker(registries) -> None:
    from scripts.registry.generate_agent_compatibility import (
        update_readme_agent_compatibility_section,
    )

    host_registry, _registry = registries
    with pytest.raises(ValueError, match="missing marker block"):
        update_readme_agent_compatibility_section("# Title\n\nno markers here", host_registry)


def test_generate_check_covers_docs_agent_compatibility_and_readme() -> None:
    """End-to-end: `generate --check` against the real repo must be clean, and must actually
    catch drift when the generated doc is hand-edited -- not just report success unconditionally."""
    from scripts.registry.cli import _check_outputs, _collect_outputs

    outputs = _collect_outputs(ROOT)
    doc_path = ROOT / "docs" / "agent-compatibility.md"
    assert doc_path in outputs
    assert outputs[doc_path] == doc_path.read_text(encoding="utf-8")

    tampered = dict(outputs)
    tampered[doc_path] = outputs[doc_path] + "\nmanual edit\n"
    errors = _check_outputs(ROOT, tampered)
    assert any("docs/agent-compatibility.md" in error for error in errors)


def test_escape_table_cell_shared_between_modules() -> None:
    from scripts.registry.generate_agent_compatibility import _cell as agent_cell
    from scripts.registry.generate_compatibility import _cell as compat_cell
    from scripts.registry.generate_docs import escape_table_cell

    assert agent_cell is escape_table_cell
    assert compat_cell is escape_table_cell
