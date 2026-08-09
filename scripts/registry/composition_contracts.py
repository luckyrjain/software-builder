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
    produce_fields: dict[str, list[str]]
    consume_fields: dict[str, list[str]]


def _parse_field_map(
    raw: object,
    *,
    contracts_path: Path,
    skill_id: str,
    label: str,
) -> dict[str, list[str]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{contracts_path}: skills.{skill_id}.{label} must be a mapping")
    parsed: dict[str, list[str]] = {}
    for artifact, fields in raw.items():
        if not isinstance(fields, list):
            raise ValueError(
                f"{contracts_path}: skills.{skill_id}.{label}.{artifact} must be a list",
            )
        parsed[str(artifact)] = [str(field) for field in fields]
    return parsed


def load_contracts(
    path: Path | None = None,
) -> tuple[set[str], dict[str, list[str]], dict[str, int], dict[str, CompositionContract]]:
    contracts_path = path or CONTRACTS_PATH
    raw = yaml.safe_load(contracts_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{contracts_path}: root must be a mapping")

    artifact_types = raw.get("artifact_types", [])
    if not isinstance(artifact_types, list):
        raise ValueError(f"{contracts_path}: artifact_types must be a list")
    artifact_set = {str(item) for item in artifact_types}

    schemas_raw = raw.get("artifact_schemas", {})
    if not isinstance(schemas_raw, dict):
        raise ValueError(f"{contracts_path}: artifact_schemas must be a mapping")
    artifact_schemas: dict[str, list[str]] = {}
    for artifact, entry in schemas_raw.items():
        artifact_name = str(artifact)
        if artifact_name not in artifact_set:
            raise ValueError(f"{contracts_path}: artifact_schemas.{artifact_name}: unknown artifact type")
        if not isinstance(entry, dict):
            raise ValueError(f"{contracts_path}: artifact_schemas.{artifact_name} must be a mapping")
        fields = entry.get("fields", [])
        if not isinstance(fields, list) or not fields:
            raise ValueError(f"{contracts_path}: artifact_schemas.{artifact_name}.fields must be a non-empty list")
        artifact_schemas[artifact_name] = [str(field) for field in fields]

    missing_schema = sorted(artifact_set - set(artifact_schemas.keys()))
    if missing_schema:
        raise ValueError(
            f"{contracts_path}: artifact_schemas missing definitions for: {', '.join(missing_schema)}",
        )

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
        produce_fields = _parse_field_map(
            entry.get("produce_fields"),
            contracts_path=contracts_path,
            skill_id=str(skill_id),
            label="produce_fields",
        )
        consume_fields = _parse_field_map(
            entry.get("consume_fields"),
            contracts_path=contracts_path,
            skill_id=str(skill_id),
            label="consume_fields",
        )
        for artifact in produces + consumes:
            if artifact not in artifact_set:
                raise ValueError(f"{contracts_path}: skills.{skill_id}: unknown artifact type {artifact!r}")
        contracts[str(skill_id)] = CompositionContract(
            produces=produces,
            consumes=consumes,
            write_authority=authority,
            produce_fields=produce_fields,
            consume_fields=consume_fields,
        )

    return artifact_set, artifact_schemas, levels, contracts


def _default_produce_fields(
    contract: CompositionContract,
    artifact: str,
    artifact_schemas: dict[str, list[str]],
) -> list[str]:
    if artifact in contract.produce_fields:
        return list(contract.produce_fields[artifact])
    if artifact in contract.produces:
        return list(artifact_schemas[artifact])
    return []


def _validate_declared_fields(
    skill_id: str,
    contract: CompositionContract,
    artifact_schemas: dict[str, list[str]],
) -> list[str]:
    errors: list[str] = []
    for artifact, fields in contract.produce_fields.items():
        schema_fields = set(artifact_schemas.get(artifact, []))
        unknown = sorted(set(fields) - schema_fields)
        if unknown:
            errors.append(
                f"error: {skill_id}: produce_fields.{artifact} unknown fields: {', '.join(unknown)}",
            )
        if artifact not in contract.produces:
            errors.append(
                f"error: {skill_id}: produce_fields declares {artifact!r} but it is not in produces",
            )
    for artifact, fields in contract.consume_fields.items():
        schema_fields = set(artifact_schemas.get(artifact, []))
        unknown = sorted(set(fields) - schema_fields)
        if unknown:
            errors.append(
                f"error: {skill_id}: consume_fields.{artifact} unknown fields: {', '.join(unknown)}",
            )
        if artifact not in contract.consumes:
            errors.append(
                f"error: {skill_id}: consume_fields declares {artifact!r} but it is not in consumes",
            )
    return errors


def _fields_covered(required: list[str], available: list[str]) -> list[str]:
    return sorted(set(required) - set(available))


def _validate_invoke_schema_matching(
    skill_id: str,
    entry,
    contract: CompositionContract,
    contracts: dict[str, CompositionContract],
    artifact_schemas: dict[str, list[str]],
) -> list[str]:
    errors: list[str] = []
    for artifact, required_fields in contract.consume_fields.items():
        if not required_fields:
            continue
        producers = [
            child_id
            for child_id in entry.composition.invokes
            if artifact in contracts.get(child_id, CompositionContract([], [], "read-only", {}, {})).produces
        ]
        if not producers:
            continue
        available: set[str] = set()
        for child_id in producers:
            child = contracts[child_id]
            available.update(_default_produce_fields(child, artifact, artifact_schemas))
        missing = _fields_covered(required_fields, sorted(available))
        if missing:
            errors.append(
                f"error: {skill_id}: consume_fields.{artifact} requires {missing!r} but invoked "
                f"producer(s) {producers} only expose {sorted(available)!r}",
            )
    return errors


def _validate_aggregate_schema_matching(
    skill_id: str,
    entry,
    contract: CompositionContract,
    contracts: dict[str, CompositionContract],
    artifact_schemas: dict[str, list[str]],
) -> list[str]:
    errors: list[str] = []
    for artifact, required_fields in contract.consume_fields.items():
        if not required_fields:
            continue
        producers = [
            dep
            for dep in entry.install.requires
            if artifact in contracts.get(dep, CompositionContract([], [], "read-only", {}, {})).produces
        ]
        if not producers:
            continue
        available: set[str] = set()
        for dep in producers:
            dep_contract = contracts[dep]
            available.update(_default_produce_fields(dep_contract, artifact, artifact_schemas))
        missing = _fields_covered(required_fields, sorted(available))
        if missing:
            errors.append(
                f"error: {skill_id}: consume_fields.{artifact} requires {missing!r} but install.requires "
                f"producer(s) {producers} only expose {sorted(available)!r}",
            )
    return errors


def validate_catalog_covers_registry(
    registry: Registry,
    contracts_path: Path | None = None,
) -> list[str]:
    _, _, _, contracts = load_contracts(contracts_path)
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
        _artifact_types, artifact_schemas, authority_levels, contracts = load_contracts(resolved_path)
    except (ValueError, yaml.YAMLError) as exc:
        return [f"error: composition contracts: {exc}"]

    missing = sorted(set(registry.skills.keys()) - set(contracts.keys()))
    if missing:
        errors.append(f"error: composition contracts missing skills: {', '.join(missing)}")
        return errors

    for skill_id, entry in registry.skills.items():
        contract = contracts[skill_id]
        errors.extend(_validate_declared_fields(skill_id, contract, artifact_schemas))

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
            errors.extend(
                _validate_invoke_schema_matching(
                    skill_id,
                    entry,
                    contract,
                    contracts,
                    artifact_schemas,
                ),
            )

        if entry.composition.mode == "aggregate" and contract.consumes:
            for rollup_input in contract.consumes:
                producers = [
                    dep
                    for dep in entry.install.requires
                    if rollup_input
                    in contracts.get(dep, CompositionContract([], [], "read-only", {}, {})).produces
                ]
                if not producers:
                    errors.append(
                        f"error: {skill_id}: aggregate consumes {rollup_input!r} but no install.requires "
                        f"skill produces it",
                    )
            errors.extend(
                _validate_aggregate_schema_matching(
                    skill_id,
                    entry,
                    contract,
                    contracts,
                    artifact_schemas,
                ),
            )

    return errors
