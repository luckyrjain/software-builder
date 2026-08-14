from __future__ import annotations

from pathlib import Path

from scripts.registry.composition_contracts import load_contracts
from scripts.registry.models import Registry
from scripts.yaml_safety import YAML_SAFETY_ERRORS, load_unique_yaml_file

RUNTIME_PATH = Path(__file__).resolve().parent / "composition_runtime.yaml"
_ALLOWED_TYPES = {"leaf", "router", "orchestrator", "trigger"}
_ALLOWED_OWNERSHIP_MODES = {"canonical", "shared", "external"}
_LOAD_ERRORS = (OSError, ValueError) + YAML_SAFETY_ERRORS


def load_composition_runtime(path: Path | None = None) -> dict[str, object]:
    resolved = path or RUNTIME_PATH
    raw = load_unique_yaml_file(resolved)
    if not isinstance(raw, dict):
        raise ValueError(f"{resolved}: root must be a mapping")
    if raw.get("schema_version") != 1:
        raise ValueError(f"{resolved}: schema_version must be 1")
    return raw


def validate_composition_runtime(
    registry: Registry,
    runtime_path: Path | None = None,
    contracts_path: Path | None = None,
) -> list[str]:
    resolved = runtime_path or RUNTIME_PATH
    try:
        raw = load_composition_runtime(resolved)
        artifact_types, _schemas, _levels, contracts = load_contracts(contracts_path)
    except _LOAD_ERRORS as exc:
        return [f"error: composition runtime: {exc}"]

    errors: list[str] = []
    skill_ids = set(registry.skills)

    skill_types = raw.get("skill_types")
    if not isinstance(skill_types, dict):
        return [f"error: {resolved}: skill_types must be a mapping"]
    typed_ids = {str(key) for key in skill_types}
    missing = sorted(skill_ids - typed_ids)
    extra = sorted(typed_ids - skill_ids)
    if missing:
        errors.append(f"error: composition runtime missing skill types: {', '.join(missing)}")
    if extra:
        errors.append(f"error: composition runtime unknown skill types: {', '.join(extra)}")
    for skill_id, skill_type in skill_types.items():
        if skill_type not in _ALLOWED_TYPES:
            errors.append(f"error: {skill_id}: invalid skill type {skill_type!r}")

    handoff_schema = raw.get("handoff_schema")
    if not isinstance(handoff_schema, dict):
        errors.append(f"error: {resolved}: handoff_schema must be a mapping")
    else:
        required = handoff_schema.get("required_fields")
        context_fields = handoff_schema.get("execution_context_fields")
        expected = {"target_skill", "reason", "inputs", "evidence_refs", "assumptions", "unresolved", "execution_context"}
        expected_context = {"invocation_id", "parent_skill", "visited_skills", "depth"}
        if not isinstance(required, list) or set(required) != expected:
            errors.append("error: handoff_schema.required_fields must define the canonical handoff envelope")
        if not isinstance(context_fields, list) or set(context_fields) != expected_context:
            errors.append("error: handoff_schema.execution_context_fields must define the recursion context")

    handoffs = raw.get("handoffs")
    if not isinstance(handoffs, dict):
        errors.append(f"error: {resolved}: handoffs must be a mapping")
        handoffs = {}
    for source_id, entry in registry.skills.items():
        for target_id in entry.composition.invokes:
            source_handoffs = handoffs.get(source_id, {})
            if not isinstance(source_handoffs, dict) or target_id not in source_handoffs:
                errors.append(f"error: {source_id}: missing handoff contract for invoked skill {target_id!r}")
                continue
            artifacts = source_handoffs[target_id]
            if not isinstance(artifacts, list) or not artifacts:
                errors.append(f"error: {source_id}->{target_id}: handoff artifacts must be a non-empty list")
                continue
            target_contract = contracts.get(target_id)
            if target_contract is None:
                continue
            for artifact in artifacts:
                if artifact not in artifact_types:
                    errors.append(f"error: {source_id}->{target_id}: unknown handoff artifact {artifact!r}")
                elif artifact not in target_contract.consumes:
                    errors.append(f"error: {source_id}->{target_id}: target does not consume {artifact!r}")

    recursion = raw.get("recursion_guard")
    if not isinstance(recursion, dict):
        errors.append(f"error: {resolved}: recursion_guard must be a mapping")
    else:
        max_depth = recursion.get("default_max_depth")
        if not isinstance(max_depth, int) or isinstance(max_depth, bool) or max_depth < 1:
            errors.append("error: recursion_guard.default_max_depth must be a positive integer")
        if recursion.get("block_revisit_by_default") is not True:
            errors.append("error: recursion_guard.block_revisit_by_default must be true")
        required_types = recursion.get("types_requiring_context")
        if not isinstance(required_types, list) or set(required_types) != {"router", "orchestrator", "trigger"}:
            errors.append("error: recursion_guard.types_requiring_context must cover router, orchestrator, and trigger")

    ownership = raw.get("artifact_ownership")
    if not isinstance(ownership, dict):
        errors.append(f"error: {resolved}: artifact_ownership must be a mapping")
        ownership = {}
    ownership_ids = {str(key) for key in ownership}
    missing_artifacts = sorted(artifact_types - ownership_ids)
    extra_artifacts = sorted(ownership_ids - artifact_types)
    if missing_artifacts:
        errors.append(f"error: artifact ownership missing types: {', '.join(missing_artifacts)}")
    if extra_artifacts:
        errors.append(f"error: artifact ownership unknown types: {', '.join(extra_artifacts)}")
    for artifact, spec in ownership.items():
        if not isinstance(spec, dict):
            errors.append(f"error: artifact_ownership.{artifact} must be a mapping")
            continue
        mode = spec.get("mode")
        owners = spec.get("owners")
        if mode not in _ALLOWED_OWNERSHIP_MODES:
            errors.append(f"error: artifact_ownership.{artifact}.mode invalid: {mode!r}")
            continue
        if not isinstance(owners, list):
            errors.append(f"error: artifact_ownership.{artifact}.owners must be a list")
            continue
        owner_ids = [str(owner) for owner in owners]
        for owner in owner_ids:
            if owner not in skill_ids:
                errors.append(f"error: artifact_ownership.{artifact}: unknown owner {owner!r}")
            elif artifact not in contracts[owner].produces:
                errors.append(f"error: artifact_ownership.{artifact}: owner {owner!r} does not produce artifact")
        if mode == "external" and owner_ids:
            errors.append(f"error: artifact_ownership.{artifact}: external artifacts cannot have skill owners")
        if mode == "canonical" and len(owner_ids) != 1:
            errors.append(f"error: artifact_ownership.{artifact}: canonical mode requires exactly one owner")
        if mode == "shared" and len(owner_ids) < 2:
            errors.append(f"error: artifact_ownership.{artifact}: shared mode requires at least two owners")

    return errors


def render_dependency_graph(
    registry: Registry,
    runtime_path: Path | None = None,
    contracts_path: Path | None = None,
) -> str:
    raw = load_composition_runtime(runtime_path)
    skill_types = raw["skill_types"]
    _artifacts, _schemas, _levels, contracts = load_contracts(contracts_path)

    lines = ["graph TD"]
    for skill_id in sorted(registry.skills):
        skill_type = skill_types[skill_id]
        lines.append(f'  {skill_id}["{skill_id}<br/>{skill_type}"]')
    for skill_id, entry in sorted(registry.skills.items()):
        for dep in sorted(entry.install.requires):
            lines.append(f"  {skill_id} -->|requires| {dep}")
        for target in sorted(entry.composition.invokes):
            lines.append(f"  {skill_id} ==>|handoff| {target}")
        for target in sorted(entry.composition.escalation_targets):
            lines.append(f"  {skill_id} -.->|escalates| {target}")
    producers: dict[str, list[str]] = {}
    consumers: dict[str, list[str]] = {}
    for skill_id, contract in contracts.items():
        for artifact in contract.produces:
            producers.setdefault(artifact, []).append(skill_id)
        for artifact in contract.consumes:
            consumers.setdefault(artifact, []).append(skill_id)
    for artifact in sorted(set(producers) & set(consumers)):
        for producer in sorted(producers[artifact]):
            for consumer in sorted(consumers[artifact]):
                if producer != consumer:
                    lines.append(f"  {producer} -->|{artifact}| {consumer}")
    return "\n".join(lines) + "\n"
