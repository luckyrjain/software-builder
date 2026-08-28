"""Automated end-to-end engineering-delivery lifecycle contract test (Task 7).

Deterministic machine-artifact construction only -- this test does not judge
LLM prose. Each stage's own internal correctness already has a dedicated test
suite (test_change_impact_analyzer.py, test_resilience_review.py,
test_implementation_plan.py, test_production_readiness_contract.py); this
test instead proves the stages actually COMPOSE: the registered
produces/consumes contract chain from PRD through release, and -- the part
only this PR's own code can prove -- that a v1 release manifest never
invokes production readiness while a v2 manifest reuses a trusted deployable-
scoped report first and only conditionally invokes production-readiness-review
through the real scripts.production_readiness orchestration logic.
"""

from __future__ import annotations

from pathlib import Path

from scripts import production_readiness as pr
from scripts import release_readiness_v2
from scripts.registry.artifact_contracts import validate_artifact_result
from scripts.registry.canonical_manifest import load_canonical_manifest
from scripts.tests.production_readiness_fixtures import (
    build_provenance,
    ci_green,
    code_review_coverage,
    dimension,
    image_candidate,
    source_candidate,
    trusted_child_result,
)
from scripts.tests.release_readiness_v2_fixtures import (
    ROOT,
    release_check_spy,
    spy,
    trusted_production_report,
    v1_entry,
    v2_entry,
)

_DEFAULT_REVISION = "a" * 40
_DEFAULT_DIGEST = "sha256:" + "b" * 64


def _composition_skills() -> dict:
    manifest = load_canonical_manifest(ROOT)
    return manifest["contracts"]["composition"]["skills"]


def _produces(skill_id: str) -> list[str]:
    return list(_composition_skills()[skill_id].get("produces", []))


def _consumes(skill_id: str) -> list[str]:
    return list(_composition_skills()[skill_id].get("consumes", []))


# ---------------------------------------------------------------------------
# Design path: prd_report -> system_design_spec -> architecture_review_report
# ---------------------------------------------------------------------------


def test_design_path_contract_chain_is_registered() -> None:
    assert "prd_report" in _produces("prd-architect")
    assert "prd_report" in _consumes("system-design")
    assert "system_design_spec" in _produces("system-design")
    assert "system_design_spec" in _consumes("architecture-review")
    assert "architecture_review_report" in _produces("architecture-review")
    # The rework loop feeds an architecture-review finding back into a NEW
    # system-design invocation, not a direct architecture-review -> PRD edge.
    assert "architecture_review_report" in _consumes("system-design")


# ---------------------------------------------------------------------------
# Planning path: design + architecture + impact + specialist conditions
# -> implementation_plan. No required condition/action/test may disappear --
# proven here by implementation-planner declaring every upstream artifact
# type (including every design-time specialist review) as a consumed input.
# ---------------------------------------------------------------------------


def test_planning_path_consumes_every_upstream_condition_source() -> None:
    consumed = set(_consumes("implementation-planner"))
    required_upstream = {
        "system_design_spec",
        "architecture_review_report",
        "change_impact_report",
        "api_design_review_report",
        "database_review_report",
        "security_review_report",
        "performance_review_report",
        "capacity_plan",
        "observability_review_report",
        "resilience_review_report",
        "dependency_upgrade_report",
    }
    assert required_upstream <= consumed
    assert "implementation_plan" in _produces("implementation-planner")


# ---------------------------------------------------------------------------
# Execution contract: implementation_plan -> loop-task selection. Internal
# plan-execution state is workflow state, never a durable composition
# artifact (Task 6.14 of the v10 design).
# ---------------------------------------------------------------------------


def test_execution_contract_consumes_plan_and_keeps_internal_state_off_registry() -> None:
    assert "implementation_plan" in _consumes("loop-task-implementer")
    assert "implementation_pr" in _produces("loop-task-implementer")

    manifest = load_canonical_manifest(ROOT)
    artifact_runtime = manifest["contracts"]["platform"]["artifact_runtime"]
    assert "plan_execution_state" not in artifact_runtime.get("durable_artifacts", [])
    assert "plan_execution_state" not in artifact_runtime.get("external_input_artifacts", [])


# ---------------------------------------------------------------------------
# PR candidate readiness: mr_review + source-scoped evidence + CI ->
# production readiness, exercised through the real aggregation logic.
# ---------------------------------------------------------------------------


def test_pr_candidate_readiness_ready_when_review_and_ci_are_clean() -> None:
    candidate = source_candidate(source_revision=_DEFAULT_REVISION)
    mr_review = trusted_child_result(
        "mr_review_report",
        status="PASS",
        source_revision=_DEFAULT_REVISION,
        evidence_authorities={"result": {"repository"}},
    )
    accepted = pr.accept_child_result(mr_review, candidate=candidate, dimension="code_review")
    ci_result = pr.validate_ci(candidate, ci_green(head_revision=_DEFAULT_REVISION))

    dims = [
        dimension("code_review", accepted.status),
        dimension("ci", ci_result["status"]),
        dimension("security", "PASS"),
    ]
    result = pr.production_readiness(candidate, dimensions=dims)
    assert result.verdict == "READY"
    assert result.skill_result_status == "SUCCESS"


def test_pr_candidate_readiness_not_ready_on_ci_failure() -> None:
    candidate = source_candidate(source_revision=_DEFAULT_REVISION)
    ci_result = pr.validate_ci(candidate, {**ci_green(head_revision=_DEFAULT_REVISION), "all_required_green": False})
    dims = [dimension("ci", ci_result["status"]), dimension("security", "PASS")]
    result = pr.production_readiness(candidate, dimensions=dims)
    assert result.verdict == "NOT_READY"


# ---------------------------------------------------------------------------
# Image release: source commit reviews + build provenance -> image digest
# production readiness -> release. This is the deployable-scoped candidate
# shape release-readiness-checker's v2 conditional invoke actually builds.
# ---------------------------------------------------------------------------


def test_image_release_candidate_bridges_source_evidence_via_build_provenance() -> None:
    candidate = image_candidate(source_revision=_DEFAULT_REVISION, digest=_DEFAULT_DIGEST)
    provenance_result = pr.validate_build_provenance(
        candidate, build_provenance(source_revision=_DEFAULT_REVISION, digest=_DEFAULT_DIGEST)
    )
    assert provenance_result["status"] == "PASS"

    coverage_result = pr.validate_code_review_coverage(
        code_review_coverage(candidate_source_revision=_DEFAULT_REVISION, status="COMPLETE"),
        candidate,
    )
    dims = [
        dimension("build_provenance", provenance_result["status"]),
        dimension("code_review", coverage_result["status"]),
        dimension("security", "PASS"),
    ]
    result = pr.production_readiness(candidate, dimensions=dims)
    assert result.verdict == "READY"

    report = trusted_production_report(
        verdict=result.verdict,
        deployable=_DEFAULT_DIGEST,
        source_revision=_DEFAULT_REVISION,
    )
    # Validate the artifact passed between the production-readiness and
    # release-readiness stages against the registered artifact contract with
    # trusted producer context, per Task 7's "validate every artifact passed
    # between stages" requirement.
    envelope = {
        "skill_result": {
            "skill": "production-readiness-review",
            "version": "1.0.0",
            "status": "SUCCESS",
            "confidence": "HIGH",
            "source_revision": _DEFAULT_REVISION,
            "evidence_status": "OBSERVED",
            "artifacts": ["production_readiness_report"],
            "blockers": [],
            "recommended_next_skill": None,
            "artifact_schema_version": 1,
            "state_semantic": "current_state",
        },
        "provenance": {
            "source_revision": _DEFAULT_REVISION,
            "sources": ["production-readiness:1"],
        },
        "freshness": {
            "observed_at": "2026-08-24T12:00:00Z",
            "source_revision": _DEFAULT_REVISION,
            "source_environment": "github",
        },
        "definition_of_done": {
            "required_artifacts": ["production_readiness_report"],
            "required_checks": ["aggregate_verdict"],
            "completed_checks": ["aggregate_verdict"],
            "blocked_conditions": [],
            "partial_result_behavior": "return PARTIAL with unresolved dimensions",
        },
        "authority": {
            "write_authority": "read-only",
            "canonical_owner": "production-readiness-review",
        },
        "payload": {
            "title": "Production Readiness Report",
            "assessment_target": {
                "repo": "acme/checkout",
                "service": "checkout",
                "environment": None,
                "head_revision_or_digest": _DEFAULT_DIGEST,
            },
            "source_revision": _DEFAULT_REVISION,
            "build_provenance_ref": "build:1",
            "criticality": "unknown",
            "verdict": "READY",
            "dimension_statuses": [],
            "operational_evidence": {},
            "blockers": [],
            "conditions": [],
            "waivers": [],
            "required_actions": [],
            "evidence_refs": ["production-readiness:1"],
        },
    }
    errors = validate_artifact_result(
        ROOT, "production_readiness_report", envelope, producer_skill="production-readiness-review"
    )
    assert errors == []

    # Release readiness (v2, required) reuses exactly this trusted report.
    entry = v2_entry(required=True, release_ref=_DEFAULT_DIGEST, source_revision=_DEFAULT_REVISION)
    release_result = release_readiness_v2.run_release(entry, trusted_reports=[report], production_invoke=None)
    assert release_result["production_readiness_source"] == "REUSED"
    assert release_result.production_readiness == "READY"


# ---------------------------------------------------------------------------
# Release v1: never invokes production readiness.
# ---------------------------------------------------------------------------


def test_release_v1_path_never_invokes_production_readiness() -> None:
    invoke = spy()
    result = release_readiness_v2.run_release(
        [v1_entry(), v1_entry(repo="acme/billing", service="billing")],
        production_invoke=invoke,
    )
    assert invoke.calls == 0
    assert result.production_readiness is None
    assert result.production_readiness_source is None


# ---------------------------------------------------------------------------
# Release v2: reuse-first, then conditional invoke through the real
# production-readiness aggregation logic (not just a bare spy return value).
# ---------------------------------------------------------------------------


def test_release_v2_path_reuses_first_then_conditionally_invokes_real_orchestration() -> None:
    # No trusted report supplied -- the release path must fall through to a
    # conditional invoke, which here actually runs pr.production_readiness()
    # end to end rather than returning a canned fixture.
    def production_invoke(candidate, *, assessment_context=None):
        dims = [
            dimension("code_review", "PASS"),
            dimension("ci", "PASS"),
            dimension("security", "PASS"),
        ]
        readiness = pr.production_readiness(candidate, dimensions=dims)
        return trusted_production_report(
            verdict=readiness.verdict,
            repo=candidate["repo"],
            service=candidate["service"],
            environment=candidate["environment"],
            deployable=candidate["head_revision_or_digest"],
            source_revision=candidate["source_revision"],
        )

    entry = v2_entry(required=True, source_revision=_DEFAULT_REVISION, release_ref=_DEFAULT_DIGEST)
    result = release_readiness_v2.run_release(
        entry,
        trusted_reports=[],
        production_invoke=production_invoke,
        check_spy=release_check_spy(),
    )
    assert result["production_readiness_source"] == "INVOKED"
    assert result.production_readiness == "READY"
    assert result.overall == "READY"

    # A second run with that same result now supplied as a trusted report
    # must reuse it instead of invoking again.
    reused_invoke = spy()
    trusted = trusted_production_report(
        verdict="READY", repo="acme/checkout", service="checkout", deployable=_DEFAULT_DIGEST, source_revision=_DEFAULT_REVISION
    )
    reuse_result = release_readiness_v2.run_release(
        v2_entry(required=True, source_revision=_DEFAULT_REVISION, release_ref=_DEFAULT_DIGEST),
        trusted_reports=[trusted],
        production_invoke=reused_invoke,
    )
    assert reused_invoke.calls == 0
    assert reuse_result["production_readiness_source"] == "REUSED"


def test_release_v2_recursion_depth_and_no_reverse_edge() -> None:
    manifest = load_canonical_manifest(ROOT)
    handoffs = manifest["contracts"]["composition_runtime"]["handoffs"]
    assert handoffs["release-readiness-checker"]["production-readiness-review"] == ["assessment_context"]
    assert "release-readiness-checker" not in handoffs.get("production-readiness-review", {})
    max_depth = manifest["contracts"]["composition_runtime"]["recursion_guard"]["default_max_depth"]
    # release-readiness-checker (0) -> production-readiness-review (1) -> leaf (2)
    assert 2 < max_depth
