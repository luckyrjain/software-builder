"""Result-envelope fixtures shared by every assessment test module.

The envelope shape and the registry lookups behind it are one domain concept, so they get one
fixture definition here rather than a copy per skill's fixture module. The three skill-specific
fixture modules keep only what is genuinely skill-specific and import these.

`consumes` uses the `.get` semantic deliberately: an unregistered skill id answers `False`, so a
coverage assertion reports "this skill does not consume that artifact" instead of raising a
`KeyError` that reads as a broken test. Two of the three previous copies already behaved this
way; the third raised, so the same question had two answers.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.registry.artifact_contracts import (
    artifact_schema_version as _declared_artifact_schema_version,
)
from scripts.registry.canonical_manifest import load_canonical_manifest

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REVISION = "a" * 40


@lru_cache(maxsize=1)
def _manifest() -> dict[str, Any]:
    """The canonical manifest, loaded once per test session instead of once per lookup.

    Treat the result as read-only: every helper here derives a fresh value from it.
    """
    return load_canonical_manifest(ROOT)


def _skill_contract(skill_id: str) -> Mapping[str, Any]:
    return _manifest()["contracts"]["composition"]["skills"].get(skill_id, {})


@lru_cache(maxsize=None)
def artifact_schema_version(artifact_type: str) -> int:
    """The version a test should expect on an envelope, read the way production reads it.

    Deliberately not a second walk of the manifest: a fixture that re-derived the version from
    its own path into `contracts.platform` could keep agreeing with a producer that had drifted
    away from `validate_artifact_result`'s declaration. Cached per artifact type for the same
    reason `_manifest()` is -- the shared reader re-parses the registry on every call.
    """
    return _declared_artifact_schema_version(ROOT, artifact_type)


def consumes(skill_id: str, artifact_type: str) -> bool:
    return artifact_type in _skill_contract(skill_id).get("consumes", [])


def consume_fields(skill_id: str, artifact_type: str) -> list[str]:
    return list(_skill_contract(skill_id).get("consume_fields", {}).get(artifact_type, []))


def assessment_context(
    *,
    assessment_target: Mapping[str, Any] | None = None,
    inputs: Mapping[str, Any] | None = None,
    input_provenance: Mapping[str, Any] | None = None,
    evidence_refs: Sequence[str] | None = None,
    unresolved: Sequence[str] | None = None,
) -> dict[str, Any]:
    """The five-key assessment-context envelope, with every section independently overridable."""
    return {
        "assessment_target": dict(assessment_target or {}),
        "inputs": dict(inputs or {}),
        "input_provenance": dict(input_provenance or {}),
        "evidence_refs": list(evidence_refs or []),
        "unresolved": list(unresolved or []),
    }
