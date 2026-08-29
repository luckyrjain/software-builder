"""Contract tests for scripts/release_readiness_v2.py (PR E).

v1 manifest behavior is byte/semantics-unchanged and never invokes production
readiness; v2 entries that require readiness reuse a trusted deployable-scoped
report first, otherwise conditionally invoke production-readiness-review only
when candidate identity/context/capability are sufficient, otherwise UNKNOWN.
"""

from __future__ import annotations

import copy

from scripts.release_readiness_v2 import (
    _candidate_from_entry,
    build_assessment_context,
    build_code_review_coverage,
    cap_release_verdict,
    classify_report_for_release,
    finalize_release,
    match_release_report,
    parse_release_entry,
    resolve_production_readiness,
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


def test_reuse_wins_even_when_code_review_coverage_is_incomplete() -> None:
    # Regression for the ordering itself, not just each side alone: reuse
    # (step 1) and the coverage-completeness gate (step 2) are both present
    # in the same call here, so a future swap of their order -- which would
    # make an incomplete `code_review_coverage` short-circuit to UNKNOWN
    # before the trusted-report loop ever runs -- fails this test even
    # though test_v2_required_reuses_trusted_report_first (no coverage
    # supplied at all) and test_incomplete_release_review_coverage_stays_
    # unknown_without_revisit (no trusted report supplied at all) would
    # both still pass.
    entry = v2_entry(required=True, repo="acme/checkout", service="checkout", source_revision="a" * 40)
    report = trusted_production_report(
        verdict="READY", repo="acme/checkout", service="checkout", source_revision="a" * 40
    )
    incomplete_coverage = build_code_review_coverage(
        candidate_source_revision="a" * 40,
        repo="acme/checkout",
        service="checkout",
        included_change_refs=["mr:1", "commit:2"],
        trusted_review_refs=["mr:1"],
    )
    s = spy()

    result = resolve_production_readiness(
        entry, trusted_reports=[report], production_invoke=s, code_review_coverage=incomplete_coverage
    )

    assert s.calls == 0
    assert result["status"] == "READY"
    assert result["source"] == "REUSED"


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


def test_same_repo_service_different_environment_entries_stay_distinguishable() -> None:
    # Two entries sharing repo+service but targeting different environments
    # (staging/prod) are a legitimate, first-class manifest shape (see the
    # freshness-fence environment-keying tests above) -- their own
    # production_readiness_results and checks rows must carry `environment`
    # so a consumer keying on (repo, service) alone cannot silently collapse
    # one environment's verdict into the other's.
    staging = v2_entry(
        required=True, repo="acme/checkout", service="checkout", environment="staging", source_revision="a" * 40
    )
    prod = v2_entry(
        required=True, repo="acme/checkout", service="checkout", environment="prod", source_revision="a" * 40
    )
    staging_report = trusted_production_report(
        verdict="READY", repo="acme/checkout", service="checkout", environment="staging", source_revision="a" * 40
    )
    prod_report = trusted_production_report(
        verdict="NOT_READY", repo="acme/checkout", service="checkout", environment="prod", source_revision="a" * 40
    )

    result = run_release([staging, prod], trusted_reports=[staging_report, prod_report])

    assert len(result.production_readiness_results) == 2
    by_environment = {r["environment"]: r["verdict"] for r in result.production_readiness_results}
    assert by_environment == {"staging": "READY", "prod": "NOT_READY"}

    check_environments = {c["environment"] for c in result.checks}
    assert check_environments == {"staging", "prod"}


def test_required_entry_voided_by_freshness_fence_still_recorded() -> None:
    # An entry that required production readiness but whose ref moved
    # mid-run must still appear in production_readiness_results (as UNKNOWN,
    # voided by the stale ref) -- never silently absent, which would make a
    # per-entry report render unable to show it was ever required at all.
    moved_entry = v2_entry(required=True, repo="acme/moved", service="moved")
    stable_entry = v2_entry(required=True, repo="acme/stable", service="stable", source_revision="a" * 40)
    stable_report = trusted_production_report(verdict="READY", repo="acme/stable", service="stable", source_revision="a" * 40)
    moved_key = ("acme/moved", "moved", None)
    stable_key = ("acme/stable", "stable", None)

    result = run_release(
        [moved_entry, stable_entry],
        trusted_reports=[stable_report],
        start_ref={moved_key: "a" * 40, stable_key: "a" * 40},
        final_ref={moved_key: "b" * 40, stable_key: "a" * 40},
    )
    by_repo = {r["repo"]: r["verdict"] for r in result.production_readiness_results}
    assert by_repo == {"acme/moved": "UNKNOWN", "acme/stable": "READY"}


def test_v2_required_missing_report_invokes_when_safe() -> None:
    s = spy(return_value=trusted_production_report(verdict="READY"))
    result = run_release(v2_entry(required=True, source_revision="a" * 40), trusted_reports=[], production_invoke=s)
    assert s.calls == 1
    assert result["production_readiness_source"] == "INVOKED"


def test_v2_required_missing_report_and_invoke_unavailable_is_unknown() -> None:
    result = run_release(v2_entry(required=True), trusted_reports=[], production_invoke=None)
    assert result["verdict"] == "UNKNOWN"


def test_resolve_production_readiness_accepts_a_raw_manifest_dict_directly() -> None:
    # resolve_production_readiness's own signature (`entry: Any`) and docstring
    # ("resolution for one v2 manifest entry") document standalone use with a
    # raw manifest mapping, not only a pre-parsed ReleaseEntry -- run_release
    # always pre-parses before calling it, so this branch
    # (`entry if isinstance(entry, ReleaseEntry) else parse_release_entry(entry)`)
    # is otherwise never exercised by any test that only goes through
    # run_release. Also exercises the NOT_REQUIRED early return, which
    # run_release never reaches this function for at all (it filters
    # non-required entries out beforehand).
    not_required = resolve_production_readiness(v2_entry(required=False))
    assert not_required == {"status": "NOT_REQUIRED", "source": None, "report": None}

    report = trusted_production_report(verdict="READY")
    reused = resolve_production_readiness(v2_entry(required=True), trusted_reports=[report])
    assert reused["status"] == "READY"
    assert reused["source"] == "REUSED"


def test_v2_image_digest_without_source_revision_is_unknown_before_invoke() -> None:
    entry = v2_entry(required=True, release_ref="sha256:" + "b" * 64, source_revision=None)
    s = spy()
    result = run_release(entry, trusted_reports=[], production_invoke=s)
    assert result["verdict"] == "UNKNOWN"
    assert s.calls == 0


def test_mutable_tag_release_ref_without_source_revision_is_unknown_before_invoke() -> None:
    # Security: design v10 Sec9 defines release_ref as "the immutable
    # deployable ref (commit SHA when that is the deployable, otherwise
    # image/artifact digest)". A colon-free but non-SHA-shaped mutable tag
    # (e.g. "latest") is neither -- it must not be mistaken for "release_ref
    # is itself a usable source revision" merely because it lacks a colon.
    for mutable_tag in ("latest", "main", "staging", "v1.2.3"):
        entry = v2_entry(required=True, release_ref=mutable_tag, source_revision=None)
        s = spy()
        result = run_release(entry, trusted_reports=[], production_invoke=s)
        assert result["verdict"] == "UNKNOWN", mutable_tag
        assert s.calls == 0, mutable_tag


def test_git_sha_release_ref_without_source_revision_is_sufficient_to_invoke() -> None:
    # The positive case: a release_ref that genuinely looks like a git commit
    # SHA is still usable as the source revision on its own, with no
    # additional source_revision field required.
    entry = v2_entry(required=True, release_ref="a" * 40, source_revision=None)
    s = spy(return_value=trusted_production_report(verdict="READY", deployable="a" * 40, source_revision=None))
    result = run_release(entry, trusted_reports=[], production_invoke=s)
    assert s.calls == 1
    assert result.production_readiness == "READY"


def test_mutable_tag_source_revision_is_unknown_before_invoke() -> None:
    # Security: sibling gap to the release_ref bug above -- an explicit
    # source_revision is untrusted release_manifest text at the exact same
    # trust boundary as release_ref, so a mutable tag or arbitrary caller
    # text supplied there (instead of merely being absent) must be exactly
    # as insufficient to invoke as one supplied via release_ref alone.
    # design v10 defines source_revision as "the immutable source-control
    # revision that code review and CI prove" -- an unproven, non-SHA-shaped
    # value can never satisfy that.
    for mutable_tag in ("latest", "HEAD", "main"):
        entry = v2_entry(required=True, release_ref="sha256:" + "b" * 64, source_revision=mutable_tag)
        s = spy()
        result = run_release(entry, trusted_reports=[], production_invoke=s)
        assert result["verdict"] == "UNKNOWN", mutable_tag
        assert s.calls == 0, mutable_tag


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


def test_non_string_trusted_report_identity_degrades_to_unknown_not_a_crash() -> None:
    # trusted_reports/production_invoke returns are external data too -- a
    # non-string repo/service/environment there must not crash run_release
    # via normalize_repo_identity/normalize_service_identity/same_environment.
    malformed_report = trusted_production_report(repo=12345)
    result = run_release(
        v2_entry(required=True), trusted_reports=[malformed_report], production_invoke=spy()
    )
    assert result["verdict"] == "UNKNOWN"


def test_non_string_coverage_repo_degrades_to_not_applied_not_a_crash() -> None:
    coverage_with_bad_repo = {
        "candidate_source_revision": "a" * 40,
        "repo": 999,
        "service": "checkout",
        "status": "COMPLETE",
        "uncovered_change_refs": [],
        "acquisition": "authoritative_host",
    }
    s = spy(return_value=trusted_production_report(verdict="READY"))
    result = run_release(
        v2_entry(required=True, source_revision="a" * 40),
        trusted_reports=[],
        production_invoke=s,
        code_review_coverage=coverage_with_bad_repo,
    )
    # Not applied to this entry (repo can't be normalized) -- proceeds to
    # invoke without pre-assembled coverage rather than crashing.
    assert s.calls == 1
    assert result.production_readiness == "READY"


def test_unhashable_verdict_degrades_to_unknown_not_a_crash() -> None:
    # A malformed report/invoke-result verdict (a list instead of a string)
    # must not crash the set-based conflict check or the _VERDICT_SEVERITY
    # membership test -- both would otherwise raise on an unhashable value.
    malformed_report = trusted_production_report(verdict=["READY"])
    result = run_release(v2_entry(required=True), trusted_reports=[malformed_report])
    assert result["verdict"] == "UNKNOWN"

    s = spy(return_value=trusted_production_report(verdict=["READY"]))
    invoked_result = run_release(
        v2_entry(required=True, source_revision="a" * 40), trusted_reports=[], production_invoke=s
    )
    assert invoked_result["verdict"] == "UNKNOWN"


def test_evidence_refs_wrong_shape_is_never_shredded() -> None:
    # A single ref string (instead of a one-element list) must never be
    # silently exploded into individual characters by a bare list(...) call.
    # For a trustworthy bundle, refs are read from `trusted_review_refs` (the
    # field actually vetted -- see
    # test_untrusted_coverage_evidence_refs_wrong_shape_is_never_shredded for
    # the caller-only/`evidence_refs` path).
    coverage = {
        "candidate_source_revision": "a" * 40,
        "repo": "acme/checkout",
        "service": "checkout",
        "status": "COMPLETE",
        "uncovered_change_refs": [],
        "acquisition": "authoritative_host",
        "trusted_review_refs": "pr-42",
        "evidence_refs": "pr-42",
    }
    context = build_assessment_context(
        parse_release_entry(v2_entry(source_revision="a" * 40)), code_review_coverage=coverage
    )
    assert context["evidence_refs"] == []
    assert context["input_provenance"]["code_review_coverage"]["evidence_refs"] == []


def test_untrusted_coverage_evidence_refs_wrong_shape_is_never_shredded() -> None:
    # Same wrong-shape guard, exercised on the caller-only (not host/runtime-
    # authoritative) path, where evidence_refs is still the field actually
    # read since there's no `trusted_review_refs` field to prefer instead.
    coverage = {
        "candidate_source_revision": "a" * 40,
        "repo": "acme/checkout",
        "service": "checkout",
        "status": "COMPLETE",
        "uncovered_change_refs": [],
        "acquisition": "caller_supplied",
        "evidence_refs": "pr-42",
    }
    context = build_assessment_context(
        parse_release_entry(v2_entry(source_revision="a" * 40)), code_review_coverage=coverage
    )
    assert context["input_provenance"]["code_review_coverage"]["authority"] == "caller"
    assert context["evidence_refs"] == []
    assert context["input_provenance"]["code_review_coverage"]["evidence_refs"] == []


def test_trustworthy_coverage_cannot_stamp_forged_evidence_refs_as_trusted_runtime() -> None:
    # Security: a bundle can satisfy every structural trustworthiness check
    # (status COMPLETE, no uncovered_change_refs, host/runtime-authoritative
    # acquisition) while separately declaring an `evidence_refs` list
    # unrelated to `trusted_review_refs` (the field actually vetted) -- e.g.
    # a hand-built or otherwise-produced bundle, not one assembled by
    # build_code_review_coverage itself (which always sets evidence_refs to
    # a copy of trusted_review_refs). That unrelated content must never be
    # stamped "trusted_runtime" and folded into the release-level
    # evidence_refs merely because the surrounding bundle passed its
    # trustworthiness check.
    coverage = {
        "candidate_source_revision": "a" * 40,
        "repo": "acme/checkout",
        "service": "checkout",
        "status": "COMPLETE",
        "uncovered_change_refs": [],
        "acquisition": "authoritative_host",
        "trusted_review_refs": ["mr:1"],
        "evidence_refs": ["TOTALLY-FORGED-UNRELATED-REF"],
    }
    context = build_assessment_context(
        parse_release_entry(v2_entry(source_revision="a" * 40)), code_review_coverage=coverage
    )
    assert context["input_provenance"]["code_review_coverage"]["authority"] == "trusted_runtime"
    assert context["evidence_refs"] == ["mr:1"]
    assert context["input_provenance"]["code_review_coverage"]["evidence_refs"] == ["mr:1"]


def test_code_review_coverage_is_never_mutated_through_the_assessment_context() -> None:
    # A production_invoke callable is a plain, caller-supplied Python
    # callable with no enforcement preventing it from mutating whatever
    # mapping it's handed. `code_review_coverage` was stored into
    # `inputs`/`assessment_target` by raw reference. Since run_release
    # passes the SAME code_review_coverage object to every entry in a
    # multi-entry manifest and to every future call that reuses it, an
    # invoke mutating its own assessment_context could otherwise corrupt the
    # caller's trusted-runtime-supplied bundle in place, silently changing a
    # later entry's (or a later run's) resolved verdict.
    coverage = build_code_review_coverage(
        candidate_source_revision="a" * 40,
        included_change_refs=["mr:1"],
        trusted_review_refs=["mr:1"],
        repo="acme/checkout",
        service="checkout",
    )
    original_coverage = copy.deepcopy(coverage)

    def mutating_invoke(candidate: dict, *, assessment_context: dict | None = None):
        supplied = (assessment_context or {}).get("inputs", {}).get("code_review_coverage")
        if supplied is not None:
            supplied["status"] = "CORRUPTED"
            supplied["trusted_review_refs"].append("INJECTED")
        return trusted_production_report(
            verdict="READY",
            repo=candidate["repo"],
            service=candidate["service"],
            deployable=candidate["head_revision_or_digest"],
            source_revision=candidate["source_revision"],
        )

    entry = v2_entry(required=True, repo="acme/checkout", service="checkout", source_revision="a" * 40)
    run_release(entry, trusted_reports=[], production_invoke=mutating_invoke, code_review_coverage=coverage)
    assert coverage == original_coverage


def test_build_assessment_context_candidate_override_is_never_mutated_via_assessment_target() -> None:
    # Sibling to the code_review_coverage mutation-safety fix above: a
    # caller-supplied `candidate` override carrying nested mutable state (a
    # dict/list value) must not be mutable-in-place through
    # `assessment_context["assessment_target"]` either -- a shallow
    # `dict(candidate)` copy only protects the top-level keys, leaving any
    # nested mutable value aliased to the caller's own object. Not reachable
    # via run_release/resolve_production_readiness today (their own
    # `_candidate_from_entry` output is always flat/scalar-only), but
    # `candidate` is a documented public parameter of build_assessment_context
    # and must not be held to a weaker mutation-safety standard than its
    # sibling `code_review_coverage` parameter.
    entry = parse_release_entry(v2_entry(source_revision="a" * 40))
    candidate = {"repo": "acme/checkout", "service": "checkout", "nested": {"x": 1}}
    original_candidate = copy.deepcopy(candidate)

    context = build_assessment_context(entry, candidate=candidate)
    context["assessment_target"]["nested"]["x"] = 999

    assert candidate == original_candidate


def test_manifest_criticality_is_never_folded_into_the_candidate_as_identity() -> None:
    # Security: release_manifest is untrusted caller-supplied text. A manifest
    # author asserting a low criticality tier (e.g. "tier3" for what is really
    # a tier0 service) must never be forwarded into assessment_target/candidate
    # as if it were vetted identity data -- design v10 Sec9.2 requires
    # "criticality when authoritative/known" only, and this module has no
    # authoritative source to vet it against.
    entry = parse_release_entry(v2_entry(source_revision="a" * 40, criticality="tier3"))
    candidate = _candidate_from_entry(entry)
    assert "criticality" not in candidate


def test_manifest_criticality_surfaces_as_caller_authority_input() -> None:
    # The manifest's criticality is still passed along (per design v10 Sec9.2
    # and production-readiness-review's own documented "explicit caller-
    # supplied criticality field" input channel), but only tagged "caller"
    # authority -- never implicitly trusted -- so the invoked child can apply
    # its own authoritative-wins-over-caller precedence rather than this
    # caller's claim being silently treated as ground truth.
    entry = parse_release_entry(v2_entry(source_revision="a" * 40, criticality="tier3"))
    context = build_assessment_context(entry)
    assert context["inputs"]["criticality"] == "tier3"
    assert context["input_provenance"]["criticality"]["authority"] == "caller"


def test_omitted_manifest_criticality_is_not_defaulted_into_the_candidate() -> None:
    # An entry that omits criticality entirely must not have one silently
    # invented (e.g. "unknown") and folded into the candidate/assessment_target
    # -- absence is absence, letting the child's own resolution (host metadata
    # lookup, else its own strictest default) apply cleanly.
    entry = parse_release_entry(v2_entry(source_revision="a" * 40, criticality=None))
    candidate = _candidate_from_entry(entry)
    assert "criticality" not in candidate
    context = build_assessment_context(entry)
    assert "criticality" not in context["inputs"]


def test_non_string_check_status_degrades_to_unknown_not_a_crash() -> None:
    # A check harness returning a non-string, unhashable status (e.g. a list)
    # must not crash the _CHECK_STATUS_VERDICT lookup.
    class _MalformedStatusSpy:
        def run(self, name: str, **_: object) -> dict:
            return {"status": ["PASS", "extra"]}

    result = run_release(v1_entry(), check_spy=_MalformedStatusSpy())
    assert result.overall == "UNKNOWN"
    assert result.skill_result.status == "PARTIAL"


def test_match_release_report_source_revision_is_flat_only() -> None:
    # A report that omits the flat top-level source_revision but carries one
    # nested inside assessment_target is schema-nonconforming for
    # production_readiness_report (source_revision is a declared top-level
    # sibling, never nested) -- it must never be read from the nested location.
    report = trusted_production_report(source_revision=None)
    report["assessment_target"]["source_revision"] = "a" * 40
    result = match_release_report(v2_entry(source_revision="a" * 40), report)
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "source_revision_mismatch"


def test_unhashable_trusted_review_ref_never_crashes_coverage_build() -> None:
    coverage = build_code_review_coverage(
        candidate_source_revision="a" * 40,
        included_change_refs=["mr:1"],
        trusted_review_refs=["mr:1", {"oops": "dict"}],
    )
    assert coverage["status"] == "COMPLETE"


def test_unhashable_integrated_revision_value_never_crashes_coverage_build() -> None:
    coverage = build_code_review_coverage(
        candidate_source_revision="a" * 40,
        included_change_refs=["mr:1"],
        trusted_review_refs=["squash-sha"],
        integrated_revisions={"mr:1": ["squash-sha"]},
    )
    assert coverage["status"] == "PARTIAL"
    assert coverage["uncovered_change_refs"] == ["mr:1"]


def test_finalize_release_tolerates_explicit_none_checks() -> None:
    result = finalize_release(release_fixture(overall="READY", unknown_dimensions=[], checks=None))
    assert result.checks == []


def test_manifest_of_only_garbage_items_is_blocked_not_a_partial_analysis() -> None:
    # A non-empty manifest whose every item is a non-mapping must reach the
    # same BLOCKED hard stop as a literally empty manifest, never generate
    # phantom NOT_RUN check rows for unidentified services.
    result = run_release(["not-a-dict", 123, None])
    assert result.skill_result.status == "BLOCKED"
    assert result.checks == []


def test_manifest_mixing_valid_and_garbage_items_keeps_the_valid_ones() -> None:
    result = run_release([v1_entry(), "garbage", None])
    assert result.skill_result.status != "BLOCKED"


# ---------------------------------------------------------------------------
# Trusted reuse: no self-attestation, no fuzzy identity matching
# ---------------------------------------------------------------------------


def test_file_ready_report_cannot_self_attest() -> None:
    report = file_supplied_production_report(verdict="READY")
    assert classify_report_for_release(report)["trusted_for_gate"] is False


def test_untrusted_producer_report_is_not_gate_trusted_even_with_trusted_acquisition() -> None:
    # producer_trusted is a distinct trust axis from acquisition -- a report
    # with an otherwise-trusted acquisition (direct_child/runtime_validated)
    # must still never be gate-trusted if its own producer_trusted field is
    # explicitly False.
    report = trusted_production_report(verdict="READY", producer_trusted=False)
    assert classify_report_for_release(report)["trusted_for_gate"] is False

    # With identity sufficient to invoke, resolution correctly falls through
    # to a fresh invoke attempt (never reusing the untrusted report) --
    # mirroring test_authoritative_host_acquisition_is_not_gate_trusted_
    # for_a_report's own no-real-invocation-configured case.
    result = run_release(v2_entry(required=True), trusted_reports=[report])
    assert result.production_readiness == "UNKNOWN"
    assert result["production_readiness_source"] is None


def test_environment_alias_mismatch_is_unknown() -> None:
    report = trusted_production_report(environment="production")
    result = match_release_report(v2_entry(environment="prod"), report)
    assert result["status"] == "UNKNOWN"


def test_entry_declared_environment_does_not_reuse_a_report_that_omits_it() -> None:
    # Mirror of test_omitted_entry_environment_does_not_reuse_a_declared_
    # environment_report: the OTHER direction of the "either side declares
    # one" guard -- an entry pinned to a specific environment must never
    # reuse a report that omits environment entirely (None), the fixture
    # default. Both directions of this OR-guard must independently hold.
    report = trusted_production_report(environment=None)
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


def test_mutable_tag_identity_can_never_be_reused_even_on_an_exact_string_match() -> None:
    # Security: sibling gap to the invoke-path SHA-shape checks -- a mutable,
    # non-identity-pinning tag (release_ref and/or source_revision) is not
    # proof a trusted report was ever produced for the SAME concrete content,
    # since a tag can be repointed between when the report was produced and
    # now. An exact string match against such a tag must never itself
    # constitute reuse, even though _candidate_identity_sufficient would
    # equally refuse to *invoke* on that same identity.
    entry = v2_entry(repo="acme/checkout", service="checkout", release_ref="v1.2.3", source_revision="latest")
    report = trusted_production_report(
        verdict="READY", repo="acme/checkout", service="checkout", deployable="v1.2.3", source_revision="latest"
    )
    result = match_release_report(entry, report)
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "unpinned_identity"

    s = spy()
    required_entry = v2_entry(
        required=True, repo="acme/checkout", service="checkout", release_ref="v1.2.3", source_revision="latest"
    )
    release_result = run_release(required_entry, trusted_reports=[report], production_invoke=s)
    assert release_result.production_readiness == "UNKNOWN"
    assert s.calls == 0


def test_immutable_digest_release_ref_alone_can_still_be_reused_without_source_revision() -> None:
    # The legitimate case _release_ref_is_immutable_identity's leniency
    # exists for: a real (immutable, content-addressed) digest release_ref is
    # itself a trustworthy anchor for REUSE even with no source_revision
    # separately known -- unlike the stricter invoke-path requirement (a bare
    # digest alone is never sufficient to *invoke*, per
    # test_v2_image_digest_without_source_revision_is_unknown_before_invoke).
    entry = v2_entry(
        repo="acme/checkout", service="checkout", release_ref="sha256:" + "b" * 64, source_revision=None
    )
    report = trusted_production_report(
        verdict="READY", repo="acme/checkout", service="checkout", deployable="sha256:" + "b" * 64,
        source_revision=None,
    )
    assert match_release_report(entry, report)["status"] == "MATCH"


def test_sha384_and_sha512_digests_are_also_recognized_as_immutable() -> None:
    # The digest-algorithm allowlist covers every genuine, registered
    # content-hash algorithm this codebase might reasonably encounter, not
    # only sha256 -- a real sha384/sha512 digest must not be rejected merely
    # because every OTHER fixture in this file happens to use sha256. Each
    # algorithm's hex portion must be its OWN correct length (sha384=96,
    # sha512=128) -- reusing sha256's 64-char length here would make this
    # test pass without ever exercising a digest shaped like a real
    # sha384/sha512 hash at all.
    for algo, hex_length in (("sha384", 96), ("sha512", 128)):
        digest = f"{algo}:" + "b" * hex_length
        entry = v2_entry(repo="acme/checkout", service="checkout", release_ref=digest, source_revision=None)
        report = trusted_production_report(
            verdict="READY", repo="acme/checkout", service="checkout", deployable=digest, source_revision=None,
        )
        assert match_release_report(entry, report)["status"] == "MATCH", algo


def test_matching_source_revision_never_redeems_a_mutable_release_ref_for_reuse() -> None:
    # Security: release_ref is the actual deployable identity match already
    # checks via exact string equality against the report's own
    # head_revision_or_digest -- a validly SHA-shaped source_revision must
    # never substitute for release_ref's own immutability on the reuse path,
    # even when it also matches the report's. A mutable tag (e.g. "v1.2.3")
    # can be repointed to entirely different, unreviewed content between when
    # a trusted report was produced and now; a stale/replayed source_revision
    # value that happens to still match tells us nothing about what the tag
    # resolves to today. Unlike the invoke path (where the freshly-invoked
    # child independently re-validates build provenance), reuse performs no
    # such re-verification -- it is pure static string matching.
    entry = v2_entry(
        repo="acme/checkout", service="checkout", release_ref="v1.2.3", source_revision="f" * 40
    )
    stale_report = trusted_production_report(
        verdict="READY", repo="acme/checkout", service="checkout", deployable="v1.2.3", source_revision="f" * 40
    )
    result = match_release_report(entry, stale_report)
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "unpinned_identity"

    # The stale report is never reused -- but since source_revision is
    # validly SHA-shaped, resolve_production_readiness correctly falls
    # through to a FRESH invoke attempt instead (the invoke gate's own,
    # separately-justified leniency), rather than silently going UNKNOWN.
    s = spy()
    required_entry = v2_entry(
        required=True, repo="acme/checkout", service="checkout", release_ref="v1.2.3", source_revision="f" * 40
    )
    release_result = run_release(required_entry, trusted_reports=[stale_report], production_invoke=s)
    assert release_result.production_readiness_source is None
    assert s.calls == 1


def test_mutable_name_tag_ref_shaped_like_a_digest_is_never_an_immutable_anchor() -> None:
    # Security: the digest algorithm component must be an explicit allowlist
    # of genuine, registered content-hash algorithms, not open-ended --
    # otherwise an ordinary, fully mutable `name:tag` container reference
    # (a common CI convention: tagging an image with a commit SHA, e.g.
    # "nightly-build:<40 hex chars>") is syntactically indistinguishable from
    # a genuine `algo:hexdigest` content digest whenever the tag happens to
    # be hex-shaped -- letting a stale trusted report keyed to such a tag be
    # reused as READY even though the registry could have repointed that tag
    # to entirely different, unreviewed content since the report was produced.
    mutable_tag_shaped_like_digest = "nightly-build:" + "a1b2c3d4e5" * 4
    entry = v2_entry(
        required=True, repo="acme/checkout", service="checkout",
        release_ref=mutable_tag_shaped_like_digest, source_revision=None,
    )
    stale_report = trusted_production_report(
        verdict="READY", repo="acme/checkout", service="checkout",
        deployable=mutable_tag_shaped_like_digest, source_revision=None,
    )
    result = match_release_report(entry, stale_report)
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "unpinned_identity"

    s = spy()
    release_result = run_release(entry, trusted_reports=[stale_report], production_invoke=s)
    assert release_result.production_readiness_source is None
    assert release_result.production_readiness == "UNKNOWN"
    assert s.calls == 0


def test_wrong_length_hex_after_a_real_algorithm_name_is_never_an_immutable_anchor() -> None:
    # Security: sixth variant of the same defect family -- round 13's
    # algorithm allowlist alone isn't enough if the hex-length requirement
    # stays open-ended ("32 or more" for every algorithm interchangeably).
    # A repository/artifact store literally named "sha256" carrying a
    # mutable, git-SHA-style tag (e.g. "sha256:<40 hex chars>") is wrong
    # length for a real sha256 digest (which is always exactly 64 hex chars)
    # but would still pass an open-ended length check -- reopening round 13's
    # exact "mutable tag mistaken for immutable digest" exploit shape under
    # one of the three now-allowlisted algorithm names instead of an
    # arbitrary one.
    wrong_length_variants = [
        "sha256:" + "a" * 40,   # too short for sha256 (needs 64)
        "sha256:" + "a" * 128,  # too long for sha256
        "sha384:" + "a" * 64,   # too short for sha384 (needs 96)
        "sha512:" + "a" * 64,   # too short for sha512 (needs 128)
    ]
    for fake_digest in wrong_length_variants:
        entry = v2_entry(
            required=True, repo="acme/checkout", service="checkout",
            release_ref=fake_digest, source_revision=None,
        )
        stale_report = trusted_production_report(
            verdict="READY", repo="acme/checkout", service="checkout",
            deployable=fake_digest, source_revision=None,
        )
        result = match_release_report(entry, stale_report)
        assert result["status"] == "UNKNOWN", fake_digest
        assert result["reason"] == "unpinned_identity", fake_digest


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


def test_production_readiness_ref_pin_cannot_resolve_a_genuine_conflict() -> None:
    # Security: production_readiness_ref is caller/manifest-supplied text --
    # untrusted -- and must never be usable to silently resolve a genuine
    # disagreement between two trusted, identity-matching reports by simply
    # hiding the one it doesn't name (e.g. pinning past a fresher NOT_READY
    # report to reuse a stale favorable READY one). Conflict detection runs
    # on the full unpinned match set; the pin narrows only among matches that
    # already agree.
    unpinned_ready = trusted_production_report(verdict="READY", report_ref="run-1")
    pinned_not_ready = trusted_production_report(verdict="NOT_READY", report_ref="run-2")
    s = spy()
    result = run_release(
        v2_entry(required=True, production_readiness_ref="run-2"),
        trusted_reports=[unpinned_ready, pinned_not_ready],
        production_invoke=s,
    )
    assert result["production_readiness_source"] is None
    assert result.production_readiness == "UNKNOWN"
    assert s.calls == 0


def test_production_readiness_ref_pin_selects_among_agreeing_matches() -> None:
    # A pin still does useful work when the identity-matching reports do NOT
    # disagree: it selects which specific (already-agreeing) report object is
    # attributed as the reused source, without needing to override a conflict.
    # Both reports share the identical verdict ("READY"), and run_release's
    # own output never exposes which underlying report object was picked --
    # only resolve_production_readiness's "report" field does -- so this
    # calls it directly and asserts on the pinned report's own report_ref,
    # the only thing that can actually distinguish "pin honored" from
    # "pin ignored, first match picked by coincidence."
    older_ready = trusted_production_report(verdict="READY", report_ref="run-1")
    newer_ready = trusted_production_report(verdict="READY", report_ref="run-2")
    result = resolve_production_readiness(
        v2_entry(required=True, production_readiness_ref="run-2"),
        trusted_reports=[older_ready, newer_ready],
    )
    assert result["status"] == "READY"
    assert result["source"] == "REUSED"
    assert result["report"]["report_ref"] == "run-2"


def test_non_resolving_pin_never_discards_agreeing_trusted_evidence() -> None:
    # Security: a production_readiness_ref that names no report among an
    # already-agreeing trusted match set (a typo, a stale/rotated ref, or
    # untrusted manifest text an attacker deliberately points at nothing)
    # must never suppress reuse of that evidence -- since every remaining
    # match already agrees in verdict, which one gets attributed cannot
    # change the resolved status, so falling through past reuse (into a
    # fresh, potentially more favorable invocation, or UNKNOWN) would
    # silently discard known trusted evidence for no security benefit.
    trusted_not_ready = trusted_production_report(verdict="NOT_READY", report_ref="run-1")
    s = spy()
    result = run_release(
        v2_entry(required=True, production_readiness_ref="no-such-ref"),
        trusted_reports=[trusted_not_ready],
        production_invoke=s,
    )
    assert result["production_readiness_source"] == "REUSED"
    assert result.production_readiness == "NOT_READY"
    assert s.calls == 0


def test_authoritative_host_acquisition_is_not_gate_trusted_for_a_report() -> None:
    # Security: a whole production_readiness_report's gate trust turns only on
    # direct_child/runtime_validated acquisition (an actual invocation this
    # release performed or that a trusted runtime performed for it) --
    # "authoritative_host"/"trusted_runtime" are evidence-level authority
    # concepts used elsewhere (e.g. code_review_coverage, provenance.sources)
    # and must never let a forged/replayed report self-attest whole-artifact
    # trust and get reused as READY without any real invocation.
    forged = trusted_production_report(verdict="READY", acquisition="authoritative_host")
    assert classify_report_for_release(forged)["trusted_for_gate"] is False
    forged2 = trusted_production_report(verdict="READY", acquisition="trusted_runtime")
    assert classify_report_for_release(forged2)["trusted_for_gate"] is False

    # With no real invocation configured, neither forged report is reused --
    # the result is UNKNOWN, never a self-attested READY.
    result = run_release(
        v2_entry(required=True),
        trusted_reports=[forged, forged2],
    )
    assert result["production_readiness_source"] is None
    assert result.production_readiness == "UNKNOWN"


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
    # evidence into another candidate's verdict. The two entries deliberately
    # share the SAME source_revision (and the bundle declares repo/service),
    # so the only thing that could prevent a leak here is repo/service
    # scoping itself -- a source_revision-only mismatch (a weaker, already
    # separately covered scenario) is not what's being tested.
    coverage_for_checkout = build_code_review_coverage(
        candidate_source_revision="a" * 40,
        included_change_refs=["mr:1"],
        trusted_review_refs=["mr:1"],
        repo="acme/checkout",
        service="checkout",
    )
    checkout_entry = v2_entry(required=True, repo="acme/checkout", service="checkout", source_revision="a" * 40)
    billing_entry = v2_entry(required=True, repo="acme/billing", service="billing", source_revision="a" * 40)
    seen_coverage: dict = {}

    def production_invoke(candidate: dict, *, assessment_context: dict | None = None):
        seen_coverage[candidate["repo"]] = (assessment_context or {}).get("inputs", {}).get("code_review_coverage")
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
    # Positive control: checkout (the entry the bundle was actually assembled
    # for) DOES receive it -- proving the bundle isn't simply rejected
    # outright, which would make the negative assertion below vacuous.
    assert seen_coverage["acme/checkout"] is not None
    # billing's own invocation must never see checkout's coverage bundle,
    # despite sharing the identical source_revision.
    assert seen_coverage["acme/billing"] is None


def test_code_review_coverage_omitting_repo_service_never_applies_even_to_the_matching_revision_entry() -> None:
    # Security: round 4's fix requires repo/service to be declared on the
    # bundle for it to ever be applied at all -- not merely "compared when
    # present". A bundle that omits them entirely must be treated as not
    # supplied even for the ONE entry whose source_revision it matches
    # (unlike test_code_review_coverage_never_leaks_across_manifest_entries
    # above, which only asserts this for the non-matching-revision entry).
    coverage_missing_repo_service = build_code_review_coverage(
        candidate_source_revision="a" * 40,
        included_change_refs=["mr:1"],
        trusted_review_refs=["mr:1"],
    )
    assert coverage_missing_repo_service["repo"] is None
    assert coverage_missing_repo_service["service"] is None
    checkout_entry = v2_entry(required=True, repo="acme/checkout", service="checkout", source_revision="a" * 40)

    def production_invoke(candidate: dict, *, assessment_context: dict | None = None):
        supplied = (assessment_context or {}).get("inputs", {}).get("code_review_coverage")
        assert supplied is None
        return trusted_production_report(
            verdict="READY",
            repo=candidate["repo"],
            service=candidate["service"],
            deployable=candidate["head_revision_or_digest"],
            source_revision=candidate["source_revision"],
        )

    run_release(
        checkout_entry,
        trusted_reports=[],
        production_invoke=production_invoke,
        code_review_coverage=coverage_missing_repo_service,
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


def test_empty_included_change_refs_is_unknown_not_trivially_complete() -> None:
    # Security: a release range with zero enumerated changes must fail
    # closed to UNKNOWN, never be treated as trivially COMPLETE -- an
    # authoritative-looking bundle claiming COMPLETE with no actually-
    # enumerated changes is exactly the kind of no-real-work self-attestation
    # this module otherwise treats as a security concern (it would otherwise
    # satisfy _coverage_is_trustworthy_and_complete and get stamped
    # trusted_runtime despite representing zero real review evidence).
    coverage = build_code_review_coverage(
        candidate_source_revision="a" * 40,
        included_change_refs=[],
        trusted_review_refs=[],
        repo="acme/checkout",
        service="checkout",
    )
    assert coverage["status"] == "UNKNOWN"


def test_malformed_change_ref_cannot_be_laundered_into_covered_by_a_placeholder_collision() -> None:
    # Security: a malformed entry's synthetic display placeholder
    # (__unresolvable_change_<index>__) must never itself participate in the
    # covered/uncovered string comparison -- a genuine ref, or an
    # integrated_revisions value, that happens to collide with that exact
    # placeholder text must never launder the malformed entry into
    # "reviewed," even though trusted_review_refs/included_change_refs come
    # from a trusted SCM-enumeration boundary and such a collision would
    # require either a harness bug or an unusual real ref/branch name.
    coverage = build_code_review_coverage(
        candidate_source_revision="a" * 40,
        included_change_refs=[
            {"bad_key_no_ref": "whatever"},           # malformed -> index 0
            {"ref": "__unresolvable_change_0__"},     # a REAL ref colliding with index 0's placeholder
        ],
        trusted_review_refs=["__unresolvable_change_0__"],
        repo="acme/widgets", service="widgets-api",
    )
    assert coverage["status"] == "PARTIAL"
    assert coverage["uncovered_change_refs"] == ["__unresolvable_change_0__"]


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


def test_existing_checks_are_attributed_to_the_correct_entry() -> None:
    # A multi-entry manifest: check_spy.run must receive enough identity to
    # discriminate which candidate it's being asked to check for pr-review/
    # k8s/incident-rca (run-check.md's own "once per service"/"per resolved
    # MR" contract), and the recorded `checks` entries must carry that
    # attribution too, not just a bare check name.
    seen_calls: list = []

    class _AttributingSpy:
        def run(self, name: str, **kwargs: object) -> dict:
            seen_calls.append((name, kwargs.get("repo"), kwargs.get("service")))
            return {"status": "PASS"}

    entry_a = v1_entry(repo="acme/a", service="a")
    entry_b = v1_entry(repo="acme/b", service="b")
    result = run_release([entry_a, entry_b], check_spy=_AttributingSpy())

    assert ("pr_review", "acme/a", "a") in seen_calls
    assert ("pr_review", "acme/b", "b") in seen_calls
    checks_by_repo = {(c["name"], c["repo"]) for c in result.get("checks", [])}
    assert ("pr_review", "acme/a") in checks_by_repo
    assert ("pr_review", "acme/b") in checks_by_repo


def test_not_ready_short_circuit_does_not_report_existing_checks_as_passed_if_not_run() -> None:
    # A check_spy with mixed outcomes: every executed check reporting PASS must
    # be marked executed=True (meaningful even when k8s independently fails).
    class _MixedSpy:
        def run(self, name: str, **_: object) -> dict:
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
        def run(self, name: str, **_: object) -> dict:
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
        def run(self, name: str, **_: object) -> dict:
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
    #
    # This asserts specifically WHICH entry got voided, not merely that
    # *some* entry did (a regression that collapsed the two entries' keys
    # together -- voiding both, or voiding the wrong one -- would still pass
    # a weaker "at least one entry moved" assertion). Each entry is given its
    # own distinct trusted report so per-entry attribution (via the
    # `environment` field on `production_readiness_results`) can be checked.
    staging_entry = v2_entry(
        required=True, repo="acme/checkout", service="checkout", environment="staging",
        source_revision="a" * 40, release_ref="a" * 40,
    )
    prod_entry = v2_entry(
        required=True, repo="acme/checkout", service="checkout", environment="prod",
        source_revision="a" * 40, release_ref="a" * 40,
    )
    staging_report = trusted_production_report(
        verdict="READY", environment="staging", deployable="a" * 40, source_revision="a" * 40
    )
    prod_report = trusted_production_report(
        verdict="NOT_READY", environment="prod", deployable="a" * 40, source_revision="a" * 40
    )
    staging_key = ("acme/checkout", "checkout", "staging")
    prod_key = ("acme/checkout", "checkout", "prod")

    result = run_release(
        [staging_entry, prod_entry],
        trusted_reports=[staging_report, prod_report],
        start_ref={staging_key: "a" * 40, prod_key: "a" * 40},
        final_ref={staging_key: "b" * 40, prod_key: "a" * 40},
    )
    assert result.candidate_changed_during_review is True
    # Worst-first: prod's own resolved NOT_READY (severity 3) caps the overall
    # verdict past staging's mere UNKNOWN (severity 2) -- proving prod's real,
    # unmasked verdict actually feeds the aggregate, not just "some entry
    # went UNKNOWN."
    assert result.overall == "NOT_READY"

    by_environment = {r["environment"]: r for r in result.production_readiness_results}
    assert by_environment["staging"] == {
        "repo": "acme/checkout", "service": "checkout", "environment": "staging",
        "source": None, "verdict": "UNKNOWN",
    }
    assert by_environment["prod"] == {
        "repo": "acme/checkout", "service": "checkout", "environment": "prod",
        "source": "REUSED", "verdict": "NOT_READY",
    }


def test_freshness_fence_key_matching_is_normalized_not_a_raw_tuple() -> None:
    # Security: every other identity comparison in this module normalizes
    # before comparing (canonical repo form, case-insensitive environment) --
    # a raw `dict.get()` on the unnormalized (repo, service, environment)
    # tuple would let a differently-cased environment (or a repo string
    # with/without a ".git" suffix) silently miss the freshness-fence lookup,
    # going inert (ref_moved=False) instead of failing closed, even though
    # match_release_report's own case/format-insensitive comparison would
    # still happily reuse a report keyed to the other spelling.
    entry = v2_entry(repo="acme/checkout", service="checkout", environment="Production")
    normalized_key = ("acme/checkout", "checkout", "production")

    result = run_release(
        entry,
        start_ref={normalized_key: "a" * 40},
        final_ref={normalized_key: "b" * 40},
    )
    assert result.candidate_changed_during_review is True
    assert result.overall == "UNKNOWN"

    repo_with_git_suffix = v2_entry(repo="https://github.com/acme/checkout.git", service="checkout")
    canonical_repo_key = ("https://github.com/acme/checkout", "checkout", None)
    repo_result = run_release(
        repo_with_git_suffix,
        start_ref={canonical_repo_key: "a" * 40},
        final_ref={canonical_repo_key: "b" * 40},
    )
    assert repo_result.candidate_changed_during_review is True
    assert repo_result.overall == "UNKNOWN"


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
