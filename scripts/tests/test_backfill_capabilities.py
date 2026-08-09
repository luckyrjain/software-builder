"""Tests for capability catalog backfill."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_capability_catalog_covers_all_registry_skills() -> None:
    from scripts.registry.backfill_capabilities import load_catalog
    from scripts.registry.schema import parse_registry

    catalog = load_catalog()
    registry = parse_registry(ROOT / "skills.yaml")
    assert set(catalog.keys()) == set(registry.skills.keys())


def test_all_skills_have_capabilities_block() -> None:
    from scripts.registry.backfill_capabilities import validate_capabilities_present

    assert validate_capabilities_present(ROOT / "skills.yaml") == []


def test_backfill_check_passes_on_repository() -> None:
    from scripts.registry.backfill_capabilities import cmd_backfill

    assert (
        cmd_backfill(check_only=True, overwrite=False, skills_path=ROOT / "skills.yaml") == 0
    )


def test_backfill_inserts_missing_block(tmp_path: Path) -> None:
    from scripts.registry.backfill_capabilities import backfill_skills_yaml_text

    skills_yaml = tmp_path / "skills.yaml"
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        """
skills:
  demo:
    required: [host.repository.read]
    optional: []
""",
        encoding="utf-8",
    )
    skills_yaml.write_text(
        """
schema_version: 1
skills:
  demo:
    path: demo
    category: testing
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install:
      requires: []
    lint:
      skill_md_max_lines: 180
      target: demo
""",
        encoding="utf-8",
    )
    updated, changes = backfill_skills_yaml_text(
        skills_yaml.read_text(encoding="utf-8"),
        catalog_path=catalog,
    )
    assert changes == ["demo"]
    assert "capabilities:" in updated
    assert "host.repository.read" in updated
