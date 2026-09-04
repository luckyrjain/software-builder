"""Tests for mcp-error-handling.md §4's generated degraded-behaviour table."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.registry.generate_degraded_behavior_doc import (
    capability_providers,
    doc_path,
    render_degraded_behavior_block,
    render_degraded_behavior_doc,
)

ROOT = Path(__file__).resolve().parents[2]


def _degraded_skills() -> dict:
    import yaml

    return yaml.safe_load(
        (ROOT / "scripts" / "registry" / "degraded_behavior.yaml").read_text(encoding="utf-8")
    )["skills"]


def test_table_covers_every_skill_in_the_policy() -> None:
    """The point of generating §4: it stops being an illustrative subset of 5 skills."""
    block = render_degraded_behavior_block(ROOT)
    for skill_id in _degraded_skills():
        assert f"| `{skill_id}` |" in block, skill_id


def test_branded_capabilities_render_in_provider_terms() -> None:
    block = render_degraded_behavior_block(ROOT)
    assert "**Kubernetes MCP ❌** `kubernetes.metrics.history`" in block
    assert "**GitLab ❌** `gitlab.get_merge_request`" in block


def test_unbranded_capabilities_render_as_ids_without_a_provider() -> None:
    """`host.*` ids name no vendor, so inventing a provider label for them would be a lie."""
    block = render_degraded_behavior_block(ROOT)
    assert "| `host.report.write` |" in block
    assert "host.report.write ❌" not in block


def test_skill_invoke_ids_are_not_treated_as_providers() -> None:
    families = {
        "release.production_readiness.conditional_invoke": {
            "resolves": ["production-readiness-review.conditional_invoke"],
        },
        "scm.pull_request.read": {"resolves": ["gitlab.get_merge_request"]},
    }
    branded = capability_providers(families, {"production-readiness-review"})
    assert branded == {"gitlab.get_merge_request": "scm.pull_request.read"}


def test_rendered_doc_is_stable_and_keeps_the_surrounding_prose() -> None:
    rendered = render_degraded_behavior_doc(ROOT)
    assert rendered == doc_path(ROOT).read_text(encoding="utf-8"), "run make generate"
    assert "## 5. Confidence impact" in rendered
    assert "## 3. Retry policy" in rendered


def test_missing_marker_block_fails_loudly(tmp_path: Path) -> None:
    """A doc that lost its markers must fail the generate rather than silently skip §4."""
    registry_dir = tmp_path / "scripts" / "registry"
    registry_dir.mkdir(parents=True)
    (registry_dir / "degraded_behavior.yaml").write_text(
        "skills:\n  solo:\n    missing_capability: host.report.write\n"
        "    available_capabilities: []\n    behavior: BLOCKED\n",
        encoding="utf-8",
    )
    (registry_dir / "capability_families.yaml").write_text("families: {}\n", encoding="utf-8")
    target = doc_path(tmp_path)
    target.parent.mkdir(parents=True)
    target.write_text("# no markers here\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing marker block"):
        render_degraded_behavior_doc(tmp_path)
