"""Resolve embedded child inputs without allowing summary or authority laundering."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from scripts.registry.assessment_target import normalize_environment_identity, normalize_repo_identity, normalize_service_identity


@dataclass(frozen=True)
class EmbeddedInputResolution:
    status: str
    missing: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    input_provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DatabaseInputResolution:
    status: str
    schema: str | None = None
    migration_script: str | None = None
    queries: str | None = None
    query_plan: Any = None
    db_engine: str | None = None
    override_verdict: str | None = None


@dataclass(frozen=True)
class SpecialistInputResolution:
    status: str
    missing: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    input_provenance: dict[str, Any] = field(default_factory=dict)


def _specialist_context_inputs(assessment_context: object) -> tuple[dict[str, Any], dict[str, Any]] | None:
    if not isinstance(assessment_context, dict):
        return None
    if not isinstance(assessment_context.get("assessment_target"), dict):
        return None
    inputs = assessment_context.get("inputs")
    if not isinstance(inputs, dict):
        return None
    provenance = assessment_context.get("input_provenance")
    if not isinstance(provenance, dict):
        return None
    if not isinstance(assessment_context.get("evidence_refs"), list):
        return None
    if not isinstance(assessment_context.get("unresolved"), list):
        return None
    return inputs, dict(provenance)


def parse_capacity_inputs(assessment_context: object) -> SpecialistInputResolution:
    """Map embedded capacity inputs while retaining demand and horizon hard stops."""
    parsed = _specialist_context_inputs(assessment_context)
    if parsed is None:
        return SpecialistInputResolution("BLOCKED", ["assessment_context.inputs"])
    inputs, provenance = parsed
    missing = [
        field_name
        for field_name in ("demand_data", "forecast_horizon")
        if inputs.get(field_name) is None or (isinstance(inputs.get(field_name), str) and not inputs[field_name].strip())
    ]
    if missing:
        return SpecialistInputResolution("BLOCKED", missing, dict(inputs), provenance)
    return SpecialistInputResolution("RESOLVED", [], dict(inputs), provenance)


def parse_dependency_inputs(assessment_context: object) -> SpecialistInputResolution:
    """Map embedded dependency inputs without inventing a version triplet."""
    parsed = _specialist_context_inputs(assessment_context)
    if parsed is None:
        return SpecialistInputResolution("BLOCKED", ["assessment_context.inputs"])
    inputs, provenance = parsed
    missing = [
        field_name
        for field_name in ("dependency_name", "current_version", "target_version")
        if not isinstance(inputs.get(field_name), str) or not inputs[field_name].strip()
    ]
    if missing:
        return SpecialistInputResolution("BLOCKED", missing, dict(inputs), provenance)
    return SpecialistInputResolution("RESOLVED", [], dict(inputs), provenance)


def parse_database_inputs(assessment_context: object) -> DatabaseInputResolution:
    """Map embedded database-review inputs without interpreting text as instructions."""
    if not isinstance(assessment_context, dict):
        return DatabaseInputResolution("BLOCKED")
    inputs = assessment_context.get("inputs")
    if not isinstance(inputs, dict):
        return DatabaseInputResolution("BLOCKED")
    values = {
        "schema": inputs.get("schema"),
        "migration_script": inputs.get("migration_script"),
        "queries": inputs.get("queries"),
        "query_plan": inputs.get("query_plan"),
        "db_engine": inputs.get("db_engine"),
    }
    if not any(isinstance(values[key], str) and values[key].strip() for key in ("schema", "migration_script", "queries")):
        return DatabaseInputResolution("BLOCKED")
    return DatabaseInputResolution(
        "RESOLVED",
        schema=values["schema"] if isinstance(values["schema"], str) else None,
        migration_script=values["migration_script"] if isinstance(values["migration_script"], str) else None,
        queries=values["queries"] if isinstance(values["queries"], str) else None,
        query_plan=values["query_plan"],
        db_engine=values["db_engine"] if isinstance(values["db_engine"], str) else None,
    )


def resolve_embedded_inputs(
    *,
    target_skill: str | None = None,
    machine_artifact: dict[str, Any] | None = None,
    document_content: str | None = None,
    document_ref: str | None = None,
    execution_context: dict[str, Any] | None = None,
    assessment_context: dict[str, Any] | None = None,
    top_level: dict[str, Any] | None = None,
) -> EmbeddedInputResolution:
    del execution_context
    missing: list[str] = []
    if machine_artifact is not None and not isinstance(machine_artifact, dict):
        return EmbeddedInputResolution("BLOCKED", ["machine_artifact"])
    has_document_content = isinstance(document_content, str) and bool(document_content)
    has_document_ref = isinstance(document_ref, str) and bool(document_ref)
    if isinstance(machine_artifact, dict) and machine_artifact and not has_document_content and not has_document_ref:
        artifact_type = machine_artifact.get("artifact_type")
        if artifact_type == "prd_report" or target_skill == "system-design":
            missing.append("full_prd_content_or_ref")
        elif artifact_type == "system_design_spec" or target_skill == "architecture-review":
            missing.append("full_system_design_content_or_ref")
    context_inputs = assessment_context.get("inputs", {}) if isinstance(assessment_context, dict) else {}
    if not isinstance(context_inputs, dict):
        return EmbeddedInputResolution("BLOCKED", ["assessment_context.inputs"])
    top = top_level if isinstance(top_level, dict) else {}
    conflicts = [key for key in set(context_inputs) & set(top) if context_inputs[key] != top[key]]
    if conflicts:
        return EmbeddedInputResolution("CONFLICTED", sorted(conflicts))
    merged = dict(context_inputs)
    merged.update(top)
    provenance = assessment_context.get("input_provenance", {}) if isinstance(assessment_context, dict) else {}
    provenance = dict(provenance) if isinstance(provenance, dict) else {}
    if missing:
        return EmbeddedInputResolution("BLOCKED", missing, merged, provenance)
    return EmbeddedInputResolution("RESOLVED", [], merged, provenance)


def validate_embedded_result_target(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return ["assessment target must be a mapping"]
    errors: list[str] = []
    for field in ("repo", "service", "environment", "source_type", "base_revision", "head_revision_or_digest", "source_artifact_ref", "source_artifact_digest"):
        left, right = expected.get(field), actual.get(field)
        if field == "repo" and isinstance(left, str) and isinstance(right, str):
            left, right = normalize_repo_identity(left), normalize_repo_identity(right)
        elif field == "service" and isinstance(left, str) and isinstance(right, str):
            left, right = normalize_service_identity(left), normalize_service_identity(right)
        elif field == "environment" and isinstance(left, str) and isinstance(right, str):
            left, right = normalize_environment_identity(left), normalize_environment_identity(right)
        else:
            if isinstance(left, str):
                left = left.strip()
            if isinstance(right, str):
                right = right.strip()
        if left != right:
            errors.append(f"assessment target mismatch: {field}")
    return errors
