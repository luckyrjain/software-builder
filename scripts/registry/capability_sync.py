from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.yaml_safety import YAML_SAFETY_ERRORS, load_unique_yaml_file


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def validate_capability_catalog_sync(root: Path) -> list[str]:
    try:
        registry_raw = _mapping(load_unique_yaml_file(root / "skills.yaml"), "skills.yaml root")
        registry_skills = _mapping(registry_raw.get("skills"), "skills.yaml skills")
        catalog_raw = _mapping(
            load_unique_yaml_file(root / "scripts" / "registry" / "capability_catalog.yaml"),
            "capability catalog root",
        )
        catalog_skills = _mapping(catalog_raw.get("skills"), "capability catalog skills")

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
            registry_entry = _mapping(registry_skills[skill_id], f"skills.{skill_id}")
            if (registry_entry.get("capabilities") or {}) != (catalog_skills[skill_id] or {}):
                drifted.append(skill_id)
        if drifted:
            return ["error: capability catalog content drift: " + ", ".join(drifted)]
        return []
    except YAML_SAFETY_ERRORS as exc:
        return [f"error: capability catalog sync: {exc}"]
