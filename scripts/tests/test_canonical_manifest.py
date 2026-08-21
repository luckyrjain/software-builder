from pathlib import Path

from scripts.registry.canonical_manifest import (
    load_canonical_manifest,
    render_legacy_projection,
    validate_canonical_manifest,
)
from scripts.registry.frontmatter import load_skill_frontmatter


ROOT = Path(__file__).resolve().parents[2]


def test_canonical_manifest_has_contracts_and_full_skill_metadata():
    manifest = load_canonical_manifest(ROOT)

    assert manifest["schema_version"] == 1
    assert {"platform", "composition_runtime", "composition"} <= set(
        manifest["contracts"]
    )

    required = {
        "version",
        "type",
        "permissions",
        "supported_hosts",
        "entrypoint",
        "output_contract",
    }
    for skill in manifest["skills"].values():
        assert required <= set(skill)

    assert manifest["skills"]["domain-comprehension"]["type"] == "orchestrator"
    assert manifest["skills"]["weekly-squad-digest"]["type"] == "trigger"


def test_legacy_projections_are_derived_from_canonical():
    assert not validate_canonical_manifest(ROOT)

    assert (
        (ROOT / "scripts/registry/platform_contracts.yaml").read_text()
        == render_legacy_projection(ROOT, "platform")
    )
    assert (
        (ROOT / "scripts/registry/composition_runtime.yaml").read_text()
        == render_legacy_projection(ROOT, "composition_runtime")
    )
    assert (
        (ROOT / "scripts/registry/composition_contracts.yaml").read_text()
        == render_legacy_projection(ROOT, "composition")
    )


def test_skill_frontmatter_contains_discovery_metadata_only():
    for skill_id in load_canonical_manifest(ROOT)["skills"]:
        frontmatter = load_skill_frontmatter(ROOT / skill_id / "SKILL.md")
        assert "skill_version" not in frontmatter
        assert "platform_contract" not in frontmatter
