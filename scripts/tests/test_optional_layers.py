"""Tests for scripts/registry/cli.py's detect_optional_layers/OptionalLayers."""

from __future__ import annotations

from pathlib import Path

from scripts.registry.canonical_manifest import legacy_projection_path
from scripts.registry.cli import (
    _capability_catalog_path,
    _release_contract_path,
    detect_optional_layers,
)


def _write_minimal_skills_yaml(tmp_path: Path) -> None:
    (tmp_path / "skills.yaml").write_text(
        "schema_version: 1\nskills:\n  solo:\n    path: solo\n",
        encoding="utf-8",
    )


def test_all_layers_inactive_on_a_bare_minimal_repo(tmp_path: Path) -> None:
    _write_minimal_skills_yaml(tmp_path)

    layers = detect_optional_layers(tmp_path)

    assert layers.host_contracts is None
    assert layers.capability_catalog is None
    assert layers.capability_families is None
    assert layers.release_contract is None
    assert layers.p1_layer_active is False
    # No canonical shape and no standalone projection: the composition contract document
    # falls all the way back to skills.yaml itself (which is what keeps minimal fixtures
    # readable), while composition_runtime has no document at all and stays inactive.
    assert layers.composition_contracts == tmp_path / "skills.yaml"
    assert layers.composition_runtime is None


def test_capability_catalog_activates_independently_of_capability_families(tmp_path: Path) -> None:
    _write_minimal_skills_yaml(tmp_path)
    catalog_path = _capability_catalog_path(tmp_path)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text("capabilities: {}\n", encoding="utf-8")

    layers = detect_optional_layers(tmp_path)

    assert layers.capability_catalog == catalog_path
    assert layers.capability_families is None


def test_p1_layer_active_when_any_one_of_its_five_files_exists(tmp_path: Path) -> None:
    _write_minimal_skills_yaml(tmp_path)
    host_contracts = tmp_path / "scripts" / "registry" / "host_contracts.yaml"
    host_contracts.parent.mkdir(parents=True, exist_ok=True)
    host_contracts.write_text("hosts: {}\n", encoding="utf-8")

    layers = detect_optional_layers(tmp_path)

    assert layers.p1_layer_active is True
    # p1_layer_active is a single bool covering all 5 files (any-of), not per-file paths --
    # that matches how _validate_for_generate/_validate_all actually consume it.
    assert layers.host_contracts == host_contracts


def test_release_contract_active_flag(tmp_path: Path) -> None:
    _write_minimal_skills_yaml(tmp_path)
    release_contract = _release_contract_path(tmp_path)
    release_contract.parent.mkdir(parents=True, exist_ok=True)
    release_contract.write_text("version: 1\n", encoding="utf-8")

    layers = detect_optional_layers(tmp_path)

    assert layers.release_contract == release_contract


def test_composition_runtime_matches_the_shared_section_resolution(tmp_path: Path) -> None:
    """detect_optional_layers must agree with canonical_manifest's own canonical-vs-legacy
    resolution -- the same one every contract-section reader takes -- not re-derive it a
    second, possibly-inconsistent way."""
    _write_minimal_skills_yaml(tmp_path)
    legacy_path = legacy_projection_path(tmp_path, "composition_runtime")
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text("schema_version: 1\n", encoding="utf-8")

    layers = detect_optional_layers(tmp_path)

    assert layers.composition_runtime == legacy_path


def test_composition_runtime_resolves_through_canonical_shape_with_skills_d_fragments(
    tmp_path: Path,
) -> None:
    """Coverage gap closed after the full-system review: no prior test exercised
    scripts/registry/skills.d/ fragments and detect_optional_layers together, even
    though detect_optional_layers's composition_runtime field depends on
    canonical_manifest's shared canonical-shape detection, which reads through
    schema.py's fragment-aware, cached load_registry_raw instead of a raw file read.
    A canonical-shape skills.yaml with an EMPTY inline `skills:` mapping, whose only
    real skill comes from a skills.d/ fragment, must still resolve composition_runtime
    to skills.yaml itself (canonical shape), not fall back to the legacy standalone
    composition_runtime.yaml path -- proving the fragment merge and the shape
    detection agree with each other through the shared cache.
    """
    from scripts.registry.manifest_merge import skills_fragments_dir

    (tmp_path / "skills.yaml").write_text(
        "schema_version: 1\nmanifest_kind: canonical\ncontracts: {}\nskills: {}\n",
        encoding="utf-8",
    )
    fragments_dir = skills_fragments_dir(tmp_path)
    fragments_dir.mkdir(parents=True)
    (fragments_dir / "fragment-skill.yaml").write_text(
        "fragment-skill:\n  path: fragment-skill\n", encoding="utf-8"
    )

    layers = detect_optional_layers(tmp_path)

    assert layers.composition_runtime == tmp_path / "skills.yaml"
    assert layers.composition_contracts == tmp_path / "skills.yaml"


def test_real_repo_has_every_optional_layer_active() -> None:
    """The real software-builder repo has all of these files -- confirms the dataclass
    reflects reality, not just synthetic fixtures."""
    root = Path(__file__).resolve().parents[2]

    layers = detect_optional_layers(root)

    assert layers.host_contracts is not None
    assert layers.capability_catalog is not None
    assert layers.capability_families is not None
    assert layers.composition_runtime is not None
    assert layers.release_contract is not None
    assert layers.composition_contracts is not None
    assert layers.p1_layer_active is True


def test_composition_contracts_is_the_document_that_will_be_read(tmp_path: Path) -> None:
    """The field names the composition contract's source, not skills.yaml's mere existence
    -- so a repository carrying the standalone projection points at the projection."""
    _write_minimal_skills_yaml(tmp_path)
    projection = legacy_projection_path(tmp_path, "composition")
    projection.parent.mkdir(parents=True, exist_ok=True)
    projection.write_text("artifact_types: []\n", encoding="utf-8")

    layers = detect_optional_layers(tmp_path)

    assert layers.composition_contracts == projection


def test_every_active_layer_field_names_a_file_that_exists() -> None:
    """A `Path` field means "active, at that path" -- it must never be a path that is not
    there, which is what a caller handing it to a loader relies on."""
    root = Path(__file__).resolve().parents[2]

    layers = detect_optional_layers(root)

    for field in (
        "host_contracts",
        "capability_catalog",
        "capability_families",
        "composition_runtime",
        "release_contract",
        "composition_contracts",
    ):
        value = getattr(layers, field)
        assert value is None or value.is_file(), field
