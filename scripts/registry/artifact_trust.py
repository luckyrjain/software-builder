"""Execution-owned trust classification for artifacts and embedded contexts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

_AUTHORITIES = {"authoritative_host", "repository", "trusted_runtime", "caller", "model_knowledge"}
_RUNTIME_HANDOFF_TOKEN = object()


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
    _trusted_authorities: Mapping[str, str]

    def effective_authority(self, input_name: str) -> str:
        # "caller" here covers three distinct causes (no handoff offered, a handoff that doesn't
        # name this input, or a rejected/forged handoff) collapsed to one value on purpose: none
        # of them may ever read as elevated, and the doctrine is UNKNOWN/least-trust over
        # speculation about which cause applies.
        if self.acquisition != "runtime_handoff" or not self.parent_execution_validated or not self.parent_skill:
            return "caller"
        authority = self._trusted_authorities.get(input_name)
        return authority if authority in _AUTHORITIES else "caller"


@dataclass(frozen=True)
class _RuntimeHandoffMetadata:
    """Opaque metadata issued by the composition runtime, not by a caller payload."""

    parent_skill: str
    trusted_authorities: Mapping[str, str]
    _token: object


def _issue_runtime_handoff_metadata(
    *, parent_skill: str, trusted_authorities: Mapping[str, str] | None = None
) -> _RuntimeHandoffMetadata:
    """Create runtime-owned metadata after the parent has validated its evidence."""
    supplied = trusted_authorities if isinstance(trusted_authorities, Mapping) else {}
    authorities = {
        name: authority
        for name, authority in supplied.items()
        if isinstance(name, str) and isinstance(authority, str) and authority in _AUTHORITIES
    }
    return _RuntimeHandoffMetadata(
        parent_skill=parent_skill,
        trusted_authorities=MappingProxyType(authorities),
        _token=_RUNTIME_HANDOFF_TOKEN,
    )


def classify_assessment_context_trust(
    context: object,
    *,
    runtime_metadata: object,
) -> AssessmentContextTrust:
    # `context` is reserved for a future content-based check; trust is decided by
    # `runtime_metadata` alone today. Don't shape a caller's context to try to influence this.
    del context
    if isinstance(runtime_metadata, _RuntimeHandoffMetadata) and runtime_metadata._token is _RUNTIME_HANDOFF_TOKEN:
        return AssessmentContextTrust(
            "runtime_handoff",
            runtime_metadata.parent_skill,
            True,
            runtime_metadata.trusted_authorities,
        )
    return AssessmentContextTrust("caller_supplied", None, False, MappingProxyType({}))
