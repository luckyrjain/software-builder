from __future__ import annotations

from pathlib import Path

from scripts.registry.canonical_manifest import load_canonical_manifest
from scripts.registry.composition_contracts import load_contracts
from scripts.registry.models import Registry
from scripts.yaml_safety import YAML_SAFETY_ERRORS, load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_PATH = Path(__file__).resolve().parent / "composition_runtime.yaml"
CANONICAL_RUNTIME_PATH = ROOT / "skills.yaml"
_ALLOWED_TYPES = {"leaf", "router", "orchestrator", "trigger"}
_ALLOWED_OWNERSHIP_MODES = {"canonical", "shared", "external"}
_LOAD_ERRORS = (OSError, ValueError) + YAML_SAFETY_ERRORS


def _is_valid_max_depth(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _exact_string_set(value: object) -> set[str] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    if len(value) != len(set(value)):
        return None
    return set(value)


def _report_id_coverage(
    actual_ids: set[str], expected_ids: set[str], *, missing_label: str, extra_label: str
) -> list[str]:
    errors: list[str] = []
    missing = sorted(expected_ids - actual_ids)
    extra = sorted(actual_ids - expected_ids)
    if missing:
        errors.append(f"error: {missing_label}: {', '.join(missing)}")
    if extra:
        errors.append(f"error: {extra_label}: {', '.join(extra)}")
    return errors


def load_composition_runtime(path: Path | None = None) -> dict[str, object]:
    resolved = path or CANONICAL_RUNTIME_PATH
    if path is None or path.name == "skills.yaml":
        manifest_root = path.parent if path is not None else ROOT
        manifest = load_canonical_manifest(manifest_root)
        contracts = manifest.get("contracts")
        raw = contracts.get("composition_runtime") if isinstance(contracts, dict) else None
    else:
        raw = load_unique_yaml_file(resolved)
    if not isinstance(raw, dict):
        raise ValueError(f"{resolved}: composition_runtime must be a mapping")
    if raw.get("schema_version") != 1:
        raise ValueError(f"{resolved}: schema_version must be 1")
    return raw


def handoff_allowed(
    target_skill: str,
    *,
    visited_skills: list[str],
    depth: int,
    runtime_path: Path | None = None,
) -> tuple[bool, str | None]:
    """Apply the portable recursion guard before a cross-skill handoff."""
    raw = load_composition_runtime(runtime_path)
    recursion = raw.get("recursion_guard")
    if not isinstance(recursion, dict):
        return False, "recursion guard is unavailable"
    max_depth = recursion.get("default_max_depth")
    if not _is_valid_max_depth(max_depth):
        return False, "recursion guard depth is invalid"
    if depth >= max_depth:
        return False, f"maximum composition depth {max_depth} reached"
    if recursion.get("block_revisit_by_default") is True and target_skill in visited_skills:
        return False, f"skill {target_skill!r} was already visited"
    return True, None


def validate_composition_runtime(
    registry: Registry,
    runtime_path: Path | None = None,
    contracts_path: Path | None = None,
) -> list[str]:
    resolved = runtime_path or CANONICAL_RUNTIME_PATH
    try:
        raw = load_composition_runtime(runtime_path)
        artifact_types, _schemas, _levels, contracts = load_contracts(contracts_path)
    except _LOAD_ERRORS as exc:
        return [f"error: composition runtime: {exc}"]

    errors: list[str] = []
    skill_ids = set(registry.skills)

    skill_types = raw.get("skill_types")
    if not isinstance(skill_types, dict):
        return [f"error: {resolved}: skill_types must be a mapping"]
    typed_ids = {str(key) for key in skill_types}
    errors.extend(
        _report_id_coverage(
            typed_ids,
            skill_ids,
            missing_label="composition runtime missing skill types",
            extra_label="composition runtime unknown skill types",
        )
    )
    for skill_id, skill_type in skill_types.items():
        if skill_type not in _ALLOWED_TYPES:
            errors.append(f"error: {skill_id}: invalid skill type {skill_type!r}")
            continue
        if skill_id not in registry.skills:
            continue
        invokes = registry.skills[skill_id].composition.invokes
        if skill_type == "leaf" and invokes:
            errors.append(f"error: {skill_id}: leaf skills cannot invoke child skills")
        if skill_type == "router" and not invokes:
            errors.append(f"error: {skill_id}: router skills must declare at least one invoke target")

    handoff_schema = raw.get("handoff_schema")
    if not isinstance(handoff_schema, dict):
        errors.append(f"error: {resolved}: handoff_schema must be a mapping")
    else:
        expected = {"target_skill", "reason", "inputs", "evidence_refs", "assumptions", "unresolved", "execution_context"}
        expected_context = {"invocation_id", "parent_skill", "visited_skills", "depth"}
        required = _exact_string_set(handoff_schema.get("required_fields"))
        context_fields = _exact_string_set(handoff_schema.get("execution_context_fields"))
        if required != expected:
            errors.append("error: handoff_schema.required_fields must define the canonical handoff envelope")
        if context_fields != expected_context:
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
        if not _is_valid_max_depth(max_depth):
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
    errors.extend(
        _report_id_coverage(
            ownership_ids,
            artifact_types,
            missing_label="artifact ownership missing types",
            extra_label="artifact ownership unknown types",
        )
    )

    artifact_producers: dict[str, set[str]] = {artifact: set() for artifact in artifact_types}
    for skill_id, contract in contracts.items():
        for artifact in contract.produces:
            artifact_producers.setdefault(artifact, set()).add(skill_id)

    for artifact, spec in ownership.items():
        if not isinstance(spec, dict):
            errors.append(f"error: artifact_ownership.{artifact} must be a mapping")
            continue
        mode = spec.get("mode")
        owners = spec.get("owners")
        delegates = spec.get("delegates", [])
        if mode not in _ALLOWED_OWNERSHIP_MODES:
            errors.append(f"error: artifact_ownership.{artifact}.mode invalid: {mode!r}")
            continue
        if not isinstance(owners, list) or not isinstance(delegates, list):
            errors.append(f"error: artifact_ownership.{artifact}.owners and delegates must be lists")
            continue
        owner_ids = [str(owner) for owner in owners]
        delegate_ids = [str(delegate) for delegate in delegates]
        declared_producers = set(owner_ids) | set(delegate_ids)
        for producer in owner_ids + delegate_ids:
            if producer not in skill_ids:
                errors.append(f"error: artifact_ownership.{artifact}: unknown producer {producer!r}")
            elif producer not in contracts or artifact not in contracts[producer].produces:
                errors.append(f"error: artifact_ownership.{artifact}: producer {producer!r} does not produce artifact")
        if mode == "external":
            if owner_ids or delegate_ids:
                errors.append(f"error: artifact_ownership.{artifact}: external artifacts cannot have skill producers")
            real_producers = sorted(artifact_producers.get(artifact, set()))
            if real_producers:
                errors.append(
                    f"error: artifact_ownership.{artifact}: external artifacts must have no producers, "
                    f"found: {', '.join(real_producers)}"
                )
        elif mode == "canonical":
            if len(owner_ids) != 1:
                errors.append(f"error: artifact_ownership.{artifact}: canonical mode requires exactly one owner")
            undeclared = sorted(artifact_producers.get(artifact, set()) - declared_producers)
            if undeclared:
                errors.append(
                    f"error: artifact_ownership.{artifact}: undeclared delegated producers: {', '.join(undeclared)}"
                )
        elif mode == "shared":
            if len(owner_ids) < 2 or delegate_ids:
                errors.append(f"error: artifact_ownership.{artifact}: shared mode requires two or more owners and no delegates")
            undeclared = sorted(artifact_producers.get(artifact, set()) - set(owner_ids))
            if undeclared:
                errors.append(f"error: artifact_ownership.{artifact}: shared producers missing owners: {', '.join(undeclared)}")

    return errors


def render_dependency_graph(
    registry: Registry,
    runtime_path: Path | None = None,
    contracts_path: Path | None = None,
) -> str:
    raw = load_composition_runtime(runtime_path)
    skill_types = raw.get("skill_types")
    if not isinstance(skill_types, dict):
        raise ValueError(f"{runtime_path or RUNTIME_PATH}: skill_types must be a mapping")
    missing = sorted(set(registry.skills) - {str(key) for key in skill_types})
    if missing:
        raise ValueError(f"{runtime_path or RUNTIME_PATH}: missing skill types: {', '.join(missing)}")
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

