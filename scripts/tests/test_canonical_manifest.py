import shutil
from pathlib import Path

import yaml

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


def test_generate_collects_all_legacy_projections_from_canonical():
    from scripts.registry.cli import _collect_outputs

    outputs = _collect_outputs(ROOT)
    assert outputs[ROOT / "scripts/registry/platform_contracts.yaml"] == render_legacy_projection(ROOT, "platform")
    assert outputs[ROOT / "scripts/registry/composition_runtime.yaml"] == render_legacy_projection(ROOT, "composition_runtime")
    assert outputs[ROOT / "scripts/registry/composition_contracts.yaml"] == render_legacy_projection(ROOT, "composition")


def _copy_manifest_fixture(tmp_path: Path) -> Path:
    shutil.copy2(ROOT / "skills.yaml", tmp_path / "skills.yaml")
    for skill_id in load_canonical_manifest(ROOT)["skills"]:
        skill_dir = tmp_path / skill_id
        skill_dir.mkdir()
        shutil.copy2(ROOT / skill_id / "SKILL.md", skill_dir / "SKILL.md")
    return tmp_path


def test_canonical_manifest_rejects_skill_metadata_drift(tmp_path: Path):
    root = _copy_manifest_fixture(tmp_path)
    manifest = yaml.safe_load((root / "skills.yaml").read_text())
    manifest["skills"]["pr-review"]["authority"] = "read-only"
    (root / "skills.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))

    errors = validate_canonical_manifest(root)

    assert any("pr-review" in error and "authority" in error for error in errors)


def test_skill_frontmatter_contains_discovery_metadata_only():
    for skill_id in load_canonical_manifest(ROOT)["skills"]:
        frontmatter = load_skill_frontmatter(ROOT / skill_id / "SKILL.md")
        assert "skill_version" not in frontmatter
        assert "platform_contract" not in frontmatter
