"""Contract tests for scripts/release_readiness_v2.py (PR E).

v1 manifest behavior is byte/semantics-unchanged and never invokes production
readiness; v2 entries that require readiness reuse a trusted deployable-scoped
report first, otherwise conditionally invoke production-readiness-review only
when candidate identity/context/capability are sufficient, otherwise UNKNOWN.
"""

from __future__ import annotations

from scripts.release_readiness_v2 import (
    build_code_review_coverage,
    cap_release_verdict,
    classify_report_for_release,
    finalize_release,
    match_release_report,
    parse_release_entry,
    run_release,
)
from scripts import production_readiness as pr
from scripts.tests.release_readiness_v2_fixtures import (
    ROOT,
    child_context,
    default_max_depth,
    expected_release_pr_review_invocations,
    file_supplied_production_report,
    grandchild_context,
    invoked_skills,
    legacy_parse,
    max_release_v2_composition_depth,
    consumes,
    registry,
    release_check_spy,
    release_fixture,
    run_v2_release_with_complete_review_coverage,
    run_v2_release_with_uncovered_change,
    runtime_handoff_artifacts,
    spy,
    trusted_production_report,
    v1_entry,
    v2_entry,
)

# ---------------------------------------------------------------------------
# v1 unchanged
# ---------------------------------------------------------------------------


def test_v1_manifest_behavior_is_unchanged() -> None:
    entry = {"repo": "acme/payments", "service": "payments", "since": "v1.2.3"}
    before = legacy_parse(entry)
    after = parse_release_entry(entry)
    assert after.compatibility_projection() == before
    assert after.production_readiness_required is False


def test_v1_never_invokes_production_readiness() -> None:
    invoke = spy()
    run_release(v1_entry(), production_invoke=invoke)
    assert invoke.calls == 0


def test_v1_mandatory_install_footprint_is_unchanged() -> None:
    registry_ = registry()
    requires = registry_.skills["release-readiness-checker"].install.requires
    assert requires == ["pr-review", "k8s-overprovisioning-datadog", "incident-rca"]
    assert "production-readiness-review" not in requires


# ---------------------------------------------------------------------------
# v2 trusted reuse / conditional invoke
# ---------------------------------------------------------------------------


def test_v2_required_reuses_trusted_report_first() -> None:
    report = trusted_production_report(verdict="READY")
    s = spy()
    result = run_release(v2_entry(required=True), trusted_reports=[report], production_invoke=s)
    assert s.calls == 0
    assert result["production_readiness_source"] == "REUSED"


def test_v2_required_missing_report_invokes_when_safe() -> None:
    s = spy(return_value=trusted_production_report(verdict="READY"))
    result = run_release(v2_entry(required=True, source_revision="a" * 40), trusted_reports=[], production_invoke=s)
    assert s.calls == 1
    assert result["production_readiness_source"] == "INVOKED"


def test_v2_required_missing_report_and_invoke_unavailable_is_unknown() -> None:
    result = run_release(v2_entry(required=True), trusted_reports=[], production_invoke=None)
    assert result["verdict"] == "UNKNOWN"


def test_v2_image_digest_without_source_revision_is_unknown_before_invoke() -> None:
    entry = v2_entry(required=True, release_ref="sha256:" + "b" * 64, source_revision=None)
    s = spy()
    result = run_release(entry, trusted_reports=[], production_invoke=s)
    assert result["verdict"] == "UNKNOWN"
    assert s.calls == 0


# ---------------------------------------------------------------------------
# Trusted reuse: no self-attestation, no fuzzy identity matching
# ---------------------------------------------------------------------------


def test_file_ready_report_cannot_self_attest() -> None:
    report = file_supplied_production_report(verdict="READY")
    assert classify_report_for_release(report)["trusted_for_gate"] is False


def test_environment_alias_mismatch_is_unknown() -> None:
    report = trusted_production_report(environment="production")
    result = match_release_report(v2_entry(environment="prod"), report)
    assert result["status"] == "UNKNOWN"


def test_wrong_source_revision_is_unknown() -> None:
    report = trusted_production_report(source_revision="b" * 40)
    assert match_release_report(v2_entry(source_revision="a" * 40), report)["status"] == "UNKNOWN"


def test_wrong_deployable_digest_is_unknown() -> None:
    report = trusted_production_report(deployable="sha256:" + "b" * 64)
    entry = v2_entry(release_ref="sha256:" + "c" * 64)
    assert match_release_report(entry, report)["status"] == "UNKNOWN"


# ---------------------------------------------------------------------------
# Composition contract / recursion safety
# ---------------------------------------------------------------------------


def test_release_production_handoff_uses_assessment_context() -> None:
    assert runtime_handoff_artifacts("release-readiness-checker", "production-readiness-review") == ["assessment_context"]
    assert consumes("production-readiness-review", "assessment_context")


def test_release_consumes_production_readiness_report() -> None:
    assert consumes("release-readiness-checker", "production_readiness_report")


def test_release_to_production_depth_is_one() -> None:
    ctx = child_context(parent="release-readiness-checker", child="production-readiness-review", depth=0)
    assert ctx["depth"] == 1


def test_production_child_dispatch_depth_is_two() -> None:
    ctx = grandchild_context(root="release-readiness-checker", parent="production-readiness-review", child="security-review")
    assert ctx["depth"] == 2


def test_no_production_to_release_invoke_edge() -> None:
    assert "release-readiness-checker" not in invoked_skills("production-readiness-review")


def test_depth_stays_below_default_max_three() -> None:
    assert max_release_v2_composition_depth() <= 2
    assert max_release_v2_composition_depth() < default_max_depth()


# ---------------------------------------------------------------------------
# Task 5 -- code-review coverage handoff
# ---------------------------------------------------------------------------


def test_one_uncovered_change_is_unknown_dimension() -> None:
    coverage = build_code_review_coverage(
        candidate_source_revision="a" * 40,
        included_change_refs=["mr:1", "mr:2"],
        trusted_review_refs=["mr:1"],
    )
    assert coverage["status"] == "PARTIAL"
    candidate = {"source_revision": "a" * 40}
    result = pr.validate_code_review_coverage(coverage, candidate)
    assert result["status"] == "UNKNOWN"


def test_revert_and_cherry_pick_are_never_silently_omitted() -> None:
    coverage = build_code_review_coverage(
        candidate_source_revision="a" * 40,
        included_change_refs=["mr:1", "revert:2", "cherry-pick:3"],
        trusted_review_refs=["mr:1", "revert:2", "cherry-pick:3"],
    )
    assert coverage["status"] == "COMPLETE"
    assert set(coverage["included_change_refs"]) == {"mr:1", "revert:2", "cherry-pick:3"}
    assert coverage["uncovered_change_refs"] == []


def test_squash_merge_with_authoritative_integrated_revision_is_covered() -> None:
    coverage = build_code_review_coverage(
        candidate_source_revision="a" * 40,
        included_change_refs=["mr:1"],
        trusted_review_refs=["squash-sha"],
        integrated_revisions={"mr:1": "squash-sha"},
    )
    assert coverage["status"] == "COMPLETE"


def test_forged_integrated_revision_is_ignored() -> None:
    forged_change = {"ref": "mr:1", "claimed_integrated_revision": "forged-sha"}
    coverage = build_code_review_coverage(
        candidate_source_revision="a" * 40,
        included_change_refs=[forged_change],
        trusted_review_refs=["forged-sha"],
        # No authoritative integrated_revisions entry for mr:1 -- the change's
        # own claimed linkage must never be consulted.
    )
    assert coverage["status"] == "PARTIAL"
    assert coverage["uncovered_change_refs"] == ["mr:1"]


def test_direct_unreviewed_commit_is_unknown_dimension() -> None:
    coverage = build_code_review_coverage(
        candidate_source_revision="a" * 40,
        included_change_refs=["commit:1"],
        trusted_review_refs=[],
    )
    candidate = {"source_revision": "a" * 40}
    assert pr.validate_code_review_coverage(coverage, candidate)["status"] == "UNKNOWN"


# ---------------------------------------------------------------------------
# Task 5.5 -- no composition revisits in the release-root path
# ---------------------------------------------------------------------------


def test_release_root_does_not_revisit_pr_review_through_production() -> None:
    trace = run_v2_release_with_complete_review_coverage()
    assert trace.count("pr-review") == expected_release_pr_review_invocations()
    assert trace.production_readiness_invoked_pr_review is False


def test_incomplete_release_review_coverage_stays_unknown_without_revisit() -> None:
    result = run_v2_release_with_uncovered_change()
    assert result.overall == "UNKNOWN"
    assert result.production_readiness_invoked_pr_review is False


# ---------------------------------------------------------------------------
# Task 6 -- preserve existing release checks and aggregate caps
# ---------------------------------------------------------------------------


def test_v2_not_ready_caps_release_not_ready() -> None:
    assert cap_release_verdict("READY", "NOT_READY") == "NOT_READY"


def test_v2_unknown_caps_release_unknown() -> None:
    assert cap_release_verdict("READY", "UNKNOWN") == "UNKNOWN"


def test_v2_conditional_caps_release_conditional() -> None:
    assert cap_release_verdict("READY", "CONDITIONAL") == "CONDITIONAL"


def test_ready_production_still_runs_existing_k8s_and_incident_checks() -> None:
    s = release_check_spy()
    run_release(
        v2_entry(required=True),
        trusted_reports=[trusted_production_report(verdict="READY")],
        check_spy=s,
    )
    assert {"k8s", "incident"} <= set(s.executed_checks)


def test_not_ready_short_circuit_does_not_report_existing_checks_as_passed_if_not_run() -> None:
    result = run_release(v2_entry(required=True), trusted_reports=[trusted_production_report(verdict="NOT_READY")])
    for check in result.get("checks", []):
        if check["status"] == "PASS":
            assert check["executed"] is True


# ---------------------------------------------------------------------------
# Task 6.5 -- final release-candidate freshness fence
# ---------------------------------------------------------------------------


def test_release_ref_changes_during_v2_run_is_unknown() -> None:
    result = run_release(v2_entry(), start_ref="a" * 40, final_ref="b" * 40)
    assert result.overall == "UNKNOWN"


def test_production_report_for_old_digest_not_reused_after_ref_moves() -> None:
    result = run_release(
        v2_entry(release_ref="sha256:" + "b" * 64),
        trusted_reports=[trusted_production_report(deployable="sha256:" + "a" * 64)],
    )
    assert result.production_readiness != "READY"


# ---------------------------------------------------------------------------
# Task 7.5 -- release execution-status semantics
# ---------------------------------------------------------------------------


def test_resolved_not_ready_release_is_successful_analysis() -> None:
    result = finalize_release(release_fixture(overall="NOT_READY", unknown_dimensions=[]))
    assert result.skill_result.status == "SUCCESS"


def test_required_unknown_dimension_makes_result_partial() -> None:
    result = finalize_release(release_fixture(overall="UNKNOWN", unknown_dimensions=["production_readiness"]))
    assert result.skill_result.status == "PARTIAL"


def test_not_ready_plus_other_unknown_is_partial_analysis() -> None:
    result = finalize_release(release_fixture(overall="NOT_READY", unknown_dimensions=["incident_health"]))
    assert result.skill_result.status == "PARTIAL"


def test_empty_manifest_is_blocked_not_failed() -> None:
    assert run_release([]).skill_result.status == "BLOCKED"
