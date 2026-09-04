"""Load and validate composition contracts (produces/consumes/write_authority)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scripts.registry.canonical_manifest import load_contract_section
from scripts.registry.models import Registry
from scripts.test_creator_catalog import TEST_CREATOR_SKILLS
from scripts.yaml_safety import YAML_SAFETY_ERRORS, load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_PATH = Path(__file__).resolve().parent / "composition_contracts.yaml"
CANONICAL_CONTRACTS_PATH = ROOT / "skills.yaml"
DEFAULT_CONTRACTS_PATH = CONTRACTS_PATH


def _load_contract_document(path: Path | None = None) -> dict[str, object]:
    """The `composition` contract document, canonical or projected.

    A path naming skills.yaml (or no path at all) delegates the canonical-vs-projection
    decision to canonical_manifest.load_contract_section, which owns that rule for all three
    contract sections; an explicit path to some other file is read as-is, which is how tests
    and legacy callers point at a standalone document.
    """
    if path is None or path.name == "skills.yaml":
        return load_contract_section(path.parent if path is not None else ROOT, "composition")
    raw = load_unique_yaml_file(path)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: root must be a mapping")
    return raw


@dataclass(frozen=True)
class CompositionContract:
    produces: list[str]
    consumes: list[str]
    write_authority: str
    produce_fields: dict[str, list[str]]
    consume_fields: dict[str, list[str]]


# Sentinel for an id with no entry in `contracts` — produces nothing, so it never
# satisfies a producer lookup.
_UNKNOWN_CONTRACT = CompositionContract([], [], "read-only", {}, {})

_TEST_CREATOR_FORWARDED_FIELDS = [
    "request",
    "repo_root",
    "target",
    "test_framework_hint",
    "run_tests",
    "max_files_per_run",
    "deadline",
    "session_token_budget",
    "output_dir",
    "specialist_inputs",
]


def _validate_creator_parity(
    contracts_path: Path,
    registry: Registry,
    artifact_schemas: dict[str, list[str]],
    contracts: dict[str, CompositionContract],
) -> list[str]:
    """Validate the explicit five-creator composition boundary."""

    present_skills = [skill_id for skill_id in TEST_CREATOR_SKILLS if skill_id in registry.skills]
    # Small registry fixtures used by generic registry tests may intentionally
    # contain none of the test-creator family. Their minimal contract catalogs
    # should not be forced to carry an unrelated family contract.
    if not present_skills:
        return []

    raw = _load_contract_document(contracts_path)
    parity = raw.get("creator_parity") if isinstance(raw, dict) else None
    if not isinstance(parity, dict):
        return ["error: composition contracts missing creator_parity"]

    errors: list[str] = []
    expected_parity = {
        "skills": list(TEST_CREATOR_SKILLS),
        "forwarded_fields": _TEST_CREATOR_FORWARDED_FIELDS,
        "framework_owned_fields": ["execution_context"],
        "child_authority": "skill_result",
        "degraded_status": "BLOCKED",
        "interactive_gate_policy": "specialist-only",
        "router_gate_policy": "classification-only",
    }
    parity_errors = {
        "skills": "error: creator_parity.skills must list the five test creators in canonical order",
        "forwarded_fields": "error: creator_parity.forwarded_fields do not match the canonical pass-through set",
        "framework_owned_fields": "error: creator_parity.framework_owned_fields must be [execution_context]",
        "child_authority": "error: creator_parity.child_authority must preserve skill_result",
        "degraded_status": "error: creator_parity.degraded_status must be BLOCKED",
        "interactive_gate_policy": "error: creator_parity.interactive_gate_policy must be specialist-only",
        "router_gate_policy": "error: creator_parity.router_gate_policy must be classification-only",
    }
    for field, expected in expected_parity.items():
        if parity.get(field) != expected:
            errors.append(parity_errors[field])

    output_contract = parity.get("output_contract")
    if not isinstance(output_contract, dict):
        errors.append("error: creator_parity.output_contract must be a mapping")
    else:
        if output_contract.get("artifact") != "test_suite":
            errors.append("error: creator_parity.output_contract.artifact must be test_suite")
        if output_contract.get("fields") != artifact_schemas.get("test_suite"):
            errors.append("error: creator_parity.output_contract.fields must match test_suite schema")

    for skill_id in TEST_CREATOR_SKILLS:
        if skill_id not in registry.skills:
            errors.append(f"error: creator_parity references unknown skill {skill_id!r}")

    required_task_fields = {
        "task_id",
        "scope",
        "acceptance_criteria",
        *_TEST_CREATOR_FORWARDED_FIELDS,
    }
    for skill_id in ["test-writer", *TEST_CREATOR_SKILLS]:
        if skill_id not in contracts:
            continue
        consumed = set(contracts[skill_id].consume_fields.get("implementation_task", []))
        missing = sorted(required_task_fields - consumed)
        if missing:
            errors.append(
                f"error: {skill_id}: implementation_task consume_fields missing forwarded fields: "
                + ", ".join(missing),
            )
    return errors


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
    resolved_path = path
    if resolved_path is None and CONTRACTS_PATH != DEFAULT_CONTRACTS_PATH:
        resolved_path = CONTRACTS_PATH
    contracts_path = resolved_path or CANONICAL_CONTRACTS_PATH
    raw = _load_contract_document(resolved_path)

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
    levels: dict[str, int] = {}
    for key, value in levels_raw.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{contracts_path}: write_authority_levels.{key} must be an integer")
        levels[str(key)] = value

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
        produces_raw = entry.get("produces", [])
        consumes_raw = entry.get("consumes", [])
        if not isinstance(produces_raw, list) or not all(isinstance(item, str) for item in produces_raw):
            raise ValueError(f"{contracts_path}: skills.{skill_id}.produces must be a list of strings")
        if not isinstance(consumes_raw, list) or not all(isinstance(item, str) for item in consumes_raw):
            raise ValueError(f"{contracts_path}: skills.{skill_id}.consumes must be a list of strings")
        produces = list(produces_raw)
        consumes = list(consumes_raw)
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


def _validate_schema_matching(
    skill_id: str,
    producer_ids: list[str],
    source_label: str,
    contract: CompositionContract,
    contracts: dict[str, CompositionContract],
    artifact_schemas: dict[str, list[str]],
) -> list[str]:
    errors: list[str] = []
    for artifact, required_fields in contract.consume_fields.items():
        if not required_fields:
            continue
        producers = [
            producer_id
            for producer_id in producer_ids
            if artifact in contracts.get(producer_id, _UNKNOWN_CONTRACT).produces
        ]
        if not producers:
            continue
        available: set[str] = set()
        for producer_id in producers:
            producer_contract = contracts[producer_id]
            available.update(_default_produce_fields(producer_contract, artifact, artifact_schemas))
        missing = _fields_covered(required_fields, sorted(available))
        if missing:
            errors.append(
                f"error: {skill_id}: consume_fields.{artifact} requires {missing!r} but {source_label} "
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
    resolved_path = contracts_path or (CONTRACTS_PATH if CONTRACTS_PATH != DEFAULT_CONTRACTS_PATH else CANONICAL_CONTRACTS_PATH)
    try:
        _artifact_types, artifact_schemas, authority_levels, contracts = load_contracts(resolved_path)
    except YAML_SAFETY_ERRORS as exc:
        return [f"error: composition contracts: {exc}"]

    try:
        parity_errors = _validate_creator_parity(resolved_path, registry, artifact_schemas, contracts)
    except (YAML_SAFETY_ERRORS, ValueError) as exc:
        return [f"error: composition creator parity: {exc}"]
    errors.extend(parity_errors)

    missing = sorted(set(registry.skills.keys()) - set(contracts.keys()))
    if missing:
        errors.append(f"error: composition contracts missing skills: {', '.join(missing)}")
        return errors

    for skill_id, entry in registry.skills.items():
        contract = contracts[skill_id]
        errors.extend(_validate_declared_fields(skill_id, contract, artifact_schemas))

        if entry.composition.mode == "invoke" and entry.composition.invokes:
            # No "producer missing" pre-check here (unlike aggregate below): an invoked
            # child that produces nothing just yields an empty `producers` list inside
            # _validate_schema_matching, which is silently skipped there. What invoke
            # mode needs instead is this authority check, since invoking calls a child
            # live at runtime and a wrapper can't safely claim broader write authority
            # than anything it might call.
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
                _validate_schema_matching(
                    skill_id,
                    entry.composition.invokes,
                    "invoked",
                    contract,
                    contracts,
                    artifact_schemas,
                ),
            )

        if entry.composition.mode == "aggregate" and contract.consumes:
            # No authority-escalation check here (unlike invoke above): aggregate mode
            # only reads install-time artifacts, it never calls a child live, so there's
            # no runtime write-authority chain to bound. What it needs instead is this
            # explicit "no producer" check — a static config error, not something a live
            # call would surface on its own the way invoke's would.
            for rollup_input in contract.consumes:
                producers = [
                    dep
                    for dep in entry.install.requires
                    if rollup_input in contracts.get(dep, _UNKNOWN_CONTRACT).produces
                ]
                if not producers:
                    errors.append(
                        f"error: {skill_id}: aggregate consumes {rollup_input!r} but no install.requires "
                        f"skill produces it",
                    )
            errors.extend(
                _validate_schema_matching(
                    skill_id,
                    entry.install.requires,
                    "install.requires",
                    contract,
                    contracts,
                    artifact_schemas,
                ),
            )

    return errors
