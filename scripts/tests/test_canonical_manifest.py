import shutil
from pathlib import Path

import yaml

from scripts.registry.canonical_manifest import (
    is_semver,
    load_canonical_manifest,
    render_legacy_projection,
    validate_canonical_manifest,
)
from scripts.registry.frontmatter import load_skill_frontmatter


ROOT = Path(__file__).resolve().parents[2]


def test_load_canonical_manifest_resolves_extends_profile(tmp_path: Path):
    (tmp_path / "skills.yaml").write_text(
        """
schema_version: 1
manifest_kind: canonical
contracts: {}
profiles:
  read-only-leaf-review:
    authority: read-only
    entrypoint: SKILL.md
skills:
  squad-map:
    path: squad-map
    extends: read-only-leaf-review
    category: architecture
""",
        encoding="utf-8",
    )

    manifest = load_canonical_manifest(tmp_path)

    assert "profiles" not in manifest
    assert manifest["skills"]["squad-map"]["authority"] == "read-only"
    assert manifest["skills"]["squad-map"]["entrypoint"] == "SKILL.md"
    assert manifest["skills"]["squad-map"]["category"] == "architecture"


def test_semver_rejects_empty_prerelease_and_build_identifiers():
    assert not is_semver("1.2.3-")
    assert not is_semver("1.2.3+")
    assert not is_semver("1.2.3-é")
    assert not is_semver("١.٢.٣")


def test_canonical_manifest_has_contracts_and_full_skill_metadata():
    manifest = load_canonical_manifest(ROOT)

    assert manifest["schema_version"] == 1
    assert {"platform", "composition_runtime", "composition"} <= set(
        manifest["contracts"]
    )

    required = {
        "version",
        "type",
        "category",
        "invocation",
        "authority",
        "permissions",
        "supported_hosts",
        "entrypoint",
        "output_contract",
        "dependencies",
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
    # skills.yaml's own skill entries declare every host in the real agent-hosts.yaml (Candidate
    # 3: the host set is data-driven) -- without this copy, schema.py falls back to its 3-host
    # default and every skill's real 4-host declaration looks like an unknown host, drowning out
    # whatever specific drift error each test below means to exercise.
    shutil.copy2(ROOT / "agent-hosts.yaml", tmp_path / "agent-hosts.yaml")
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


def test_canonical_manifest_requires_versioned_artifact_runtime_contract(tmp_path: Path):
    root = _copy_manifest_fixture(tmp_path)
    manifest = yaml.safe_load((root / "skills.yaml").read_text())
    del manifest["contracts"]["platform"]["artifact_runtime"]
    (root / "skills.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))

    errors = validate_canonical_manifest(root)

    assert any("artifact_runtime" in error for error in errors)


def test_canonical_manifest_rejects_output_and_host_projection_drift(tmp_path: Path):
    root = _copy_manifest_fixture(tmp_path)
    manifest = yaml.safe_load((root / "skills.yaml").read_text())
    manifest["skills"]["pr-review"]["output_contract"]["produces"] = ["rca_report"]
    manifest["skills"]["pr-review"]["supported_hosts"] = ["cursor"]
    (root / "skills.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))

    errors = validate_canonical_manifest(root)

    assert any("pr-review" in error and "output contract artifact" in error for error in errors)
    assert any("pr-review" in error and "supported host" in error for error in errors)


def test_canonical_manifest_normalizes_quoted_schema_version(tmp_path: Path):
    root = _copy_manifest_fixture(tmp_path)
    manifest = yaml.safe_load((root / "skills.yaml").read_text())
    manifest["schema_version"] = "1"
    (root / "skills.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))

    assert load_canonical_manifest(root)["schema_version"] == 1


def test_skill_frontmatter_contains_discovery_metadata_only():
    for skill_id in load_canonical_manifest(ROOT)["skills"]:
        frontmatter = load_skill_frontmatter(ROOT / skill_id / "SKILL.md")
        assert "skill_version" not in frontmatter
        assert "platform_contract" not in frontmatter


def test_projections_carry_the_generated_marker_and_stay_loadable():
    """The three projections are machine-written; marking them says so to a maintainer who
    opens one, and the loader must still read a marked file (comments are not data)."""
    from scripts.registry.canonical_manifest import (
        GENERATED_MARKER,
        LEGACY_PROJECTION_FILENAMES,
        legacy_projection_path,
        load_contract_section,
    )

    for section in LEGACY_PROJECTION_FILENAMES:
        text = legacy_projection_path(ROOT, section).read_text(encoding="utf-8")
        assert text.startswith(GENERATED_MARKER + "\n"), section

    # Reading a marked projection must produce the same document as the canonical section.
    for section in LEGACY_PROJECTION_FILENAMES:
        projection = yaml.safe_load(legacy_projection_path(ROOT, section).read_text(encoding="utf-8"))
        assert projection == load_contract_section(ROOT, section), section


def test_render_legacy_projection_is_idempotent():
    """generate --check compares rendered text against the file on disk, so re-rendering an
    already-marked projection must not stack a second marker."""
    from scripts.registry.canonical_manifest import LEGACY_PROJECTION_FILENAMES, render_legacy_projection

    for section in LEGACY_PROJECTION_FILENAMES:
        first = render_legacy_projection(ROOT, section)
        assert first == render_legacy_projection(ROOT, section)
        assert first.count("# GENERATED from skills.yaml contracts") == 1
