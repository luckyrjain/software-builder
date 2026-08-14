from __future__ import annotations

from pathlib import Path

import yaml

from scripts.registry.capability_family_sync import (
    CATALOG_PATH,
    FAMILIES_PATH,
    validate_capability_families,
)


def test_real_catalog_and_families_are_in_sync() -> None:
    assert validate_capability_families() == []


def test_unfamilied_provider_capability_is_rejected(tmp_path: Path) -> None:
    catalog_path = tmp_path / "capability_catalog.yaml"
    catalog_path.write_text(
        yaml.safe_dump(
            {
                "skills": {
                    "demo": {"required": ["newvendor.do_thing"], "optional": [], "any_of": []},
                },
            },
        ),
        encoding="utf-8",
    )
    errors = validate_capability_families(catalog_path=catalog_path, families_path=FAMILIES_PATH)
    assert any("newvendor.do_thing" in error for error in errors)


def test_stale_family_resolution_is_rejected(tmp_path: Path) -> None:
    families_path = tmp_path / "capability_families.yaml"
    families_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "families": {
                    "scm.pull_request.read": {"resolves": ["gitlab.this_id_does_not_exist"]},
                },
            },
        ),
        encoding="utf-8",
    )
    errors = validate_capability_families(catalog_path=CATALOG_PATH, families_path=families_path)
    assert any("gitlab.this_id_does_not_exist" in error for error in errors)


def test_host_and_invoke_capabilities_are_exempt_from_family_resolution(tmp_path: Path) -> None:
    catalog_path = tmp_path / "capability_catalog.yaml"
    catalog_path.write_text(
        yaml.safe_dump(
            {
                "skills": {
                    "demo": {
                        "required": ["host.repository.read", "other-skill.invoke"],
                        "optional": [],
                        "any_of": [],
                    },
                },
            },
        ),
        encoding="utf-8",
    )
    families_path = tmp_path / "capability_families.yaml"
    families_path.write_text(
        yaml.safe_dump({"schema_version": 1, "families": {}}),
        encoding="utf-8",
    )
    errors = validate_capability_families(catalog_path=catalog_path, families_path=families_path)
    assert errors == []
