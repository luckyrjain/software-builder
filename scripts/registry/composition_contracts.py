"""Load and validate composition contracts (produces/consumes/write_authority)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from scripts.registry.models import Registry

CONTRACTS_PATH = Path(__file__).resolve().parent / "composition_contracts.yaml"


@dataclass(frozen=True)
class CompositionContract:
    produces: list[str]
    consumes: list[str]
    write_authority: str


def load_contracts(path: Path | None = None) -> tuple[set[str], dict[str, int], dict[str, CompositionContract]]:
    contracts_path = path or CONTRACTS_PATH
    raw = yaml.safe_load(contracts_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{contracts_path}: root must be a mapping")

    artifact_types = raw.get("artifact_types", [])
    if not isinstance(artifact_types, list):
        raise ValueError(f"{contracts_path}: artifact_types must be a list")
    artifact_set = {str(item) for item in artifact_types}

    levels_raw = raw.get("write_authority_levels", {})
    if not isinstance(levels_raw, dict):
        raise ValueError(f"{contracts_path}: write_authority_levels must be a mapping")
    levels = {str(key): int(value) for key, value in levels_raw.items()}

    skills_raw = raw.get("skills", {})
    if not isinstance(skills_raw, dict):
        raise ValueError(f"{contracts_path}: skills must be a mapping")

    contracts: dict[str, CompositionContract] = {}
    for skill_id, entry in skills_raw.items():
        if not isinstance(entry, dict):
            raise ValueError(f"{contracts_path}: skills.{skill_id} must be a mapping")
        authority = str(entry.get("write_authority", ""))
        if authority not in levels:
            raise ValueError(f"{contracts_path}: skills.{skill_id}.write_authority invalid: {authority!r}")
        produces = [str(item) for item in entry.get("produces", [])]
        consumes = [str(item) for item in entry.get("consumes", [])]
        for artifact in produces + consumes:
            if artifact not in artifact_set:
                raise ValueError(f"{contracts_path}: skills.{skill_id}: unknown artifact type {artifact!r}")
        contracts[str(skill_id)] = CompositionContract(
            produces=produces,
            consumes=consumes,
            write_authority=authority,
        )

    return artifact_set, levels, contracts


def validate_catalog_covers_registry(
    registry: Registry,
    contracts_path: Path | None = None,
) -> list[str]:
    _, _, contracts = load_contracts(contracts_path)
    missing = sorted(set(registry.skills.keys()) - set(contracts.keys()))
    extra = sorted(set(contracts.keys()) - set(registry.skills.keys()))
    errors: list[str] = []
    if missing:
        errors.append(f"error: composition contracts missing skills: {', '.join(missing)}")
    if extra:
        errors.append(f"error: composition contracts unknown skills: {', '.join(extra)}")
    return errors


def validate_composition_contracts(
    registry: Registry,
    contracts_path: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    resolved_path = contracts_path or CONTRACTS_PATH
    try:
        _artifact_types, authority_levels, contracts = load_contracts(resolved_path)
    except (ValueError, yaml.YAMLError) as exc:
        return [f"error: composition contracts: {exc}"]

    missing = sorted(set(registry.skills.keys()) - set(contracts.keys()))
    if missing:
        errors.append(f"error: composition contracts missing skills: {', '.join(missing)}")
        return errors

    for skill_id, entry in registry.skills.items():
        contract = contracts[skill_id]

        if entry.composition.mode == "invoke" and entry.composition.invokes:
            max_child_authority = -1
            for child_id in entry.composition.invokes:
                child = contracts.get(child_id)
                if child is None:
                    continue
                max_child_authority = max(
                    max_child_authority,
                    authority_levels[child.write_authority],
                )
            wrapper_rank = authority_levels[contract.write_authority]
            if max_child_authority >= 0 and wrapper_rank > max_child_authority:
                errors.append(
                    f"error: {skill_id}: write_authority {contract.write_authority!r} exceeds "
                    f"max invoked skill authority (rank {max_child_authority})",
                )

        if entry.composition.mode == "aggregate" and contract.consumes:
            for rollup_input in contract.consumes:
                producers = [
                    dep
                    for dep in entry.install.requires
                    if rollup_input in contracts.get(dep, CompositionContract([], [], "read-only")).produces
                ]
                if not producers:
                    errors.append(
                        f"error: {skill_id}: aggregate consumes {rollup_input!r} but no install.requires "
                        f"skill produces it",
                    )

    return errors
