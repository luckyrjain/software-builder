from pathlib import Path

import pytest

from scripts.change_impact import finalize_impact
from scripts.registry.artifact_contracts import validate_artifact_result
from scripts.registry.canonical_manifest import load_canonical_manifest
from scripts.registry.result_envelope import (
    ResultEnvelopeError,
    artifact_schema_version,
    build_result_envelope,
)
from scripts.resilience_review import review_resilience

ROOT = Path(__file__).resolve().parents[2]

_RESILIENCE_SOURCE = {
    "ref": "repo:service.yaml",
    "authority": "repository",
    "kind": "repo_content",
    "observed_at": "2026-01-01T00:00:00Z",
    "source_revision": "a" * 40,
    "source_environment": "production",
    "derived_from": [],
    "dimensions": ["timeout_budgets"],
    "environment_sensitive_dimensions": [],
    "source_defined_application_code": False,
}


def _declared_versions() -> dict:
    manifest = load_canonical_manifest(ROOT)
    return manifest["contracts"]["platform"]["artifact_runtime"]["artifact_schema_versions"]


def test_producers_read_their_schema_version_from_the_canonical_manifest() -> None:
    # The two producers used to literal `1`. Binding them to the contract means the next bump of
    # either artifact cannot silently produce results the validator rejects.
    versions = _declared_versions()
    impact = finalize_impact(
        {
            "title": "t",
            "coverage_status": "PARTIAL",
            "evidence_refs": ["repo:x"],
            "assessment_target": {"source_type": "change", "head_revision_or_digest": "a" * 40},
        },
    ).to_envelope()
    assert impact["skill_result"]["artifact_schema_version"] == versions["change_impact_report"]
    resilience = review_resilience({"resilience_behavior": {}, "dependency_paths": []})
    assert (
        resilience["skill_result"]["artifact_schema_version"]
        == versions["resilience_review_report"]
    )


def test_artifact_schema_version_reads_each_artifact_independently() -> None:
    versions = _declared_versions()
    for artifact_type, expected in versions.items():
        assert artifact_schema_version(ROOT, artifact_type) == expected
    with pytest.raises(ResultEnvelopeError):
        artifact_schema_version(ROOT, "not_a_registered_artifact")


def test_sources_shape_follows_the_artifact_contract_not_the_producer() -> None:
    # change_impact_report carries no machine summary, so its envelope stores bare refs;
    # resilience_review_report does, so its envelope stores the typed source records.
    impact = finalize_impact(
        {
            "title": "t",
            "coverage_status": "PARTIAL",
            "evidence_refs": ["repo:x"],
            "assessment_target": {"source_type": "change", "head_revision_or_digest": "a" * 40},
        },
    ).to_envelope()
    assert all(isinstance(source, str) for source in impact["provenance"]["sources"])
    resilience = review_resilience(
        {
            "resilience_behavior": {"timeout_budgets": {"status": "PASS"}},
            "dependency_paths": ["payments"],
            "evidence": [dict(_RESILIENCE_SOURCE)],
            "assessment_target": {"kind": "service", "head_revision_or_digest": "a" * 40},
        },
    )
    assert all(isinstance(source, dict) for source in resilience["provenance"]["sources"])
    assert all("authority" in source for source in resilience["provenance"]["sources"])


def test_an_undeclared_environment_is_null_in_every_producer() -> None:
    impact = finalize_impact(
        {
            "title": "t",
            "coverage_status": "PARTIAL",
            "evidence_refs": ["repo:x"],
            "assessment_target": {"source_type": "change", "head_revision_or_digest": "a" * 40},
        },
    ).to_envelope()
    resilience = review_resilience({"resilience_behavior": {}, "dependency_paths": []})
    assert impact["freshness"]["source_environment"] is None
    assert resilience["freshness"]["source_environment"] is None


def test_the_builder_refuses_to_emit_an_envelope_its_contract_rejects() -> None:
    with pytest.raises(ResultEnvelopeError) as excinfo:
        build_result_envelope(
            skill="resilience-review",
            version="1.0.0",
            artifact_type="resilience_review_report",
            # A SUCCESS carrying blockers is exactly what the contract forbids.
            status="SUCCESS",
            confidence="UNKNOWN",
            evidence_status="UNKNOWN",
            state_semantic="proposed_state",
            source_revision="UNKNOWN",
            blockers=["dependency_paths"],
            sources=[],
            observed_at="UNKNOWN",
            source_environment=None,
            required_checks=["timeout_budgets"],
            completed_checks=[],
            partial_result_behavior="explicit UNKNOWN conditions",
            canonical_owner="resilience-review",
            payload={},
        )
    assert "must not contain blockers" in str(excinfo.value)


def test_the_builder_output_still_satisfies_the_standalone_validator() -> None:
    envelope = review_resilience(
        {
            "resilience_behavior": {"timeout_budgets": {"status": "PASS"}},
            "dependency_paths": ["payments"],
            "evidence": [dict(_RESILIENCE_SOURCE)],
            "assessment_target": {"kind": "service", "head_revision_or_digest": "a" * 40},
        },
    )
    assert validate_artifact_result(
        ROOT, "resilience_review_report", envelope, producer_skill="resilience-review"
    ) == []


def test_the_fixture_modules_answer_one_registry_question_one_way() -> None:
    # `consumes` used to exist three times, and one copy raised KeyError for an unregistered
    # skill while the others answered False. All three modules now resolve to the same function.
    from scripts.tests import artifact_v2_fixtures, envelope_fixtures

    assert artifact_v2_fixtures.consumes is envelope_fixtures.consumes
    assert envelope_fixtures.consumes("not-a-registered-skill", "change_impact_report") is False
    assert envelope_fixtures.consume_fields("not-a-registered-skill", "change_impact_report") == []
    assert envelope_fixtures.consumes("production-readiness-review", "change_impact_report") is True


def test_the_shared_assessment_context_declares_all_five_sections() -> None:
    from scripts.tests.envelope_fixtures import assessment_context
    from scripts.tests.production_readiness_fixtures import assessment_context_fixture

    assert set(assessment_context()) == {
        "assessment_target", "inputs", "input_provenance", "evidence_refs", "unresolved",
    }
    assert assessment_context()["assessment_target"] == {}
    # The production-readiness variant differs only in defaulting the target to its candidate.
    assert set(assessment_context_fixture()) == set(assessment_context())
    assert assessment_context_fixture()["assessment_target"] != {}
