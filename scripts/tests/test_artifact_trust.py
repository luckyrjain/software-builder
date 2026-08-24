from scripts.registry.artifact_trust import (
    classify_artifact_trust,
    classify_assessment_context_trust,
)


def test_caller_supplied_artifact_never_becomes_gate_trusted() -> None:
    trust = classify_artifact_trust(
        artifact_type="security_review_report",
        acquisition="caller_supplied",
        producer_skill="security-review",
        validator_passed=True,
    )
    assert trust.trusted_for_gate is False


def test_direct_child_requires_runtime_producer_identity_and_validation() -> None:
    trust = classify_artifact_trust(
        artifact_type="security_review_report",
        acquisition="direct_child",
        producer_skill="security-review",
        validator_passed=True,
    )
    assert trust.trusted_for_gate is True


def test_caller_context_cannot_self_claim_authoritative_host() -> None:
    ctx = {"input_provenance": {"rollback_plan": {"authority": "authoritative_host"}}}
    trust = classify_assessment_context_trust(
        ctx,
        runtime_metadata={"acquisition": "caller_supplied", "parent_execution_validated": False},
    )
    assert trust.effective_authority("rollback_plan") == "caller"


def test_validated_runtime_handoff_preserves_but_does_not_upgrade_authority() -> None:
    ctx = {"input_provenance": {"rollback_plan": {"authority": "repository"}}}
    trust = classify_assessment_context_trust(
        ctx,
        runtime_metadata={
            "acquisition": "runtime_handoff",
            "parent_skill": "production-readiness-review",
            "parent_execution_validated": True,
        },
    )
    assert trust.effective_authority("rollback_plan") == "repository"
