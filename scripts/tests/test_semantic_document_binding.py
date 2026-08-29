from __future__ import annotations

from pathlib import Path

from scripts.registry.assessment_target import canonical_text_digest
from scripts.registry.artifact_contracts import validate_artifact_result
from scripts.registry.semantic_document import (
    is_sha256_digest,
    resolve_architecture_design_input,
    resolve_system_design_prd_input,
)
from scripts.tests.artifact_v2_fixtures import machine_summary_fixture


ROOT = Path(__file__).resolve().parents[2]


def _target(source_type: str, text: str, source_ref: str | None = None) -> dict[str, str | None]:
    return {
        "repo": "github.com/acme/payments",
        "service": "payments",
        "environment": "production",
        "source_type": source_type,
        "base_revision": "a" * 40,
        "head_revision_or_digest": "b" * 40,
        "source_artifact_ref": source_ref,
        "source_artifact_digest": canonical_text_digest(text),
    }


def _result(
    *,
    artifact_type: str,
    skill: str,
    version: str,
    payload: dict,
) -> dict:
    summary = machine_summary_fixture()
    return {
        "skill_result": {
            "skill": skill,
            "version": version,
            "status": "SUCCESS",
            "confidence": "HIGH",
            "source_revision": "a" * 40,
            "evidence_status": "OBSERVED",
            "artifacts": [artifact_type],
            "blockers": [],
            "recommended_next_skill": None,
            "artifact_schema_version": 2,
            "state_semantic": "proposed_state",
        },
        "provenance": summary["provenance"],
        "freshness": {
            "observed_at": "2026-08-24T00:00:00Z",
            "source_revision": "a" * 40,
            "source_environment": "repository",
        },
        "definition_of_done": {
            "required_artifacts": [artifact_type],
            "required_checks": ["assessment_complete"],
            "completed_checks": ["assessment_complete"],
            "blocked_conditions": [],
            "partial_result_behavior": "return PARTIAL with blockers",
        },
        "authority": {"write_authority": "read-only", "canonical_owner": skill},
        "payload": payload,
    }


def _prd_result(text: str, *, source_ref: str | None = None) -> dict:
    summary = machine_summary_fixture()
    return _result(
        artifact_type="prd_report",
        skill="prd-architect",
        version="1.3.0",
        payload={
            "title": "Checkout",
            "build_readiness": "READY",
            "depth": "standard",
            "response_mode": "document",
            **summary["payload"],
            "assessment_target": _target("prd", text, source_ref),
        },
    )


def _system_design_result(text: str) -> dict:
    summary = machine_summary_fixture()
    return _result(
        artifact_type="system_design_spec",
        skill="system-design",
        version="1.2.0",
        payload={
            "title": "Checkout",
            "readiness": "Ready to implement",
            **summary["payload"],
            "assessment_target": _target("system_design", text),
        },
    )


def test_prd_v2_binds_machine_gate_to_full_prd_digest() -> None:
    text = "Final PRD\nRequirement A"
    result = _prd_result(text)

    assert validate_artifact_result(ROOT, "prd_report", result, producer_skill="prd-architect") == []
    assert result["payload"]["assessment_target"]["source_artifact_digest"] == canonical_text_digest(text)


def test_prd_v2_rejects_missing_semantic_document_digest() -> None:
    result = _prd_result("Final PRD\nRequirement A")
    result["payload"]["assessment_target"]["source_artifact_digest"] = None

    errors = validate_artifact_result(ROOT, "prd_report", result, producer_skill="prd-architect")

    assert any("source_artifact_digest" in error for error in errors)


def test_system_design_v2_rejects_wrong_semantic_source_type() -> None:
    result = _system_design_result("System Design\nComponent A")
    result["payload"]["assessment_target"]["source_type"] = "prd"

    errors = validate_artifact_result(ROOT, "system_design_spec", result, producer_skill="system-design")

    assert any("source_type" in error for error in errors)


def test_system_design_rejects_prd_summary_with_mismatched_full_document() -> None:
    report = _prd_result("Final PRD\nRequirement A")

    resolved = resolve_system_design_prd_input(report, full_prd="Final PRD\nRequirement B")

    assert resolved.status == "BLOCKED"
    assert "digest" in resolved.reason.lower()


def test_prd_v2_rejects_mixed_case_semantic_document_digest() -> None:
    text = "Final PRD\nRequirement A"
    result = _prd_result(text)
    result["payload"]["assessment_target"]["source_artifact_digest"] = canonical_text_digest(text).upper()

    errors = validate_artifact_result(ROOT, "prd_report", result, producer_skill="prd-architect")

    assert any("source_artifact_digest" in error for error in errors)


def test_system_design_resolve_rejects_mixed_case_digest_even_when_bytes_match() -> None:
    report = _prd_result("Final PRD\nRequirement A")
    report["payload"]["assessment_target"]["source_artifact_digest"] = report["payload"][
        "assessment_target"
    ]["source_artifact_digest"].upper()

    resolved = resolve_system_design_prd_input(report, full_prd="Final PRD\nRequirement A")

    assert resolved.status == "BLOCKED"


def test_is_sha256_digest_rejects_mixed_and_upper_case() -> None:
    lower = canonical_text_digest("anything")

    assert is_sha256_digest(lower) is True
    assert is_sha256_digest(lower.upper()) is False
    assert is_sha256_digest(lower[:-1] + lower[-1].upper()) is False


def test_system_design_accepts_exact_prd_document_binding() -> None:
    text = "Final PRD\nRequirement A"
    report = _prd_result(text)

    assert resolve_system_design_prd_input(report, full_prd=text).status == "READY"


def test_system_design_rejects_contradictory_immutable_prd_ref_even_with_same_digest() -> None:
    text = "Final PRD\nRequirement A"
    report = _prd_result(text, source_ref="docs/prd.md@rev-a")

    resolved = resolve_system_design_prd_input(
        report,
        full_prd=text,
        source_ref="docs/prd.md@rev-b",
    )

    assert resolved.status == "BLOCKED"


def test_architecture_rejects_mismatched_full_system_design() -> None:
    text = "System Design\nComponent A"
    spec = _system_design_result(text)

    resolved = resolve_architecture_design_input(spec, full_design="System Design\nComponent B")

    assert resolved.status == "BLOCKED"


def test_architecture_accepts_exact_system_design_binding() -> None:
    text = "System Design\nComponent A"
    spec = _system_design_result(text)

    assert resolve_architecture_design_input(spec, full_design=text).status == "READY"
