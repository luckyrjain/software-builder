from __future__ import annotations

from pathlib import Path

from scripts.registry.backfill_capabilities import capabilities_equal
from scripts.registry.schema import load_registry_raw
from scripts.yaml_safety import YAML_SAFETY_ERRORS, load_unique_yaml_file, require_mapping


def validate_capability_catalog_sync(root: Path) -> list[str]:
    try:
        registry_raw = require_mapping(load_registry_raw(root / "skills.yaml"), "skills.yaml root")
        registry_skills = require_mapping(registry_raw.get("skills"), "skills.yaml skills")
        catalog_raw = require_mapping(
            load_unique_yaml_file(root / "scripts" / "registry" / "capability_catalog.yaml"),
            "capability catalog root",
        )
        catalog_skills = require_mapping(catalog_raw.get("skills"), "capability catalog skills")

        registry_ids = set(registry_skills)
        catalog_ids = set(catalog_skills)
        if registry_ids != catalog_ids:
            missing = sorted(registry_ids - catalog_ids)
            extra = sorted(catalog_ids - registry_ids)
            parts: list[str] = []
            if missing:
                parts.append(f"catalog missing: {', '.join(missing)}")
            if extra:
                parts.append(f"catalog unknown: {', '.join(extra)}")
            return ["error: capability catalog registry drift: " + "; ".join(parts)]

        drifted: list[str] = []
        for skill_id in sorted(registry_ids):
            registry_entry = require_mapping(registry_skills[skill_id], f"skills.{skill_id}")
            catalog_entry = require_mapping(catalog_skills[skill_id], f"capability catalog.skills.{skill_id}")
            if not capabilities_equal(registry_entry.get("capabilities"), catalog_entry):
                drifted.append(skill_id)
        if drifted:
            return ["error: capability catalog content drift: " + ", ".join(drifted)]
        return []
    except (OSError, *YAML_SAFETY_ERRORS) as exc:
        return [f"error: capability catalog sync: {exc}"]
