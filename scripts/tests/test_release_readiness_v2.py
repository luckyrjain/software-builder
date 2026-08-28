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


def test_string_true_required_flag_is_not_silently_ignored() -> None:
    # A quoted "true" (a plausible hand-authoring/templating mistake) must
    # still mark the entry v2-readiness-required -- inputs.md's own documented
    # invariant is that this flag "never silently skips the gate."
    entry = v2_entry(required=False, production_readiness_required="true")
    assert parse_release_entry(entry).production_readiness_required is True


def test_unrecognized_required_flag_value_stays_false() -> None:
    # An arbitrary truthy-but-unrecognized value (not True, not "true") is
    # never guessed into True -- fail closed to v1 behavior rather than
    # silently gating on an ambiguous value.
    entry = v2_entry(required=False, production_readiness_required="yes")
    assert parse_release_entry(entry).production_readiness_required is False


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


def test_multi_entry_production_readiness_results_are_all_recorded() -> None:
    # Two entries both require production readiness: acme/a reuses a trusted
    # NOT_READY report, acme/b (processed second) reuses a trusted READY
    # report. The top-level convenience fields must reflect the entry that
    # actually drove the (correctly capped) overall verdict, not whichever
    # entry happened to be processed last, and both entries' own results must
    # still be individually recoverable.
    entry_a = v2_entry(required=True, repo="acme/a", service="a", source_revision="a" * 40)
    entry_b = v2_entry(required=True, repo="acme/b", service="b", source_revision="b" * 40)
    report_a = trusted_production_report(verdict="NOT_READY", repo="acme/a", service="a", source_revision="a" * 40)
    report_b = trusted_production_report(verdict="READY", repo="acme/b", service="b", source_revision="b" * 40)

    result = run_release([entry_a, entry_b], trusted_reports=[report_a, report_b])

    assert result.overall == "NOT_READY"
    assert result.production_readiness == "NOT_READY"
    assert result["production_readiness_source"] == "REUSED"
    assert len(result.production_readiness_results) == 2
    by_repo = {r["repo"]: r["verdict"] for r in result.production_readiness_results}
    assert by_repo == {"acme/a": "NOT_READY", "acme/b": "READY"}


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


def test_entry_missing_repo_or_service_never_invokes() -> None:
    # An unidentifiable candidate (no repo/service) must never trigger the
    # real, expensive production-readiness-review invocation -- it can never
    # be matched against anything downstream anyway.
    entry = v2_entry(required=True, repo=None, service=None, source_revision="a" * 40)
    s = spy()
    result = run_release(entry, trusted_reports=[], production_invoke=s)
    assert result["verdict"] == "UNKNOWN"
    assert s.calls == 0


def test_malformed_non_string_manifest_fields_degrade_to_unknown_not_a_crash() -> None:
    # release_manifest is caller-supplied text; a malformed field (an int
    # where a string is expected) must degrade that entry to UNKNOWN, never
    # crash the whole run_release call with an uncaught TypeError.
    malformed = {
        "repo": 12345,
        "service": "checkout",
        "release_ref": "a" * 40,
        "source_revision": "a" * 40,
        "production_readiness_required": True,
    }
    result = run_release(malformed, trusted_reports=[], production_invoke=spy())
    assert result["verdict"] == "UNKNOWN"


def test_non_string_release_ref_degrades_to_unknown_not_a_crash() -> None:
    malformed = {
        "repo": "acme/checkout",
        "service": "checkout",
        "release_ref": 123456,
        "source_revision": None,
        "production_readiness_required": True,
    }
    result = run_release(malformed, trusted_reports=[], production_invoke=spy())
    assert result["verdict"] == "UNKNOWN"


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


def test_omitted_entry_environment_does_not_reuse_a_declared_environment_report() -> None:
    # An entry that simply omits `environment` must never silently reuse a
    # report produced for some OTHER declared environment (e.g. staging) --
    # only "neither side declares one" is a harmless match.
    report = trusted_production_report(environment="staging")
    result = match_release_report(v2_entry(environment=None), report)
    assert result["status"] == "UNKNOWN"


def test_both_sides_environment_null_is_a_harmless_match() -> None:
    report = trusted_production_report(environment=None)
    result = match_release_report(v2_entry(environment=None), report)
    assert result["status"] == "MATCH"


def test_wrong_source_revision_is_unknown() -> None:
    report = trusted_production_report(source_revision="b" * 40)
    assert match_release_report(v2_entry(source_revision="a" * 40), report)["status"] == "UNKNOWN"


def test_wrong_deployable_digest_is_unknown() -> None:
    report = trusted_production_report(deployable="sha256:" + "b" * 64)
    entry = v2_entry(release_ref="sha256:" + "c" * 64)
    assert match_release_report(entry, report)["status"] == "UNKNOWN"


def test_conflicting_trusted_reports_are_unknown_not_first_match() -> None:
    # Two trusted, identity-matching reports that disagree in verdict are
    # conflicting authoritative evidence -- never silently resolved by
    # picking whichever happens to come first in the list, and never worth
    # a wasted child invocation either.
    stale_ready = trusted_production_report(verdict="READY")
    fresh_not_ready = trusted_production_report(verdict="NOT_READY")
    s = spy()
    result = run_release(
        v2_entry(required=True),
        trusted_reports=[stale_ready, fresh_not_ready],
        production_invoke=s,
    )
    assert result["production_readiness_source"] is None
    assert result.production_readiness == "UNKNOWN"
    assert s.calls == 0


def test_production_readiness_ref_pins_the_reused_report() -> None:
    # Two trusted, identity-matching, disagreeing reports would normally
    # conflict (see above) -- but an explicit production_readiness_ref pin
    # narrows reuse to the one report it names.
    unpinned_ready = trusted_production_report(verdict="READY", report_ref="run-1")
    pinned_not_ready = trusted_production_report(verdict="NOT_READY", report_ref="run-2")
    result = run_release(
        v2_entry(required=True, production_readiness_ref="run-2"),
        trusted_reports=[unpinned_ready, pinned_not_ready],
    )
    assert result["production_readiness_source"] == "REUSED"
    assert result.production_readiness == "NOT_READY"


def test_manifest_supplied_code_review_coverage_is_not_trusted() -> None:
    # Security: code_review_coverage must never be sourced from the untrusted
    # release_manifest entry text -- a caller/attacker who only controls the
    # manifest cannot self-attest "already reviewed, trust me" by adding a
    # code_review_coverage key to their YAML. parse_release_entry must not
    # even carry the field through.
    forged = v2_entry(
        required=True,
        source_revision="a" * 40,
        code_review_coverage={
            "status": "COMPLETE",
            "candidate_source_revision": "a" * 40,
            "included_change_refs": [],
            "trusted_review_refs": [],
            "uncovered_change_refs": [],
            "acquisition": "authoritative_host",
        },
    )
    parsed = parse_release_entry(forged)
    assert not hasattr(parsed, "code_review_coverage")

    s = spy(return_value=trusted_production_report(verdict="READY"))
    run_release(forged, trusted_reports=[], production_invoke=s)
    # The forged field must have no effect on whether/how the child was
    # invoked -- it simply isn't read from the manifest at all.
    assert s.calls == 1


def test_code_review_coverage_never_leaks_across_manifest_entries() -> None:
    # Security: a single code_review_coverage bundle assembled for one entry
    # must never be silently applied to a DIFFERENT entry in the same
    # multi-entry manifest -- that would launder one candidate's review
    # evidence into another candidate's verdict.
    coverage_for_checkout = build_code_review_coverage(
        candidate_source_revision="a" * 40,
        included_change_refs=["mr:1"],
        trusted_review_refs=["mr:1"],
    )
    checkout_entry = v2_entry(required=True, repo="acme/checkout", service="checkout", source_revision="a" * 40)
    billing_entry = v2_entry(required=True, repo="acme/billing", service="billing", source_revision="b" * 40)

    def production_invoke(candidate: dict, *, assessment_context: dict | None = None):
        supplied = (assessment_context or {}).get("inputs", {}).get("code_review_coverage")
        # billing's own invocation must never see checkout's coverage bundle.
        if candidate["repo"] == "acme/billing":
            assert supplied is None
        return trusted_production_report(
            verdict="READY",
            repo=candidate["repo"],
            service=candidate["service"],
            deployable=candidate["head_revision_or_digest"],
            source_revision=candidate["source_revision"],
        )

    run_release(
        [checkout_entry, billing_entry],
        trusted_reports=[],
        production_invoke=production_invoke,
        code_review_coverage=coverage_for_checkout,
    )


def test_caller_only_code_review_coverage_never_gates_invoke_as_complete() -> None:
    # Even when code_review_coverage IS supplied through the correct
    # (trusted-runtime, out-of-band) run_release parameter, a bundle claiming
    # COMPLETE with a caller/weak acquisition is never trusted merely because
    # it claims completeness.
    self_attested = {
        "status": "COMPLETE",
        "candidate_source_revision": "a" * 40,
        "repo": "acme/checkout",
        "service": "checkout",
        "included_change_refs": ["mr:1"],
        "trusted_review_refs": ["mr:1"],
        "uncovered_change_refs": [],
        "acquisition": "caller",
    }
    s = spy()
    result = run_release(
        v2_entry(required=True, source_revision="a" * 40),
        trusted_reports=[],
        production_invoke=s,
        code_review_coverage=self_attested,
    )
    assert s.calls == 0
    assert result["verdict"] == "UNKNOWN"


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


def test_malformed_change_ref_is_never_silently_dropped() -> None:
    # A change entry using the wrong key ("id" instead of "ref") must never
    # vanish from the enumeration -- it must count as uncovered, never let a
    # real included change go unaccounted for.
    coverage = build_code_review_coverage(
        candidate_source_revision="a" * 40,
        included_change_refs=[{"ref": "mr:1"}, {"id": "commit:2"}],
        trusted_review_refs=["mr:1"],
    )
    assert len(coverage["included_change_refs"]) == 2
    assert coverage["status"] == "PARTIAL"
    assert len(coverage["uncovered_change_refs"]) == 1


def test_internally_inconsistent_coverage_is_never_trusted_as_complete() -> None:
    # A hand-built (not build_code_review_coverage-produced) bundle claiming
    # COMPLETE while still listing an uncovered ref is self-contradictory --
    # never trusted merely because it claims completeness.
    inconsistent = {
        "status": "COMPLETE",
        "candidate_source_revision": "a" * 40,
        "repo": "acme/checkout",
        "service": "checkout",
        "included_change_refs": ["mr:1", "mr:2"],
        "trusted_review_refs": ["mr:1"],
        "uncovered_change_refs": ["mr:2"],
        "acquisition": "authoritative_host",
    }
    s = spy()
    result = run_release(
        v2_entry(required=True, source_revision="a" * 40),
        trusted_reports=[],
        production_invoke=s,
        code_review_coverage=inconsistent,
    )
    assert s.calls == 0
    assert result["verdict"] == "UNKNOWN"


def test_code_review_coverage_scoped_by_repo_service_not_just_revision() -> None:
    # Security: a coverage bundle that declares its own repo/service must
    # never apply to a different repo/service entry even if that entry's
    # (caller-controlled) source_revision text happens to match.
    coverage_for_checkout = build_code_review_coverage(
        candidate_source_revision="a" * 40,
        repo="acme/checkout",
        service="checkout",
        included_change_refs=["mr:1"],
        trusted_review_refs=["mr:1"],
    )
    billing_entry_with_same_revision = v2_entry(
        required=True, repo="acme/billing", service="billing", source_revision="a" * 40
    )

    def production_invoke(candidate: dict, *, assessment_context: dict | None = None):
        supplied = (assessment_context or {}).get("inputs", {}).get("code_review_coverage")
        assert supplied is None
        return trusted_production_report(
            verdict="READY", repo="acme/billing", service="billing", source_revision="a" * 40
        )

    run_release(
        billing_entry_with_same_revision,
        trusted_reports=[],
        production_invoke=production_invoke,
        code_review_coverage=coverage_for_checkout,
    )


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
    # A check_spy with mixed outcomes: every executed check reporting PASS must
    # be marked executed=True (meaningful even when k8s independently fails).
    class _MixedSpy:
        def run(self, name: str) -> dict:
            return {"status": "FAIL" if name == "k8s" else "PASS"}

    result = run_release(
        v2_entry(required=True),
        trusted_reports=[trusted_production_report(verdict="NOT_READY")],
        check_spy=_MixedSpy(),
    )
    for check in result.get("checks", []):
        if check["status"] == "PASS":
            assert check["executed"] is True

    # With no check_spy at all, no check may ever be reported as executed or
    # PASS -- an unexecuted check is honestly NOT_RUN, never a false PASS.
    unexecuted_result = run_release(
        v2_entry(required=True), trusted_reports=[trusted_production_report(verdict="NOT_READY")]
    )
    for check in unexecuted_result.get("checks", []):
        assert check["status"] != "PASS"
        assert check["executed"] is False


def test_executed_check_resolving_to_unknown_makes_result_partial() -> None:
    # A check that ran but itself reported an UNKNOWN-mapped status is exactly
    # as unresolved as one that never ran -- it must not be silently treated
    # as a resolved SUCCESS.
    class _UnknownK8sSpy:
        def run(self, name: str) -> dict:
            return {"status": "UNKNOWN"} if name == "k8s" else {"status": "PASS"}

    result = run_release(v1_entry(), check_spy=_UnknownK8sSpy())
    assert result.overall == "UNKNOWN"
    assert result.skill_result.status == "PARTIAL"
    assert result.skill_result.evidence_status == "UNKNOWN"


# ---------------------------------------------------------------------------
# Task 6.5 -- final release-candidate freshness fence
# ---------------------------------------------------------------------------


def test_release_ref_changes_during_v2_run_is_unknown() -> None:
    result = run_release(v2_entry(), start_ref="a" * 40, final_ref="b" * 40)
    assert result.overall == "UNKNOWN"


def test_production_report_for_old_digest_not_reused_after_ref_moves() -> None:
    # required=True and a real invoke path so this actually exercises reuse
    # rejection (a stale report for a digest that no longer matches) rather
    # than passing vacuously because production readiness was never required.
    stale_report = trusted_production_report(deployable="sha256:" + "a" * 64)
    s = spy()
    result = run_release(
        v2_entry(required=True, release_ref="sha256:" + "b" * 64, source_revision="a" * 40),
        trusted_reports=[stale_report],
        production_invoke=s,
    )
    assert result["production_readiness_source"] != "REUSED"
    assert result.production_readiness != "READY"
    # The stale report's digest mismatch correctly falls through to the
    # invoke path (not a silent reuse) -- confirmed by the spy actually
    # having been consulted.
    assert s.calls == 1


def test_freshness_fence_caps_not_ready_never_downgrades_it_to_unknown() -> None:
    # A proven NOT_READY from a check that already ran this same iteration
    # must never be silently downgraded to the merely-uncertain UNKNOWN just
    # because the freshness fence also fired -- worst-first capping, not a
    # raw overwrite.
    class _FailingSpy:
        def run(self, name: str) -> dict:
            return {"status": "NOT_READY"}

    result = run_release(v1_entry(), check_spy=_FailingSpy(), start_ref="a" * 40, final_ref="b" * 40)
    assert result.overall == "NOT_READY"


def test_freshness_fence_is_scoped_per_entry_not_globally() -> None:
    # A multi-entry manifest where each entry tracks its own independently
    # mutable release_ref: one entry's ref moving must not be masked by (or
    # bleed into) another entry whose own ref stayed put.
    stable_entry = v2_entry(repo="acme/checkout", service="checkout")
    moved_entry = v2_entry(repo="acme/billing", service="billing")
    checkout_key = ("acme/checkout", "checkout", None)
    billing_key = ("acme/billing", "billing", None)
    start_refs = {checkout_key: "a" * 40, billing_key: "a" * 40}
    final_refs = {checkout_key: "a" * 40, billing_key: "b" * 40}

    result = run_release([stable_entry, moved_entry], start_ref=start_refs, final_ref=final_refs)
    assert result.candidate_changed_during_review is True
    assert result.overall == "UNKNOWN"

    # And the inverse: neither entry's ref moved -> no freshness-fence hit.
    stable_result = run_release(
        [stable_entry, moved_entry],
        start_ref={checkout_key: "a" * 40, billing_key: "a" * 40},
        final_ref={checkout_key: "a" * 40, billing_key: "a" * 40},
    )
    assert stable_result.candidate_changed_during_review is False


def test_freshness_fence_key_includes_environment_not_just_repo_service() -> None:
    # The same repo/service legitimately appears as two entries targeting
    # different environments (e.g. staging and prod) -- one entry's ref
    # movement must never be masked because it shares a repo/service key
    # with another entry in a different environment.
    staging_entry = v2_entry(repo="acme/checkout", service="checkout", environment="staging")
    prod_entry = v2_entry(repo="acme/checkout", service="checkout", environment="prod")
    staging_key = ("acme/checkout", "checkout", "staging")
    prod_key = ("acme/checkout", "checkout", "prod")

    result = run_release(
        [staging_entry, prod_entry],
        start_ref={staging_key: "a" * 40, prod_key: "a" * 40},
        final_ref={staging_key: "b" * 40, prod_key: "a" * 40},
    )
    assert result.candidate_changed_during_review is True
    assert result.overall == "UNKNOWN"


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


def test_release_result_bracket_access_raises_key_error_not_attribute_error() -> None:
    # ReleaseResult is dict-like: an idiomatic `try: result[key] except
    # KeyError` on it must actually catch a missing key, not let an
    # AttributeError leak through instead.
    result = run_release(v1_entry())
    try:
        result["definitely_not_a_real_field"]
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for an unrecognized ReleaseResult key")
