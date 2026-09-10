"""Load per-skill authoring fragments from scripts/registry/skills.d/.

Split out of manifest_merge.py so it has no dependency on schema.py: schema.py needs
these loader functions (to compose the raw registry before parsing it), and
manifest_merge.py needs schema.py's resolve_registry_profiles (to re-derive contract
sub-mappings from a resolved skill view). Keeping the loaders here, with only a
stdlib + yaml_safety dependency, lets both of those imports be plain module-level
imports instead of one of them needing to be deferred inside a function to dodge an
import cycle.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from scripts.yaml_safety import load_unique_yaml_file, require_mapping

FRAGMENTS_DIRNAME = "skills.d"


def skills_fragments_dir(root: Path) -> Path:
    return root / "scripts" / "registry" / FRAGMENTS_DIRNAME


def load_fragment_skills(root: Path) -> dict[str, Any]:
    """Load and merge every scripts/registry/skills.d/*.yaml fragment.

    Each fragment must be a mapping with exactly one key: the skill id, whose
    value is that skill's own entry (the same shape it had inline under
    skills.yaml's `skills:` mapping, `extends:` profile references included --
    profile resolution happens later, against the merged document). The
    fragment's filename (minus `.yaml`) must match its skill id, so a
    misnamed or accidentally duplicated fragment fails loudly instead of
    silently mismatching or shadowing another skill.
    """
    fragments_dir = skills_fragments_dir(root)
    fragment_paths = sorted(fragments_dir.glob("*.yaml"))
    if not fragment_paths:
        raise ValueError(
            f"{fragments_dir}: exists but contains no *.yaml fragments -- refusing to "
            "merge an empty skill set (a bad rebase, partial checkout, or misconfigured "
            ".gitignore could produce this; if the fragments directory itself is meant "
            "to go away, remove it rather than leaving it present and empty)",
        )
    skills: dict[str, Any] = {}
    for fragment_path in fragment_paths:
        raw = require_mapping(load_unique_yaml_file(fragment_path), str(fragment_path))
        if len(raw) != 1:
            raise ValueError(
                f"{fragment_path}: fragment must contain exactly one skill entry, got {len(raw)}",
            )
        ((skill_id, entry),) = raw.items()
        if not isinstance(skill_id, str):
            raise ValueError(f"{fragment_path}: skill id must be a string")
        if skill_id != fragment_path.stem:
            raise ValueError(
                f"{fragment_path}: fragment key {skill_id!r} must match filename {fragment_path.stem!r}.yaml",
            )
        if skill_id in skills:
            raise ValueError(f"duplicate skill id across fragments: {skill_id!r}")
        skills[skill_id] = entry
    return skills


def _skill_composition_contract(entry: dict[str, Any]) -> dict[str, Any]:
    """One skill's `contracts.composition.skills.<id>` entry, from that skill's own fragment.

    `produces`/`produce_fields` come from the skill's `output_contract`, `write_authority`
    from its `authority`, and the consumed half from its `composition` block -- the only
    facts here with no other home in the fragment. Empty field maps are omitted rather than
    written as `{}`, matching how the section was authored by hand. Missing blocks project as
    empty rather than raising: requiring them is `validate_canonical_manifest`'s job, and the
    minimal fixtures several tests build carry neither.
    """
    output_contract = require_mapping(entry.get("output_contract") or {}, "output_contract")
    composition = require_mapping(entry.get("composition") or {}, "composition")
    contract: dict[str, Any] = {
        "produces": list(output_contract.get("produces", [])),
        "consumes": list(composition.get("consumes", [])),
    }
    produce_fields = output_contract.get("produce_fields") or {}
    if produce_fields:
        contract["produce_fields"] = produce_fields
    consume_fields = composition.get("consume_fields") or {}
    if consume_fields:
        contract["consume_fields"] = consume_fields
    contract["write_authority"] = entry.get("authority")
    return contract


def derive_contract_sections(
    contracts: dict[str, Any],
    skills: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Return `contracts` with every per-skill sub-mapping re-derived from `skills`.

    `skills` must be profile-resolved, so a skill inheriting its `authority` or `type` from a
    `profiles:` entry projects the value it actually runs with.

    A section this registry does not carry is left alone rather than conjured: the minimal
    skills.yaml fixtures several tests build declare only part of `contracts:`, and whether a
    required section is missing is `validate_canonical_manifest`'s question, not this one's.
    """
    derived = copy.deepcopy(contracts)
    skill_types = {skill_id: entry.get("type") for skill_id, entry in skills.items()}
    sub_mappings: dict[str, dict[str, Any]] = {
        "platform": {
            "skill_types": skill_types,
            "skill_permissions": {
                skill_id: entry.get("permissions") for skill_id, entry in skills.items()
            },
        },
        "composition_runtime": {"skill_types": dict(skill_types)},
        "composition": {
            "skills": {
                skill_id: _skill_composition_contract(entry) for skill_id, entry in skills.items()
            },
        },
    }
    for section, fields in sub_mappings.items():
        if section not in derived:
            continue
        target = require_mapping(derived[section], f"contracts.{section}")
        for field, value in fields.items():
            target[field] = value
    return derived
