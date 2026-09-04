"""Validate that provider-branded capability ids resolve to an abstract family.

Skills declare concrete capability ids (``gitlab.get_merge_request``,
``datadog.query_metrics``, ...) in ``capability_catalog.yaml`` because that's
what actually gets called. ``capability_families.yaml`` is the separate
adapter-resolution layer: it maps each provider-branded id to a
provider-agnostic family name a host can resolve to whichever adapter it has
installed. This validator keeps the two files from drifting -- every branded
id in the catalog must resolve to a family, and every id a family claims to
resolve must still exist in the catalog.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.registry.capability_catalog import load_catalog
from scripts.yaml_safety import YAML_SAFETY_ERRORS, load_unique_yaml_file

FAMILIES_PATH = Path(__file__).resolve().parent / "capability_families.yaml"
CATALOG_PATH = Path(__file__).resolve().parent / "capability_catalog.yaml"

# Capability ids exempt from family resolution: host adapter capabilities and
# skill-invoke capabilities are already provider-neutral by construction, and
# these leaf ids never named a specific vendor to begin with.
_EXEMPT_PREFIXES = ("host.",)
_EXEMPT_SUFFIXES = (".invoke",)
_EXEMPT_IDS = frozenset(
    {
        "telemetry.logs.query",
        "pager.webhook.receive",
        "scheduler.cron.trigger",
        "slack.post.message",
        "slack.slash_command.receive",
    },
)


def _is_exempt(capability_id: str) -> bool:
    if capability_id in _EXEMPT_IDS:
        return True
    if any(capability_id.startswith(prefix) for prefix in _EXEMPT_PREFIXES):
        return True
    return any(capability_id.endswith(suffix) for suffix in _EXEMPT_SUFFIXES)


def _optional_names(optional: Any, *, label: str) -> list[str]:
    if optional is None:
        return []
    if not isinstance(optional, list) or not all(isinstance(item, dict) and "name" in item for item in optional):
        raise ValueError(f"{label} must be a list of {{name: ...}} mappings")
    return [item["name"] for item in optional]


def _catalog_capability_ids(entry: dict[str, Any], *, skill_id: str) -> set[str]:
    ids: set[str] = set()
    ids.update(entry.get("required") or [])
    ids.update(_optional_names(entry.get("optional"), label=f"{skill_id}.optional"))
    for path in entry.get("any_of") or []:
        path_name = path.get("name", "<unnamed any_of path>")
        ids.update(path.get("required") or [])
        ids.update(
            _optional_names(path.get("optional"), label=f"{skill_id}.any_of[{path_name!r}].optional"),
        )
    ids.update((entry.get("degraded_modes") or {}).keys())
    return ids


def load_capability_families(path: Path = FAMILIES_PATH) -> dict[str, list[str]]:
    raw = load_unique_yaml_file(path)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: root must be a mapping")
    if raw.get("schema_version") != 1:
        raise ValueError(f"{path}: schema_version must be 1")
    families = raw.get("families")
    if not isinstance(families, dict):
        raise ValueError(f"{path}: families must be a mapping")
    parsed: dict[str, list[str]] = {}
    for family, spec in families.items():
        if not isinstance(spec, dict) or not isinstance(spec.get("resolves"), list):
            raise ValueError(f"{path}: families.{family}.resolves must be a list")
        parsed[str(family)] = [str(item) for item in spec["resolves"]]
    return parsed


def validate_capability_families(
    catalog_path: Path = CATALOG_PATH,
    families_path: Path = FAMILIES_PATH,
) -> list[str]:
    try:
        catalog = load_catalog(catalog_path)
        families = load_capability_families(families_path)
    except (OSError, *YAML_SAFETY_ERRORS) as exc:
        return [f"error: capability families: {exc}"]

    catalog_ids: set[str] = set()
    try:
        for skill_id, entry in catalog.items():
            catalog_ids.update(_catalog_capability_ids(entry, skill_id=skill_id))
    except ValueError as exc:
        return [f"error: capability families: {exc}"]

    resolved_ids: set[str] = set()
    errors: list[str] = []
    for family, resolves in families.items():
        for capability_id in resolves:
            resolved_ids.add(capability_id)
            if capability_id not in catalog_ids:
                errors.append(
                    f"error: capability_families.{family} resolves stale/unknown "
                    f"capability {capability_id!r} (not in capability_catalog.yaml)",
                )

    unresolved = sorted(
        capability_id
        for capability_id in catalog_ids
        if capability_id not in resolved_ids and not _is_exempt(capability_id)
    )
    if unresolved:
        errors.append(
            "error: capability_catalog.yaml has provider-branded capabilities with no "
            "abstract family in capability_families.yaml: " + ", ".join(unresolved),
        )
    return errors
