"""Fixtures for artifact-v2 machine-summary contract tests."""

from __future__ import annotations

from typing import Any


def finding(identifier: str, *, evidence_refs: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": identifier,
        "category": "security",
        "summary": "authentication gap",
        "blocking": True,
        "evidence_status": "OBSERVED",
        "evidence_refs": ["repo:diff"] if evidence_refs is None else evidence_refs,
    }


def machine_summary_fixture(
    *,
    assessment_target: dict[str, Any] | None = None,
    normalized_decision: str = "PASS",
    findings: list[dict[str, Any]] | None = None,
    conditions: list[dict[str, Any]] | None = None,
    required_actions: list[dict[str, Any]] | None = None,
    evidence_refs: list[str] | None = None,
    provenance_sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a valid artifact-v2 summary envelope unless overridden."""
    default_ref = "repo:diff"
    return {
        "payload": {
            "assessment_target": assessment_target
            or {"kind": "repository", "repo": "acme/service"},
            "normalized_decision": normalized_decision,
            "findings": [] if findings is None else findings,
            "conditions": [] if conditions is None else conditions,
            "required_actions": [] if required_actions is None else required_actions,
            "evidence_refs": [default_ref] if evidence_refs is None else evidence_refs,
        },
        "provenance": {
            "source_revision": "a" * 40,
            "sources": [
                {
                    "ref": default_ref,
                    "authority": "repository",
                    "kind": "repo_content",
                    "observed_at": "2026-08-23T00:00:00Z",
                    "source_revision": "a" * 40,
                    "source_environment": "repository",
                    "derived_from": [],
                }
            ]
            if provenance_sources is None
            else provenance_sources,
        },
    }
