"""Execution-owned trust classification for artifacts and embedded contexts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_AUTHORITIES = {"authoritative_host", "repository", "trusted_runtime", "caller", "model_knowledge"}


@dataclass(frozen=True)
class ArtifactTrust:
    acquisition: str
    producer_skill: str | None
    validator_passed: bool
    trusted_for_gate: bool


def classify_artifact_trust(
    *,
    artifact_type: str,
    acquisition: str,
    producer_skill: str | None,
    validator_passed: bool,
) -> ArtifactTrust:
    trusted_acquisition = acquisition in {"direct_child", "runtime_validated"}
    trusted = bool(artifact_type and producer_skill and validator_passed and trusted_acquisition)
    return ArtifactTrust(acquisition, producer_skill, validator_passed, trusted)


@dataclass(frozen=True)
class AssessmentContextTrust:
    acquisition: str
    parent_skill: str | None
    parent_execution_validated: bool
    _context: dict[str, Any]

    def effective_authority(self, input_name: str) -> str:
        provenance = self._context.get("input_provenance", {})
        entry = provenance.get(input_name, {}) if isinstance(provenance, dict) else {}
        claimed = entry.get("authority") if isinstance(entry, dict) else None
        if self.acquisition != "runtime_handoff" or not self.parent_execution_validated or not self.parent_skill:
            return "caller"
        return claimed if claimed in _AUTHORITIES else "caller"


def classify_assessment_context_trust(
    context: object,
    *,
    runtime_metadata: object,
) -> AssessmentContextTrust:
    safe_context = context if isinstance(context, dict) else {}
    metadata = runtime_metadata if isinstance(runtime_metadata, dict) else {}
    acquisition = metadata.get("acquisition")
    if acquisition not in {"runtime_handoff", "caller_supplied"}:
        acquisition = "caller_supplied"
    parent_skill = metadata.get("parent_skill") if isinstance(metadata.get("parent_skill"), str) else None
    validated = metadata.get("parent_execution_validated") is True
    return AssessmentContextTrust(acquisition, parent_skill, validated, safe_context)
