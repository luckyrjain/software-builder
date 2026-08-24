from scripts.registry.artifact_trust import classify_assessment_context_trust
from scripts.registry.embedded_context import resolve_embedded_inputs, validate_embedded_result_target


def assessment_context(**overrides):
    context = {"assessment_target": {}, "inputs": {}, "input_provenance": {}, "evidence_refs": [], "unresolved": []}
    context.update(overrides)
    return context


def assessment_target(**overrides):
    target = {"repo": "github.com/acme/payments", "head_revision_or_digest": "a" * 40}
    target.update(overrides)
    return target


def test_system_design_blocks_on_machine_prd_summary_without_full_prd() -> None:
    result = resolve_embedded_inputs(target_skill="system-design", machine_artifact={"artifact_type": "prd_report", "payload": {"title": "Checkout", "build_readiness": "READY"}})
    assert result.status == "BLOCKED"
    assert result.missing == ["full_prd_content_or_ref"]


def test_architecture_review_blocks_on_machine_design_summary_without_design_body() -> None:
    result = resolve_embedded_inputs(target_skill="architecture-review", machine_artifact={"artifact_type": "system_design_spec", "payload": {"title": "Checkout", "readiness": "Ready to implement"}})
    assert result.status == "BLOCKED"
    assert result.missing == ["full_system_design_content_or_ref"]


def test_embedded_context_conflict_never_silently_prefers_top_level_input() -> None:
    result = resolve_embedded_inputs(assessment_context=assessment_context(inputs={"service_name": "payments"}), top_level={"service_name": "ledger"})
    assert result.status in {"CONFLICTED", "BLOCKED"}


def test_child_result_target_must_match_handoff_target() -> None:
    assert validate_embedded_result_target(assessment_target(head_revision_or_digest="a" * 40), assessment_target(head_revision_or_digest="b" * 40)) != []


def test_embedded_handoff_preserves_caller_input_authority() -> None:
    ctx = assessment_context(inputs={"rollback_plan": "always safe"}, input_provenance={"rollback_plan": {"authority": "caller", "evidence_refs": ["caller:rollback"]}})
    resolved = resolve_embedded_inputs(assessment_context=ctx, top_level={})
    assert resolved.input_provenance["rollback_plan"]["authority"] == "caller"


def test_validated_runtime_handoff_preserves_but_does_not_upgrade_authority() -> None:
    ctx = assessment_context(input_provenance={"rollback_plan": {"authority": "repository"}})
    trust = classify_assessment_context_trust(ctx, runtime_metadata={"acquisition": "runtime_handoff", "parent_skill": "production-readiness-review", "parent_execution_validated": True})
    assert trust.effective_authority("rollback_plan") == "repository"
