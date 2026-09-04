"""Tests for the generated capability catalogue and the registry's capability blocks.

`capability_catalog.yaml` is a projection of the `capabilities:` block of each
`scripts/registry/skills.d/*.yaml` fragment (see `manifest_merge.SIDE_FILE_PROJECTIONS`),
so the tests that used to cover writing the catalogue back into skills.yaml are gone with
that write direction. What is left is the reading half, plus the two invariants the
projection has to keep: it covers every registered skill, and it says exactly what the
fragments say.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_capability_catalog_covers_all_registry_skills() -> None:
    """Guards the one gap the projection could open: `load_fragment_skills` reads
    fragments *before* `extends:` profile resolution, so a skill that inherited its
    capabilities from a profile would be silently absent from the catalogue.
    """
    from scripts.registry.backfill_capabilities import load_catalog
    from scripts.registry.schema import parse_registry

    catalog = load_catalog()
    registry = parse_registry(ROOT / "skills.yaml")
    assert set(catalog.keys()) == set(registry.skills.keys())


def test_capability_catalog_matches_the_registry_capabilities_blocks() -> None:
    from scripts.registry.backfill_capabilities import load_catalog
    from scripts.registry.schema import load_registry_raw

    catalog = load_catalog()
    skills = load_registry_raw(ROOT / "skills.yaml")["skills"]
    for skill_id, catalog_entry in catalog.items():
        assert catalog_entry == skills[skill_id]["capabilities"], skill_id


def test_all_skills_have_capabilities_block() -> None:
    from scripts.registry.backfill_capabilities import validate_capabilities_present

    assert validate_capabilities_present(ROOT / "skills.yaml") == []


def test_capabilities_check_passes_on_repository() -> None:
    from scripts.registry.backfill_capabilities import cmd_check_capabilities

    assert cmd_check_capabilities(skills_path=ROOT / "skills.yaml") == 0


def test_capabilities_check_reports_a_missing_block(tmp_path: Path) -> None:
    from scripts.registry.backfill_capabilities import cmd_check_capabilities

    skills_path = tmp_path / "skills.yaml"
    skills_path.write_text(
        "schema_version: 1\nskills:\n  solo:\n    path: solo\n",
        encoding="utf-8",
    )
    assert cmd_check_capabilities(skills_path=skills_path) == 1


def test_validate_capabilities_present_rejects_stray_top_level_keys(tmp_path: Path) -> None:
    from scripts.registry.backfill_capabilities import validate_capabilities_present

    skills_path = tmp_path / "skills.yaml"
    skills_path.write_text(
        "schema_version: 1\n"
        "skills:\n"
        "  solo:\n"
        "    path: solo\n"
        "    required: []\n"
        "    capabilities:\n"
        "      required: []\n"
        "      optional: []\n",
        encoding="utf-8",
    )
    errors = validate_capabilities_present(skills_path)
    assert any("stray top-level 'required'" in error for error in errors), errors


def test_load_catalog_rejects_non_mapping_entry(tmp_path: Path) -> None:
    from scripts.registry.backfill_capabilities import load_catalog

    catalog = tmp_path / "catalog.yaml"
    catalog.write_text("skills:\n  demo: null\n", encoding="utf-8")
    try:
        load_catalog(catalog)
    except ValueError as exc:
        assert "demo" in str(exc)
    else:
        raise AssertionError("expected ValueError for non-mapping catalog entry")
