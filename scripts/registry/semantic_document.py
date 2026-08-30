"""Fail-closed identity binding for machine summaries and semantic documents."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any

from scripts.registry.assessment_target import canonical_text_digest


_TARGET_FIELDS = frozenset(
    {
        "repo",
        "service",
        "environment",
        "source_type",
        "base_revision",
        "head_revision_or_digest",
        "source_artifact_ref",
        "source_artifact_digest",
    }
)
_SOURCE_TYPES = {"prd_report": "prd", "system_design_spec": "system_design"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SemanticDocumentResolution:
    status: str
    reason: str = ""


def _normalized_ref(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return unicodedata.normalize("NFC", value.strip()) or None


def _target(payload: object) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(payload, dict):
        return None, ["error: assessment_target must be a mapping"]
    value = payload.get("assessment_target")
    if not isinstance(value, dict):
        return None, ["error: assessment_target must be a mapping"]
    errors: list[str] = []
    missing = sorted(_TARGET_FIELDS - set(value))
    extra = sorted(set(value) - _TARGET_FIELDS)
    if missing:
        errors.append("error: assessment_target missing fields: " + ", ".join(missing))
    if extra:
        errors.append("error: assessment_target contains undeclared fields: " + ", ".join(extra))
    source_type = value.get("source_type")
    if not isinstance(source_type, str) or not source_type.strip():
        errors.append("error: assessment_target.source_type must be a non-empty string")
    digest = value.get("source_artifact_digest")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        errors.append("error: assessment_target.source_artifact_digest must be an exact lower-case SHA-256 hex digest")
    for field in _TARGET_FIELDS - {"source_type", "source_artifact_digest"}:
        current = value.get(field)
        if current is not None and not isinstance(current, str):
            errors.append(f"error: assessment_target.{field} must be a string or null")
    for field in ("repo", "service", "environment", "base_revision", "head_revision_or_digest", "source_artifact_ref"):
        current = value.get(field)
        if isinstance(current, str) and not current.strip():
            errors.append(f"error: assessment_target.{field} must be non-empty when present")
    return value, errors


def validate_semantic_artifact_target(artifact_type: str, payload: object) -> list[str]:
    """Validate the full-document identity fields required by B1 semantic artifacts."""
    expected_source_type = _SOURCE_TYPES.get(artifact_type)
    if expected_source_type is None:
        return []
    target, errors = _target(payload)
    if target is None:
        return errors
    if target.get("source_type") != expected_source_type:
        errors.append(
            f"error: {artifact_type}: assessment_target.source_type must be {expected_source_type!r}"
        )
    return errors


def _resolve(
    artifact_type: str,
    report: object,
    full_document: object,
    source_ref: object,
) -> SemanticDocumentResolution:
    if not isinstance(report, dict) or not isinstance(report.get("payload"), dict):
        return SemanticDocumentResolution("BLOCKED", "machine artifact payload is missing")
    payload = report["payload"]
    target = payload.get("assessment_target")
    if not isinstance(target, dict):
        return SemanticDocumentResolution("BLOCKED", "assessment target is missing")
    if not isinstance(full_document, str) or not full_document:
        return SemanticDocumentResolution("BLOCKED", "complete semantic document is missing")
    expected_type = _SOURCE_TYPES[artifact_type]
    if target.get("source_type") != expected_type:
        return SemanticDocumentResolution("BLOCKED", "assessment target source type mismatch")
    digest = target.get("source_artifact_digest")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        return SemanticDocumentResolution("BLOCKED", "full-document digest is missing or invalid")
    if digest != canonical_text_digest(full_document):
        return SemanticDocumentResolution("BLOCKED", "full-document digest mismatch")
    target_ref = _normalized_ref(target.get("source_artifact_ref"))
    resolved_ref = _normalized_ref(source_ref)
    if target_ref is not None and resolved_ref is not None and target_ref != resolved_ref:
        return SemanticDocumentResolution("BLOCKED", "immutable source reference mismatch")
    return SemanticDocumentResolution("READY")


def resolve_system_design_prd_input(
    report: object,
    *,
    full_prd: object,
    source_ref: object = None,
) -> SemanticDocumentResolution:
    return _resolve("prd_report", report, full_prd, source_ref)


def resolve_architecture_design_input(
    spec: object,
    *,
    full_design: object,
    source_ref: object = None,
) -> SemanticDocumentResolution:
    return _resolve("system_design_spec", spec, full_design, source_ref)


def is_sha256_digest(value: object) -> bool:
    """Expose strict digest validation for focused contract tests.

    Requires an exact lower-case 64-character hex digest per the design's
    canonical target identity rule; a mixed/upper-case string is rejected
    rather than silently accepted as an alias.
    """
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None
