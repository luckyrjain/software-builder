"""One builder for the runtime result envelope every assessment skill returns.

skills.yaml's `contracts.platform` section declares six invariant sections -- `skill_result`,
`provenance`, `freshness`, `definition_of_done`, `authority`, `payload` -- and
`artifact_contracts.validate_artifact_result` checks them. Between those two lived one
hand-written literal per producer, so the contract could drift silently in either direction.

This module is the adapter between them: producers pass only the parts that genuinely vary per
skill, and the builder owns the section shapes, reads the artifact's schema version from the
canonical manifest instead of literalling it, and validates its own output before returning --
a producer that would emit a rejected artifact fails here, at the producer, rather than at
whichever consumer happens to validate first.

Two shapes vary *by artifact type*, not by producer taste, and are resolved from the contract
rather than left to the caller:

* `provenance.sources` is a list of typed source records for an artifact that carries the common
  machine summary, and a list of bare `ref` strings for one that does not -- exactly the split
  `validate_artifact_result` enforces.
* `freshness.source_environment` is `None` when no environment is known. The validator treats
  `None` and `"UNKNOWN"` identically, so one of them is redundant; `None` is kept because it is
  also what the typed source records use for the same "not declared" state.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.registry.artifact_contracts import (
    artifact_schema_version as _declared_artifact_schema_version,
    validate_artifact_result,
)
from scripts.registry.composition_contracts import load_contracts
from scripts.registry.machine_summary import COMMON_MACHINE_SUMMARY_FIELDS

ROOT = Path(__file__).resolve().parents[2]

SOURCE_RECORD_FIELDS = (
    "ref",
    "authority",
    "kind",
    "observed_at",
    "source_revision",
    "source_environment",
    "derived_from",
)


class ResultEnvelopeError(RuntimeError):
    """A producer assembled an envelope its own artifact contract rejects."""


def artifact_schema_version(root: Path, artifact_type: str) -> int:
    """An artifact's declared schema version, as `ResultEnvelopeError`-flavoured lookup.

    `artifact_contracts` owns the reading of
    `contracts.platform.artifact_runtime.artifact_schema_versions` -- the same declaration
    `validate_artifact_result` checks an envelope against, so there is one reader and a bump
    cannot reach the validator without also reaching producers. This adapter only re-raises the
    lookup's `ValueError` as this module's own error type, so a producer assembling an envelope
    catches one exception class for every way the assembly can fail.
    """
    try:
        return _declared_artifact_schema_version(root, artifact_type)
    except ValueError as exc:
        raise ResultEnvelopeError(f"{artifact_type}: {exc}") from exc


def _carries_machine_summary(root: Path, artifact_type: str) -> bool:
    _, artifact_schemas, _, _ = load_contracts(root / "skills.yaml")
    return set(artifact_schemas.get(artifact_type, [])) >= COMMON_MACHINE_SUMMARY_FIELDS


def _source_environment(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _projected_sources(sources: Sequence[Mapping[str, Any]], *, typed: bool) -> list[Any]:
    if typed:
        return [
            {field: source.get(field) for field in SOURCE_RECORD_FIELDS}
            for source in sources
            if isinstance(source, Mapping)
        ]
    return [source["ref"] for source in sources if isinstance(source, Mapping) and source.get("ref")]


def build_result_envelope(
    *,
    skill: str,
    version: str,
    artifact_type: str,
    status: str,
    confidence: str,
    evidence_status: str,
    state_semantic: str,
    source_revision: object,
    blockers: Sequence[str],
    sources: Sequence[Mapping[str, Any]],
    observed_at: object,
    source_environment: object,
    required_checks: Sequence[str],
    completed_checks: Sequence[str],
    partial_result_behavior: str,
    canonical_owner: str,
    payload: Mapping[str, Any],
    write_authority: str = "read-only",
    recommended_next_skill: str | None = None,
    artifacts: Sequence[str] | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Assemble and validate one durable artifact result.

    `sources` is always the producer's own typed source records; the builder projects them into
    whatever shape this artifact's contract declares. Raises `ResultEnvelopeError` when the
    assembled envelope does not validate, so a producer cannot ship a rejected artifact.
    """
    declared_artifacts = list(artifacts) if artifacts is not None else [artifact_type]
    envelope = {
        "skill_result": {
            "skill": skill,
            "version": version,
            "status": status,
            "confidence": confidence,
            "source_revision": source_revision,
            "evidence_status": evidence_status,
            "artifacts": declared_artifacts,
            "blockers": list(blockers),
            "recommended_next_skill": recommended_next_skill,
            "artifact_schema_version": artifact_schema_version(root, artifact_type),
            "state_semantic": state_semantic,
        },
        "provenance": {
            "source_revision": source_revision,
            "sources": _projected_sources(
                sources, typed=_carries_machine_summary(root, artifact_type)
            ),
        },
        "freshness": {
            "observed_at": observed_at,
            "source_revision": source_revision,
            "source_environment": _source_environment(source_environment),
        },
        "definition_of_done": {
            "required_artifacts": [artifact_type],
            "required_checks": list(required_checks),
            "completed_checks": list(completed_checks),
            "blocked_conditions": list(blockers),
            "partial_result_behavior": partial_result_behavior,
        },
        "authority": {
            "write_authority": write_authority,
            "canonical_owner": canonical_owner,
        },
        "payload": dict(payload),
    }
    errors = validate_artifact_result(root, artifact_type, envelope, producer_skill=skill)
    if errors:
        raise ResultEnvelopeError(f"{artifact_type}: " + "; ".join(errors))
    return envelope
