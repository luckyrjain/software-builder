"""Tests for scripts/registry/cli.py's resolve_optional_layers/OptionalLayers."""

from __future__ import annotations

from pathlib import Path

from scripts.registry.cli import (
    _capability_catalog_path,
    _composition_runtime_path,
    _release_contract_path,
    resolve_optional_layers,
)


def _write_minimal_skills_yaml(tmp_path: Path) -> None:
    (tmp_path / "skills.yaml").write_text(
        "schema_version: 1\nskills:\n  solo:\n    path: solo\n",
        encoding="utf-8",
    )


def test_all_layers_inactive_on_a_bare_minimal_repo(tmp_path: Path) -> None:
    _write_minimal_skills_yaml(tmp_path)

    layers = resolve_optional_layers(tmp_path)

    assert layers.host_contracts is None
    assert layers.capability_catalog is None
    assert layers.capability_families is None
    assert layers.release_contract is None
    assert layers.p1_layer_active is False
    # skills.yaml itself always exists in this fixture, so composition_contracts is active.
    assert layers.composition_contracts == tmp_path / "skills.yaml"
    # No canonical shape -> composition_runtime falls back to the legacy standalone file,
    # which doesn't exist in this minimal fixture either.
    assert layers.composition_runtime is None


def test_capability_catalog_activates_independently_of_capability_families(tmp_path: Path) -> None:
    _write_minimal_skills_yaml(tmp_path)
    catalog_path = _capability_catalog_path(tmp_path)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text("capabilities: {}\n", encoding="utf-8")

    layers = resolve_optional_layers(tmp_path)

    assert layers.capability_catalog == catalog_path
    assert layers.capability_families is None


def test_p1_layer_active_when_any_one_of_its_five_files_exists(tmp_path: Path) -> None:
    _write_minimal_skills_yaml(tmp_path)
    host_contracts = tmp_path / "scripts" / "registry" / "host_contracts.yaml"
    host_contracts.parent.mkdir(parents=True, exist_ok=True)
    host_contracts.write_text("hosts: {}\n", encoding="utf-8")

    layers = resolve_optional_layers(tmp_path)

    assert layers.p1_layer_active is True
    # p1_layer_active is a single bool covering all 5 files (any-of), not per-file paths --
    # that matches how _validate_for_generate/_validate_all actually consume it.
    assert layers.host_contracts == host_contracts


def test_release_contract_active_flag(tmp_path: Path) -> None:
    _write_minimal_skills_yaml(tmp_path)
    release_contract = _release_contract_path(tmp_path)
    release_contract.parent.mkdir(parents=True, exist_ok=True)
    release_contract.write_text("version: 1\n", encoding="utf-8")

    layers = resolve_optional_layers(tmp_path)

    assert layers.release_contract == release_contract


def test_composition_runtime_matches_the_standalone_helper(tmp_path: Path) -> None:
    """resolve_optional_layers must agree with _composition_runtime_path's own
    canonical-vs-legacy resolution, not re-derive it a second, possibly-inconsistent way."""
    _write_minimal_skills_yaml(tmp_path)
    legacy_path = _composition_runtime_path(tmp_path)
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text("schema_version: 1\n", encoding="utf-8")

    layers = resolve_optional_layers(tmp_path)

    assert layers.composition_runtime == legacy_path


def test_real_repo_has_every_optional_layer_active() -> None:
    """The real software-builder repo has all of these files -- confirms the dataclass
    reflects reality, not just synthetic fixtures."""
    root = Path(__file__).resolve().parents[2]

    layers = resolve_optional_layers(root)

    assert layers.host_contracts is not None
    assert layers.capability_catalog is not None
    assert layers.capability_families is not None
    assert layers.composition_runtime is not None
    assert layers.release_contract is not None
    assert layers.composition_contracts is not None
    assert layers.p1_layer_active is True
