"""Validate durable artifact contracts and runtime result envelopes."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.registry.canonical_manifest import is_semver, load_canonical_manifest
from scripts.registry.composition_contracts import load_contracts
from scripts.yaml_safety import YAML_SAFETY_ERRORS, require_mapping

ROOT = Path(__file__).resolve().parents[2]

_SECTION_FIELDS = {
    "skill_result": {
        "skill",
        "version",
        "status",
        "confidence",
        "source_revision",
        "evidence_status",
        "artifacts",
        "blockers",
        "recommended_next_skill",
        "artifact_schema_version",
        "state_semantic",
    },
    "provenance": {"source_revision", "sources"},
    "freshness": {"observed_at", "source_revision", "source_environment"},
    "definition_of_done": {
        "required_artifacts",
        "required_checks",
        "completed_checks",
        "blocked_conditions",
        "partial_result_behavior",
    },
    "authority": {"write_authority", "canonical_owner"},
}
_COMPLETION_STATUSES = {"SUCCESS", "PARTIAL", "BLOCKED", "FAILED", "ESCALATED"}
_CONFIDENCE_VALUES = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}
_EVIDENCE_STATUSES = {"OBSERVED", "INFERRED", "UNKNOWN", "CONFLICTED", "NOT_APPLICABLE"}
_PAYLOAD_TYPES = {"mapping", "list", "string", "boolean", "integer"}
_STATE_VALUES = {"current_state", "proposed_state", "desired_state", "transitional_state"}


def _strings(value: object, label: str) -> tuple[list[str] | None, str | None]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        return None, f"error: artifact runtime {label} must be a non-empty list of strings"
    if len(value) != len(set(value)):
        return None, f"error: artifact runtime {label} must not contain duplicates"
    return list(value), None


def _load_contract_data(
    root: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, int],
    dict[str, Any],
    set[str],
    dict[str, list[str]],
    dict[str, Any],
]:
    manifest = load_canonical_manifest(root)
    contracts = require_mapping(manifest.get("contracts"), "canonical manifest.contracts")
    platform = require_mapping(contracts.get("platform"), "contracts.platform")
    runtime = require_mapping(contracts.get("composition_runtime"), "contracts.composition_runtime")
    artifact_runtime = require_mapping(platform.get("artifact_runtime"), "platform.artifact_runtime")
    skills = require_mapping(manifest.get("skills"), "canonical manifest.skills")
    artifact_types, artifact_schemas, authority_levels, skill_contracts = load_contracts(root / "skills.yaml")
    return artifact_runtime, runtime, authority_levels, skill_contracts, artifact_types, artifact_schemas, skills


def _validate_catalog(
    artifact_runtime: dict[str, Any],
    runtime: dict[str, Any],
    authority_levels: dict[str, int],
    skill_contracts: dict[str, Any],
    artifact_types: set[str],
    skill_ids: set[str],
    artifact_schemas: dict[str, list[str]],
) -> list[str]:
    errors: list[str] = []
    if artifact_runtime.get("schema_version") != 1:
        errors.append("error: artifact runtime schema_version must be 1")

    external, error = _strings(
        artifact_runtime.get("external_input_artifacts"),
        "external_input_artifacts",
    )
    if error:
        errors.append(error)
        external = []
    durable, error = _strings(artifact_runtime.get("durable_artifacts"), "durable_artifacts")
    if error:
        errors.append(error)
        durable = []
    required_sections = artifact_runtime.get("required_sections")
    if not isinstance(required_sections, dict) or set(required_sections) != set(_SECTION_FIELDS):
        errors.append("error: artifact runtime required_sections must cover skill_result, provenance, freshness, definition_of_done, and authority")
    else:
        for section, expected in _SECTION_FIELDS.items():
            entry = required_sections.get(section)
            fields = entry.get("required_fields") if isinstance(entry, dict) else None
            if (
                not isinstance(fields, list)
                or not all(isinstance(field, str) for field in fields)
                or len(fields) != len(set(fields))
                or set(fields) != expected
            ):
                errors.append(f"error: artifact runtime {section}.required_fields drift")

    declared = set(external or []) | set(durable or [])
    if declared != artifact_types:
        errors.append("error: artifact runtime artifact coverage drift")
    if set(external or []) & set(durable or []):
        errors.append("error: artifact runtime external and durable artifacts overlap")

    schema_versions = artifact_runtime.get("artifact_schema_versions")
    if not isinstance(schema_versions, dict) or set(schema_versions) != set(durable or []):
        errors.append("error: artifact runtime artifact_schema_versions must cover every durable artifact exactly once")
    elif any(type(version) is not int or version < 1 for version in schema_versions.values()):
        errors.append("error: artifact runtime artifact_schema_versions values must be positive integers")
    state_semantics = artifact_runtime.get("state_semantics")
    if not isinstance(state_semantics, dict) or set(state_semantics) != set(durable or []):
        errors.append("error: artifact runtime state_semantics must cover every durable artifact exactly once")
    elif any(not isinstance(value, str) or value not in _STATE_VALUES for value in state_semantics.values()):
        errors.append("error: artifact runtime state_semantics contains an invalid value")

    allowed_state_semantics = artifact_runtime.get("allowed_state_semantics", {})
    if not isinstance(allowed_state_semantics, dict):
        errors.append("error: artifact runtime allowed_state_semantics must be a mapping")
        allowed_state_semantics = {}
    else:
        unknown_allowed = sorted(set(allowed_state_semantics) - set(durable or []))
        if unknown_allowed:
            errors.append(
                "error: artifact runtime allowed_state_semantics contains unknown artifacts: "
                + ", ".join(unknown_allowed),
            )
        for artifact, allowed in allowed_state_semantics.items():
            if not isinstance(allowed, list) or not allowed or len(allowed) != len(set(allowed)):
                errors.append(f"error: artifact runtime allowed_state_semantics.{artifact} must be a non-empty unique list")
            elif any(not isinstance(value, str) or value not in _STATE_VALUES for value in allowed):
                errors.append(f"error: artifact runtime allowed_state_semantics.{artifact} contains an invalid value")
            elif isinstance(state_semantics, dict) and state_semantics.get(artifact) not in allowed:
                errors.append(f"error: artifact runtime allowed_state_semantics.{artifact} must include the default state semantic")

    payload_types = artifact_runtime.get("payload_types")
    if not isinstance(payload_types, dict) or set(payload_types) != set(durable or []):
        errors.append("error: artifact runtime payload_types must cover every durable artifact exactly once")
    else:
        for artifact in durable or []:
            type_map = payload_types.get(artifact)
            if not isinstance(type_map, dict) or set(type_map) != set(artifact_schemas.get(artifact, [])):
                errors.append(f"error: artifact runtime payload_types.{artifact} must match artifact schema fields")
            elif not all(isinstance(field_type, str) and field_type in _PAYLOAD_TYPES for field_type in type_map.values()):
                errors.append(f"error: artifact runtime payload_types.{artifact} has invalid field types")

    ownership = runtime.get("artifact_ownership")
    if not isinstance(ownership, dict):
        errors.append("error: artifact runtime requires composition artifact_ownership")
        ownership = {}
    for artifact in durable or []:
        producers = [skill_id for skill_id, contract in skill_contracts.items() if artifact in contract.produces]
        unregistered = sorted(set(producers) - skill_ids)
        if unregistered:
            errors.append(f"error: durable artifact {artifact} has unregistered producers: {', '.join(unregistered)}")
        if not producers:
            errors.append(f"error: durable artifact {artifact} has no producer")
        ownership_spec = ownership.get(artifact)
        if not isinstance(ownership_spec, dict):
            errors.append(f"error: durable artifact {artifact} has no ownership contract")
            continue
        owners = ownership_spec.get("owners")
        if not isinstance(owners, list) or not owners or not all(isinstance(owner, str) for owner in owners):
            errors.append(f"error: durable artifact {artifact} ownership must declare owners")
        else:
            mode = ownership_spec.get("mode")
            if not isinstance(mode, str) or mode not in {"canonical", "shared", "external"}:
                errors.append(f"error: durable artifact {artifact} ownership mode is invalid")
            if mode == "canonical" and len(owners) != 1:
                errors.append(f"error: durable artifact {artifact} canonical ownership requires one owner")
            for owner in owners:
                if owner not in producers:
                    errors.append(f"error: durable artifact {artifact} owner {owner!r} is not a producer")
        delegates = ownership_spec.get("delegates", [])
        if not isinstance(delegates, list) or not all(isinstance(delegate, str) for delegate in delegates):
            errors.append(f"error: durable artifact {artifact} ownership delegates must be a list of strings")
        else:
            for delegate in delegates:
                if delegate not in producers:
                    errors.append(f"error: durable artifact {artifact} delegate {delegate!r} is not a producer")
    for skill_id, contract in skill_contracts.items():
        if contract.write_authority not in authority_levels:
            errors.append(f"error: {skill_id}: unknown write authority {contract.write_authority!r}")
    return errors


def validate_artifact_contracts(root: Path = ROOT) -> list[str]:
    """Validate universal runtime metadata coverage for every durable artifact."""
    try:
        artifact_runtime, runtime, authority_levels, skill_contracts, artifact_types, _schemas, _skills = _load_contract_data(root)
        return _validate_catalog(
            artifact_runtime,
            runtime,
            authority_levels,
            skill_contracts,
            artifact_types,
            set(_skills),
            _schemas,
        )
    except (OSError, TypeError, ValueError, *YAML_SAFETY_ERRORS) as exc:
        return [f"error: artifact runtime contracts: {exc}"]


def _required_sections(artifact_runtime: dict[str, Any]) -> dict[str, set[str]]:
    raw = artifact_runtime["required_sections"]
    return {
        section: set(require_mapping(raw[section], f"artifact_runtime.required_sections.{section}")["required_fields"])
        for section in _SECTION_FIELDS
    }


def validate_artifact_result(
    root: Path,
    artifact_type: str,
    result: object,
    *,
    producer_skill: str | None = None,
) -> list[str]:
    """Validate one durable artifact result against the canonical manifest."""
    try:
        if not isinstance(artifact_type, str) or not artifact_type:
            return ["error: artifact type must be a non-empty string"]
        if not isinstance(producer_skill, str) or not producer_skill:
            return [f"error: {artifact_type}: trusted producer context is required"]
        artifact_runtime, runtime, authority_levels, skill_contracts, artifact_types, artifact_schemas, skills = _load_contract_data(root)
        errors = _validate_catalog(
            artifact_runtime,
            runtime,
            authority_levels,
            skill_contracts,
            artifact_types,
            set(skills),
            artifact_schemas,
        )
        if errors:
            return errors
        external = set(artifact_runtime.get("external_input_artifacts", []))
        durable = set(artifact_runtime.get("durable_artifacts", []))
        if artifact_type in external:
            errors.append(f"error: {artifact_type}: external input is not a durable artifact result")
            return errors
        if artifact_type not in durable:
            errors.append(f"error: {artifact_type}: unknown durable artifact")
            return errors
        if not isinstance(result, dict):
            return [*errors, f"error: {artifact_type}: result must be a mapping"]
        payload = result.get("payload")
        if not isinstance(payload, dict):
            return [*errors, f"error: {artifact_type}: payload must be a mapping"]

        sections = _required_sections(artifact_runtime)
        parsed: dict[str, dict[str, Any]] = {}
        for section, fields in sections.items():
            value = result.get(section)
            if not isinstance(value, dict):
                errors.append(f"error: {artifact_type}: {section} must be a mapping")
                continue
            missing = sorted(fields - set(value))
            if missing:
                errors.append(f"error: {artifact_type}: {section} missing fields: {', '.join(missing)}")
            extra = sorted(set(value) - fields)
            if extra:
                errors.append(f"error: {artifact_type}: {section} contains undeclared fields: {', '.join(extra)}")
            parsed[section] = value

        envelope = parsed.get("skill_result")
        provenance = parsed.get("provenance")
        freshness = parsed.get("freshness")
        authority = parsed.get("authority")
        producer = None
        if envelope:
            if not isinstance(envelope.get("skill"), str):
                errors.append(f"error: {artifact_type}: result.skill must be a string")
            elif envelope["skill"] != producer_skill:
                errors.append(f"error: {artifact_type}: result.skill does not match trusted producer context")
            elif envelope["skill"] not in skill_contracts:
                errors.append(f"error: {artifact_type}: result.skill must identify a registered producer")
            else:
                producer = skill_contracts[envelope["skill"]]
                if artifact_type not in producer.produces:
                    errors.append(f"error: {artifact_type}: result.skill is not a producer")
                owner_spec = runtime.get("artifact_ownership", {}).get(artifact_type, {})
                declared_actors = set(owner_spec.get("owners", [])) | set(owner_spec.get("delegates", []))
                if envelope["skill"] not in declared_actors:
                    errors.append(f"error: {artifact_type}: result.skill is not an owner or delegate")
                if authority and authority.get("write_authority") != producer.write_authority:
                    errors.append(f"error: {artifact_type}: authority.write_authority does not match producer")
                registered = skills.get(envelope["skill"], {})
                registered_version = registered.get("version")
                if isinstance(registered_version, str) and isinstance(envelope.get("version"), str):
                    if envelope["version"].split(".", 1)[0] != registered_version.split(".", 1)[0]:
                        errors.append(f"error: {artifact_type}: result.version major is incompatible with registered skill version")
            if not isinstance(envelope.get("version"), str) or not is_semver(envelope["version"]):
                errors.append(f"error: {artifact_type}: result.version must be semantic version")
            if not isinstance(envelope.get("status"), str) or envelope.get("status") not in _COMPLETION_STATUSES:
                errors.append(f"error: {artifact_type}: invalid result.status")
            if not isinstance(envelope.get("confidence"), str) or envelope.get("confidence") not in _CONFIDENCE_VALUES:
                errors.append(f"error: {artifact_type}: invalid result.confidence")
            if not isinstance(envelope.get("evidence_status"), str) or envelope.get("evidence_status") not in _EVIDENCE_STATUSES:
                errors.append(f"error: {artifact_type}: invalid result.evidence_status")
            if envelope.get("artifact_schema_version") != artifact_runtime["artifact_schema_versions"][artifact_type]:
                errors.append(f"error: {artifact_type}: artifact schema version is unsupported")
            allowed_states = artifact_runtime.get("allowed_state_semantics", {}).get(artifact_type)
            if not isinstance(allowed_states, list):
                allowed_states = [artifact_runtime["state_semantics"][artifact_type]]
            if envelope.get("state_semantic") not in allowed_states:
                errors.append(f"error: {artifact_type}: state semantic does not match the artifact contract")
            artifacts = envelope.get("artifacts")
            if not isinstance(artifacts, list) or not all(isinstance(item, str) for item in artifacts):
                errors.append(f"error: {artifact_type}: result.artifacts must be a list of strings")
            else:
                if len(artifacts) != len(set(artifacts)):
                    errors.append(f"error: {artifact_type}: result.artifacts must not contain duplicates")
                unknown_artifacts = sorted(set(artifacts) - artifact_types)
                if unknown_artifacts:
                    errors.append(f"error: {artifact_type}: result.artifacts contains unknown types: {', '.join(unknown_artifacts)}")
                if artifact_type not in artifacts:
                    errors.append(f"error: {artifact_type}: result.artifacts must include the artifact type")
            source_revision = envelope.get("source_revision")
            if source_revision not in (None, "UNKNOWN") and (
                not isinstance(source_revision, str) or not source_revision
            ):
                errors.append(f"error: {artifact_type}: result.source_revision must be a string, null, or UNKNOWN")
            if not isinstance(envelope.get("blockers"), list):
                errors.append(f"error: {artifact_type}: result.blockers must be a list")
            next_skill = envelope.get("recommended_next_skill")
            if next_skill is not None and (not isinstance(next_skill, str) or next_skill not in skills):
                errors.append(f"error: {artifact_type}: result.recommended_next_skill must be a registered skill or null")
            if envelope.get("status") == "SUCCESS" and envelope.get("blockers"):
                errors.append(f"error: {artifact_type}: SUCCESS results must not contain blockers")
            if isinstance(envelope.get("status"), str) and envelope.get("status") in {"BLOCKED", "FAILED", "ESCALATED"} and not envelope.get("blockers"):
                errors.append(f"error: {artifact_type}: non-success results must declare blockers")
            if producer is not None and envelope.get("skill") == producer_skill:
                required_payload_fields = producer.produce_fields.get(
                    artifact_type,
                    artifact_schemas[artifact_type],
                )
                claimed_artifacts = envelope.get("artifacts")
                if isinstance(claimed_artifacts, list):
                    unproduced = sorted(set(claimed_artifacts) - set(producer.produces))
                    if unproduced:
                        errors.append(
                            f"error: {artifact_type}: result.artifacts are not all produced by the skill: {', '.join(unproduced)}",
                        )
                allowed_payload_fields = set(required_payload_fields)
                extra_payload = sorted(set(payload) - allowed_payload_fields)
                if extra_payload:
                    errors.append(
                        f"error: {artifact_type}: payload contains undeclared fields: {', '.join(extra_payload)}",
                    )
                missing_payload = sorted(allowed_payload_fields - set(payload))
                if missing_payload and envelope.get("status") == "SUCCESS":
                    errors.append(
                        f"error: {artifact_type}: payload missing schema fields: {', '.join(missing_payload)}",
                    )
                type_map = artifact_runtime["payload_types"][artifact_type]
                for field in required_payload_fields:
                    if field not in payload:
                        continue
                    expected = type_map.get(field)
                    if expected is None:
                        errors.append(f"error: {artifact_type}: payload field {field!r} has no declared type")
                        continue
                    value = payload[field]
                    matches = {
                        "mapping": isinstance(value, dict),
                        "list": isinstance(value, list),
                        "string": isinstance(value, str),
                        "boolean": isinstance(value, bool),
                        "integer": isinstance(value, int) and not isinstance(value, bool),
                    }[expected]
                    if not matches:
                        errors.append(f"error: {artifact_type}: payload.{field} must be {expected}")
        if provenance:
            provenance_revision = provenance.get("source_revision")
            if provenance_revision not in (None, "UNKNOWN") and (
                not isinstance(provenance_revision, str) or not provenance_revision
            ):
                errors.append(f"error: {artifact_type}: provenance.source_revision must be a string, null, or UNKNOWN")
            sources = provenance.get("sources")
            if not isinstance(sources, list) or not all(isinstance(source, str) and source for source in sources):
                errors.append(f"error: {artifact_type}: provenance.sources must be a list of strings")
        if freshness:
            for field in ("observed_at", "source_revision", "source_environment"):
                value = freshness.get(field)
                if value not in (None, "UNKNOWN") and (not isinstance(value, str) or not value):
                    errors.append(f"error: {artifact_type}: freshness.{field} must be a string, null, or UNKNOWN")
            observed_at = freshness.get("observed_at")
            if isinstance(observed_at, str) and observed_at != "UNKNOWN":
                try:
                    parsed_observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
                    if parsed_observed_at.tzinfo is None:
                        raise ValueError
                except ValueError:
                    errors.append(f"error: {artifact_type}: freshness.observed_at must be an ISO-8601 datetime with timezone")
        if envelope and (provenance or freshness):
            unknown_freshness = any(
                section.get(field) in (None, "UNKNOWN")
                for section, fields in (
                    (provenance, ("source_revision",)),
                    (freshness, ("observed_at", "source_revision", "source_environment")),
                )
                if section
                for field in fields
            )
            if unknown_freshness and (
                not isinstance(envelope.get("confidence"), str)
                or envelope.get("confidence") not in {"LOW", "UNKNOWN"}
            ):
                errors.append(f"error: {artifact_type}: unknown freshness requires LOW or UNKNOWN confidence")
        dod = parsed.get("definition_of_done")
        if dod:
            for field in ("required_artifacts", "required_checks", "completed_checks", "blocked_conditions"):
                value = dod.get(field)
                if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
                    errors.append(f"error: {artifact_type}: definition_of_done.{field} must be a list")
            required_artifacts = dod.get("required_artifacts")
            if isinstance(required_artifacts, list) and all(isinstance(item, str) and item for item in required_artifacts):
                if len(required_artifacts) != len(set(required_artifacts)):
                    errors.append(f"error: {artifact_type}: definition_of_done.required_artifacts must not contain duplicates")
                unknown_required = sorted(set(required_artifacts) - artifact_types)
                if unknown_required:
                    errors.append(f"error: {artifact_type}: definition_of_done.required_artifacts contains unknown types: {', '.join(unknown_required)}")
                if artifact_type not in required_artifacts:
                    errors.append(f"error: {artifact_type}: definition_of_done.required_artifacts must include the artifact type")
                if envelope and envelope.get("status") == "SUCCESS" and isinstance(envelope.get("artifacts"), list):
                    missing_required = sorted(set(required_artifacts) - set(envelope["artifacts"]))
                    if missing_required:
                        errors.append(f"error: {artifact_type}: SUCCESS result is missing DoD artifacts: {', '.join(missing_required)}")
            if isinstance(dod.get("required_checks"), list) and not dod["required_checks"]:
                errors.append(f"error: {artifact_type}: definition_of_done.required_checks must not be empty")
            if (
                isinstance(dod.get("required_checks"), list)
                and isinstance(dod.get("completed_checks"), list)
                and all(isinstance(item, str) for item in dod["required_checks"] + dod["completed_checks"])
            ):
                missing_checks = sorted(set(dod["required_checks"]) - set(dod["completed_checks"]))
                if missing_checks and envelope and envelope.get("status") == "SUCCESS":
                    errors.append(f"error: {artifact_type}: SUCCESS result is missing DoD checks: {', '.join(missing_checks)}")
            if not isinstance(dod.get("partial_result_behavior"), str) or not dod["partial_result_behavior"]:
                errors.append(f"error: {artifact_type}: definition_of_done.partial_result_behavior must be a non-empty string")
        if provenance and freshness:
            revisions = [
                envelope.get("source_revision") if envelope else None,
                provenance.get("source_revision"),
                freshness.get("source_revision"),
            ]
            known_revisions = [revision for revision in revisions if revision not in (None, "UNKNOWN")]
            unknown_count = len(revisions) - len(known_revisions)
            if known_revisions and unknown_count:
                errors.append(f"error: {artifact_type}: source revisions must be uniformly known or unknown")
            elif known_revisions and len(set(known_revisions)) != 1:
                errors.append(f"error: {artifact_type}: source revisions must match across the envelope")
        if authority:
            if not isinstance(authority.get("write_authority"), str) or authority.get("write_authority") not in authority_levels:
                errors.append(f"error: {artifact_type}: invalid authority.write_authority")
            owner_names = runtime.get("artifact_ownership", {}).get(artifact_type, {}).get("owners", [])
            if authority.get("canonical_owner") not in owner_names:
                errors.append(f"error: {artifact_type}: authority.canonical_owner is not an owner")
        return errors
    except (OSError, TypeError, ValueError, *YAML_SAFETY_ERRORS) as exc:
        return [f"error: {artifact_type}: artifact result validation unavailable: {exc}"]
