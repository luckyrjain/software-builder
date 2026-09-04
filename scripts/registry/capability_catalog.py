"""Read the generated capability catalogue, and validate the registry's capability blocks.

`capability_catalog.yaml` used to be hand-authored and this module wrote its contents
back *into* skills.yaml -- an inverse projection, policed by a drift validator
(`capability_sync.py`) that existed only because the same contract was written twice.
The catalogue is now generated from the `capabilities:` block of each
`scripts/registry/skills.d/*.yaml` fragment (see `manifest_merge.SIDE_FILE_PROJECTIONS`),
so the fragment is the one place a skill's capability contract is authored and
`make generate-check` is what detects drift.

What remains here is the reading half: `load_catalog` for the catalogue's readers, and
`validate_capabilities_present` for the shape every registered skill's own block must
have. The `backfill-capabilities` CLI subcommand and Makefile targets keep their names
as the stable external interface; this module is renamed to match what it now does.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from scripts.registry.paths import SKILLS_YAML_PATH as SKILLS_PATH
from scripts.registry.schema import load_registry_raw
from scripts.yaml_safety import load_unique_yaml_file

CATALOG_PATH = Path(__file__).resolve().parent / "capability_catalog.yaml"

_STRAY_CAPABILITY_KEYS = ("required", "optional", "any_of", "degraded_modes")


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    raw = load_unique_yaml_file(path)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: root must be a mapping")
    skills = raw.get("skills")
    if not isinstance(skills, dict):
        raise ValueError(f"{path}: skills must be a mapping")
    for skill_id, entry in skills.items():
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: skills.{skill_id} must be a mapping")
    return {str(skill_id): entry for skill_id, entry in skills.items()}


def validate_capabilities_present(skills_path: Path = SKILLS_PATH) -> list[str]:
    raw = load_registry_raw(skills_path)
    if not isinstance(raw, dict):
        return ["error: skills.yaml root must be a mapping"]
    skills = raw.get("skills")
    if not isinstance(skills, dict):
        return ["error: skills.yaml skills must be a mapping"]

    errors: list[str] = []
    for skill_id, entry in skills.items():
        if not isinstance(entry, dict):
            errors.append(f"error: {skill_id}: skill entry must be a mapping")
            continue
        for orphan_key in _STRAY_CAPABILITY_KEYS:
            if orphan_key in entry:
                errors.append(
                    f"error: {skill_id}: stray top-level {orphan_key!r} key (belongs under capabilities)",
                )
        capabilities = entry.get("capabilities")
        if not isinstance(capabilities, dict):
            errors.append(f"error: {skill_id}: missing capabilities block")
            continue
        required = capabilities.get("required", [])
        optional = capabilities.get("optional", [])
        any_of = capabilities.get("any_of", [])
        if not isinstance(required, list):
            errors.append(f"error: {skill_id}: capabilities.required must be a list")
        if not isinstance(optional, list):
            errors.append(f"error: {skill_id}: capabilities.optional must be a list")
        if not isinstance(any_of, list):
            errors.append(f"error: {skill_id}: capabilities.any_of must be a list")
        degraded_modes = capabilities.get("degraded_modes", {})
        if not isinstance(degraded_modes, dict):
            errors.append(f"error: {skill_id}: capabilities.degraded_modes must be a mapping")

    return errors


def cmd_check_capabilities(*, skills_path: Path) -> int:
    """Validate that every registered skill declares a well-shaped capabilities block.

    Reached as the `backfill-capabilities` subcommand, whose name and `--check`/`--overwrite`
    flags are kept so `make backfill-capabilities-check` and
    `make backfill-capabilities-drift-check` keep working while those targets are retired.
    Neither flag selects a direction any more: there is no write direction, and catalogue
    drift is now a `make generate-check` failure.
    """
    errors = validate_capabilities_present(skills_path)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(
            "hint: edit the skill's scripts/registry/skills.d/<skill>.yaml fragment, then run make generate",
            file=sys.stderr,
        )
        return 1
    print("ok: all skills declare a capabilities block")
    return 0
