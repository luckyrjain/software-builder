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
    if machine_artifact and not document_content and not document_ref:
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
