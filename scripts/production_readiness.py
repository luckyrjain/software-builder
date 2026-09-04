"""Pure evidence-aggregation and gating logic for the production-readiness-review orchestrator.

This module holds only deterministic, side-effect-free logic: verdict aggregation,
evidence-authority policy, prerequisite reuse/refresh decisions, and the individual
readiness gates (CI, build provenance, SCM policy, operational evidence, capacity,
dependency). Registry wiring, dispatcher integration, and child invocation live
outside this module; `dispatch_child` here is a policy-level adapter only.
"""

from __future__ import annotations

import dataclasses
from types import MappingProxyType
from typing import Any, Callable, Mapping, MutableMapping, Optional, Sequence

from scripts.registry.assessment_target import safe_same_environment, target_of
from scripts.registry.skill_result import SkillResult, derive_execution_status
from scripts.registry.validation_primitives import as_mapping

# ---------------------------------------------------------------------------
# Canonical vocab
# ---------------------------------------------------------------------------

DIMENSION_STATUSES = ("PASS", "CONDITIONAL", "FAIL", "UNKNOWN", "NOT_APPLICABLE")

# The strong half of `artifact_trust.AUTHORITIES`; the rest ("caller", "model_knowledge") are
# weak by definition, so this module names only the half its gates actually test membership in.
STRONG_AUTHORITIES = frozenset({"repository", "authoritative_host", "trusted_runtime"})

ENV_SENSITIVE_DIMENSIONS = frozenset(
    {
        "observability",
        "capacity",
        "deployment_risk",
        "operational_ownership",
        "rollback_and_abort",
        "post_deploy_verification_plan",
        "recovery",
    }
)

# Immutable (MappingProxyType): this table enforces gate-policy.md's "never dispatch a specialist
# with a knowingly-incomplete mandatory input" -- unlike a plain dict, it can't be mutated
# in-process (accidentally or otherwise) to silently disable that gate for the rest of the run.
CHILD_MANDATORY_INPUTS: Mapping[str, Sequence[str]] = MappingProxyType(
    {
        "pr-review": ("merge_request_iid", "project", "expected_head_sha"),
        "deployment-risk-review": ("change_description",),
        "security-review": ("review_target",),
        "observability-review": ("service_name", "observability_material"),
        "resilience-review": ("resilience_behavior", "dependency_paths"),
        "api-design-review": ("api_spec",),
        "performance-review": ("reviewed_content",),
        "capacity-planner": ("demand_data", "forecast_horizon"),
        "dependency-upgrade-review": ("dependency_name", "current_version", "target_version"),
    }
)

DATABASE_REVIEW_ONE_OF = ("schema", "migration_script", "queries")

# Children whose mandatory input is satisfied by ANY ONE of several fields, not ALL of them.
# "changed_paths" is change-impact-analyzer's own real diff-carrier field (see its `analyze_change`
# contract), documented alongside the other four in reference/child-input-map.md.
CHILD_ONE_OF_INPUTS: Mapping[str, Sequence[str]] = MappingProxyType(
    {
        "database-review": DATABASE_REVIEW_ONE_OF,
        "change-impact-analyzer": ("system_design_spec", "mr_context", "diff_text", "change_text", "changed_paths"),
    }
)


@dataclasses.dataclass(frozen=True)
class GateResult:
    """Generic gate outcome: status plus an optional machine-readable reason."""

    status: str
    reason: str = ""


# ---------------------------------------------------------------------------
# Evidence-authority helpers (shared by every gate below)
# ---------------------------------------------------------------------------


def _authority_set(value: Any) -> set:
    """Normalize an authority value (bare string or iterable of strings) to a set of strings.

    A Mapping is rejected outright rather than iterated: `set({"repository": "REVOKED"})`
    would silently collect the *keys*, letting a child name a strong authority as a dict key
    with an arbitrary (even negating) value and still be read back as authoritative.
    """
    if not value:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, Mapping):
        return set()
    try:
        return set(value)
    except TypeError:
        return set()


def _is_strong_authority(value: Any) -> bool:
    """True only when value is a hashable string naming a strong authority.

    A scalar `*_authority`/`acquisition` field is normally tested with `value in
    STRONG_AUTHORITIES`; an unhashable shape (a list, a dict) raises TypeError there instead of
    failing closed, taking down the whole aggregation over one malformed field. Every such
    membership test in this module should route through this helper instead of the bare `in`.
    """
    return isinstance(value, str) and value in STRONG_AUTHORITIES


def is_host_or_runtime_acquisition(value: Any) -> bool:
    """True only when value is a hashable string naming authoritative_host or trusted_runtime.

    CI and code-review coverage evidence specifically excludes "repository" acquisition (a static
    repo-content read is not a live CI/review observation) -- narrower than STRONG_AUTHORITIES,
    but the same unhashable-value hazard applies to a bare `in {...}` membership test.
    """
    return isinstance(value, str) and value in {"authoritative_host", "trusted_runtime"}


def _is_true(value: Any) -> bool:
    """Strict boolean read: only the literal `True` counts.

    A truthy non-bool (the string "false", a nonzero int, a non-empty list) must never be read as
    a confirmed affirmative signal for a field that is only ever supposed to carry a real boolean
    (`complete`, `reversible`, `required`, `producer_trusted`, `bypass_approved`, ...) -- bare
    Python truthiness would treat the string "false" as true.
    """
    return value is True


def _minimum_authority_met(evidence_authorities: Optional[Mapping[str, Any]]) -> bool:
    """True only when EVERY evidence entry backing a conclusion is *purely* strongly authoritative.

    A single weakly-authoritative entry must not be laundered into a strong conclusion merely
    because some unrelated entry in the same map happens to be strong (round-3 fix). Nor may an
    entry that mixes a strong and a weak authority together (`{"caller", "repository"}`) pass on
    the strength of its strong half alone -- per evidence-authority-policy.md rule 4, mixed
    evidence downgrades the whole entry, so each entry's authority set must be a *subset* of
    `STRONG_AUTHORITIES`, not merely intersect it.
    """
    # A malformed evidence_authorities shape (a list, a string, ...) from an untrusted or buggy
    # child degrades to "no authoritative evidence" rather than raising: a crash here would take
    # down the whole aggregation instead of failing closed on just the affected dimension.
    evidence_authorities = as_mapping(evidence_authorities)
    if not evidence_authorities:
        return False
    for authorities in evidence_authorities.values():
        authority_set = _authority_set(authorities)
        if not authority_set or not authority_set.issubset(STRONG_AUTHORITIES):
            return False
    return True


_KNOWN_CRITICALITY_TIERS = frozenset({"tier0", "tier1", "tier2", "tier3", "unknown"})


def _tier_requires_strict_unknown(criticality: str) -> bool:
    """True when caller-only evidence must be UNKNOWN (never CONDITIONAL) at this tier.

    Per operational-gates.md, `unknown` criticality is treated as strictly as tier0/tier1 -- never
    as a permissive default. A value outside the five-tier vocabulary (a typo, `None`, wrong
    casing, an unrecognized string) must not silently take the permissive tier2/tier3 branch
    either: it is treated at least as strictly as `unknown`.
    """
    if not isinstance(criticality, str) or criticality not in _KNOWN_CRITICALITY_TIERS:
        # An unhashable shape (a list, a dict) must degrade to the strict branch, never raise --
        # `in _KNOWN_CRITICALITY_TIERS` alone would crash on `criticality=['tier3']`.
        return True
    return criticality in ("tier0", "tier1", "unknown")


# ---------------------------------------------------------------------------
# Dimension model + verdict aggregation
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Dimension:
    name: str
    status: str
    applicability: str = "REQUIRED"
    evidence_status: Optional[str] = None

    def __post_init__(self) -> None:
        if self.status not in DIMENSION_STATUSES:
            raise ValueError(f"Dimension status must be one of {DIMENSION_STATUSES}, got {self.status!r}")
        if self.evidence_status is None:
            object.__setattr__(
                self, "evidence_status", "UNKNOWN" if self.status == "UNKNOWN" else "OBSERVED"
            )
        elif self.status in ("PASS", "CONDITIONAL", "NOT_APPLICABLE") and self.evidence_status == "UNKNOWN":
            # A self-contradictory artifact: aggregate_verdict would fold PASS/CONDITIONAL into a
            # READY/CONDITIONAL verdict, and NOT_APPLICABLE deletes the dimension from the
            # required set entirely (an even MORE favorable outcome), while aggregate_readiness's
            # own envelope would simultaneously mark the evidence UNKNOWN -- per accept_child_
            # result's own precedent (claiming inapplicability must never require less authority
            # than claiming PASS would), NOT_APPLICABLE is included alongside PASS/CONDITIONAL.
            raise ValueError(
                f"A {self.status} dimension cannot declare evidence_status='UNKNOWN'"
            )


def _is_required(d: Dimension) -> bool:
    return d.applicability != "NOT_APPLICABLE" and d.status != "NOT_APPLICABLE"


def _required_statuses(dims: Sequence[Dimension]) -> list:
    return [d.status for d in dims if _is_required(d)]


def aggregate_verdict(dims: Sequence[Dimension], waivers: Optional[Sequence[Mapping]] = None) -> str:
    """Worst-first aggregation. Waivers never promote a verdict — see aggregate_report."""

    statuses = _required_statuses(dims)
    if any(s == "FAIL" for s in statuses):
        return "NOT_READY"
    if any(s == "UNKNOWN" for s in statuses):
        return "UNKNOWN"
    if any(s == "CONDITIONAL" for s in statuses):
        return "CONDITIONAL"
    return "READY"


def summarize_required_passes(dims: Sequence[Dimension]) -> int:
    return sum(1 for d in dims if _is_required(d) and d.status == "PASS")


def _is_valid_waiver(waiver: Mapping) -> bool:
    if not isinstance(waiver, Mapping):
        return False
    if not waiver.get("accepted_by") or not waiver.get("evidence_ref"):
        return False
    expires_at = waiver.get("expires_at")
    if expires_at:
        try:
            import datetime

            expiry = datetime.datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if expiry.tzinfo is None:
                # A naive timestamp (no "Z"/offset) can't be compared to an aware "now" below --
                # treat it as UTC rather than letting the comparison raise TypeError.
                expiry = expiry.replace(tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            if expiry < now:
                return False
        except Exception:
            # Broad on purpose: `str(expires_at)` itself can raise (a caller-supplied object with
            # a broken __str__), not just datetime.fromisoformat's documented ValueError/TypeError
            # -- any failure parsing an untrusted, caller-controlled expiry must degrade to
            # "invalid waiver," never crash the whole report.
            return False
    return True


def aggregate_report(
    dims: Sequence[Dimension],
    waivers: Optional[Sequence[Mapping]] = None,
) -> MutableMapping[str, Any]:
    verdict = aggregate_verdict(dims, waivers=waivers)
    try:
        waiver_candidates = list(waivers) if waivers else []
    except Exception:
        # Broad on purpose: a non-iterable `waivers` value raises TypeError at this line, but an
        # iterable whose iterator raises mid-iteration (a hostile/buggy generator) can raise
        # anything -- either way this is untrusted, caller-controlled input, and must degrade to
        # "no waivers supplied," never crash the whole report.
        waiver_candidates = []
    valid_waivers = [w for w in waiver_candidates if _is_valid_waiver(w)]
    return {
        "verdict": verdict,
        "dimension_statuses": list(dims),
        "waivers": valid_waivers,
        "required_passes": summarize_required_passes(dims),
    }


@dataclasses.dataclass(frozen=True)
class ReadinessResult:
    verdict: str
    skill_result_status: str
    evidence_status: str
    dimensions: Sequence[Dimension] = ()


def aggregate_readiness(
    required_dimensions: Sequence[Dimension],
    waivers: Optional[Sequence[Mapping]] = None,
) -> ReadinessResult:
    verdict = aggregate_verdict(required_dimensions, waivers=waivers)
    required = [d for d in required_dimensions if _is_required(d)]
    unresolved = [d for d in required if d.evidence_status == "UNKNOWN" or d.status == "UNKNOWN"]
    skill_result_status, evidence_status = derive_execution_status(unknowns=unresolved)
    return ReadinessResult(
        verdict=verdict,
        skill_result_status=skill_result_status,
        evidence_status=evidence_status,
        dimensions=tuple(required_dimensions),
    )


# ---------------------------------------------------------------------------
# Evidence-authority policy: child-result acceptance
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class AcceptedChildResult:
    status: str
    trusted_for_gate: bool
    reason: str = ""


def _effective_source_revision(obj: Mapping[str, Any]) -> Optional[str]:
    """Best-effort revision identity, resolved through the same nested-first precedence `target_of`
    gives every other identity comparison: a nested `assessment_target`/`target`'s own
    source_revision/head_sha/head_revision_or_digest is checked before any flat top-level field.

    Without this, a caller could supply a stale flat `source_revision` alongside a fresher nested
    `assessment_target` and have every evidence validator that calls this helper directly on a raw
    candidate (validate_ci, validate_code_review_coverage, validate_build_provenance, the
    dependency-CI scope check) silently validate against the stale flat revision while
    `_identity_mismatch`/`dispatch_child` bind children to the fresher nested one -- two different
    "current" identities in the same run. `_has_minimum_candidate_identity` accepts a
    project+merge_request_iid+head_sha candidate as a first-class shape carrying no
    `source_revision` at all, so `head_sha` and `head_revision_or_digest` are both checked too.

    Falls back to `obj`'s own flat fields when the nested target exists but simply doesn't declare
    any identity field itself (e.g. a carrier that only declares `environment`) -- the same
    per-field nested-then-flat precedence `_effective_environment` already gives `environment`.
    Without this, a nested carrier declaring unrelated fields would shadow a real flat identity
    entirely, wrongly reporting no identity at all for a fully-identified candidate.

    Coerces a non-Mapping `obj` to `{}` up front -- some callers (e.g. `_identity_mismatch`'s
    `expected` side, sourced from a caller-supplied `candidate`) may not have pre-validated it.
    """
    obj = as_mapping(obj)
    target = target_of(obj) or {}
    revision = target.get("source_revision") or target.get("head_sha") or target.get("head_revision_or_digest")
    if revision is None:
        revision = obj.get("source_revision") or obj.get("head_sha") or obj.get("head_revision_or_digest")
    return revision


def _effective_head_digest(obj: Mapping[str, Any]) -> Optional[str]:
    """Best-effort `head_revision_or_digest` read, nested-first with the same per-field flat
    fallback `_effective_source_revision` gives the sibling identity fields.
    """
    obj = as_mapping(obj)
    target = target_of(obj) or {}
    digest = target.get("head_revision_or_digest")
    if digest is None:
        digest = obj.get("head_revision_or_digest")
    return digest


def _identity_mismatch(child: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    child_rev = _effective_source_revision(child)
    child_head = _effective_head_digest(child) or child_rev
    # The expected/candidate side gets the same nested-first resolution as the child side: if it
    # names its identity via a nested assessment_target/target (rather than flat top-level
    # fields), that nested value is authoritative -- a flat field alongside it must never be
    # silently preferred over (or allowed to shadow) the candidate's own declared canonical target.
    expected_rev = _effective_source_revision(expected)
    expected_head = _effective_head_digest(expected) or expected_rev
    if not expected_rev and not expected_head:
        # The expected side (an empty/unresolved candidate) names no identity at all -- there is
        # nothing to bind the child's evidence to, so this is unknown scope, not a vacuous match.
        # Only a genuinely absent expected side (checked by the caller via `is not None`) skips
        # this fence entirely; an empty mapping must not.
        return True
    # When the expected side names an identity, the child MUST supply a matching one -- a child
    # that names no revision/target at all is evidence of unknown scope, not a safe match.
    if expected_rev and (not child_rev or expected_rev != child_rev):
        return True
    if expected_head and (not child_head or expected_head != child_head):
        return True
    return False


def accept_child_result(
    child: Mapping[str, Any],
    *,
    expected_target: Optional[Mapping[str, Any]] = None,
    candidate: Optional[Mapping[str, Any]] = None,
    dimension: Optional[str] = None,
    criticality: Optional[str] = None,
) -> AcceptedChildResult:
    child = as_mapping(child)
    target_ref = expected_target if expected_target is not None else candidate
    if target_ref is not None and _identity_mismatch(child, target_ref):
        return AcceptedChildResult(status="UNKNOWN", trusted_for_gate=False, reason="target_mismatch")

    if target_ref is not None:
        # Same binding this identity check just applied, extended to environment: a child result
        # scoped to a different environment than the one this dispatch/reuse was actually for must
        # not be recorded as this candidate's own evidence, per operational-gates.md's
        # environment-sensitivity rule. This is the one place dispatch_child's binding and
        # match_dimension_evidence's own separate environment fence both ultimately route through.
        if _environment_conflict(child, target_ref):
            return AcceptedChildResult(status="UNKNOWN", trusted_for_gate=False, reason="environment_mismatch")

    if child.get("producer_trusted", True) is not True:
        # Strict identity: a malformed non-bool value (a truthy string like "false") must never
        # be read as "trusted" just because it's Python-truthy.
        return AcceptedChildResult(status="UNKNOWN", trusted_for_gate=False, reason="untrusted_producer")

    status = child.get("status", "UNKNOWN")
    if status not in DIMENSION_STATUSES:
        # An unrecognized status (a typo, a child-specific vocabulary like "BLOCKED") must never
        # silently fall through an aggregator's status-string comparisons as an implicit PASS.
        status = "UNKNOWN"
    elif status in ("PASS", "CONDITIONAL", "NOT_APPLICABLE") and not _minimum_authority_met(
        child.get("evidence_authorities")
    ):
        # The no-laundering rule applies to PASS/CONDITIONAL/NOT_APPLICABLE alike: per evidence-
        # authority-policy.md rule 3, evidence that is only caller/model_knowledge-authoritative is
        # UNKNOWN. NOT_APPLICABLE is included because it is the MORE favorable outcome (deletes the
        # dimension from the required set entirely) -- claiming inapplicability must never require
        # LESS authority than claiming PASS would, matching the precedent evaluate_recovery already
        # sets for its own reversible/NOT_APPLICABLE shortcut.
        # A FAIL a child already reported is not softened just because it lacked authority.
        status = "UNKNOWN"
    return AcceptedChildResult(status=status, trusted_for_gate=True, reason="")


# ---------------------------------------------------------------------------
# Trusted prerequisite resolution (slice 4)
# ---------------------------------------------------------------------------


def _child_mandatory_inputs_satisfied(child_name: str, inputs: Mapping[str, Any]) -> bool:
    one_of = CHILD_ONE_OF_INPUTS.get(child_name)
    if one_of is not None:
        return any(inputs.get(key) for key in one_of)
    required = CHILD_MANDATORY_INPUTS.get(child_name)
    if required is None:
        # An unmapped/unrecognized child's requirements are unknown -- never assume satisfied.
        return False
    return all(inputs.get(key) for key in required)


def _mandatory_inputs_available(artifact_type: str, mandatory_inputs: Optional[Mapping[str, Any]]) -> bool:
    mandatory_inputs = as_mapping(mandatory_inputs) if mandatory_inputs is not None else {}
    if not mandatory_inputs:
        return False
    child_name = {
        "change_impact_report": "change-impact-analyzer",
        "deployment_risk_report": "deployment-risk-review",
    }.get(artifact_type)
    if child_name is None:
        return False
    return _child_mandatory_inputs_satisfied(child_name, mandatory_inputs)


def resolve_prerequisite(
    artifact_type: str,
    *,
    supplied: Optional[Mapping[str, Any]] = None,
    candidate: Optional[Mapping[str, Any]] = None,
    invoke_spy: Optional[Callable[..., Any]] = None,
    mandatory_inputs: Optional[Mapping[str, Any]] = None,
) -> MutableMapping[str, Any]:
    if candidate is None:
        # No candidate identity to bind reuse/refresh to -- never resolve a prerequisite blind.
        return {"status": "UNKNOWN", "mode": None}
    candidate = as_mapping(candidate)
    if supplied is not None:
        supplied = as_mapping(supplied)
        accepted = accept_child_result(supplied, candidate=candidate)
        # coverage_status is a change_impact_report-specific field (composition_contracts.yaml);
        # other prerequisite artifacts (e.g. deployment_risk_report) have no such field and must
        # not be required to carry it.
        stale = artifact_type == "change_impact_report" and supplied.get("coverage_status") != "COMPLETE"
        if not stale and accepted.status in ("PASS", "FAIL", "CONDITIONAL", "NOT_APPLICABLE"):
            # A definitive PASS/FAIL/CONDITIONAL/NOT_APPLICABLE the supplied artifact reached is
            # real, standalone evidence and must not be discarded just because a refresh path
            # exists -- accept_child_result already authority-gates NOT_APPLICABLE the same way it
            # gates PASS, so reaching this status here is exactly as trustworthy as reaching PASS.
            return {"status": accepted.status, "mode": "REUSE"}
        # Falls through: the supplied artifact is stale (incomplete coverage), or all it yielded
        # was UNKNOWN (identity mismatch, untrusted producer, or weak-authority claim) -- per
        # collect-evidence.md, that is exactly the case that should attempt a fresh invocation
        # when one is available, not a dead end reported as UNKNOWN with an unused refresh path
        # sitting right there.

    if invoke_spy is None or not _mandatory_inputs_available(artifact_type, mandatory_inputs):
        return {"status": "UNKNOWN", "mode": None}

    result = invoke_spy(artifact_type, candidate=candidate)
    if result is None:
        return {"status": "UNKNOWN", "mode": None}
    accepted = accept_child_result(result, candidate=candidate)
    return {"status": accepted.status, "mode": "REFRESH"}


# ---------------------------------------------------------------------------
# Trusted CI / code-review coverage / build provenance (Task 5)
# ---------------------------------------------------------------------------


def validate_ci(candidate: Mapping[str, Any], ci: Optional[Mapping[str, Any]]) -> MutableMapping[str, Any]:
    if ci is None:
        return {"status": "UNKNOWN", "reason": "missing_ci_evidence"}
    candidate = as_mapping(candidate)
    ci = as_mapping(ci)
    source_revision = _effective_source_revision(candidate)
    head_revision = ci.get("head_revision")
    if not source_revision or not head_revision or head_revision != source_revision:
        return {"status": "UNKNOWN", "reason": "scope_mismatch"}
    if not is_host_or_runtime_acquisition(ci.get("acquisition")):
        return {"status": "UNKNOWN", "reason": "untrusted_acquisition"}
    all_required_green = ci.get("all_required_green")
    if all_required_green is not True and all_required_green is not False:
        # A non-boolean value (a string like "false", a missing field) is not a trustworthy
        # affirmative signal either way -- never coerce it via truthiness into FAIL or PASS.
        return {"status": "UNKNOWN", "reason": "all_required_green_not_boolean"}
    if not all_required_green:
        return {"status": "FAIL", "reason": "required_checks_not_green"}
    return {"status": "PASS"}


def validate_code_review_coverage(
    coverage: Optional[Mapping[str, Any]], candidate: Mapping[str, Any]
) -> MutableMapping[str, Any]:
    if coverage is None:
        return {"status": "UNKNOWN", "reason": "missing_coverage_evidence"}
    coverage = as_mapping(coverage)
    candidate = as_mapping(candidate)
    # Mandatory scope fence, matching validate_ci/validate_build_provenance's own contract: code
    # review evidence computed for a different revision (e.g. the pre-force-push head) must never
    # validate as this candidate's own coverage. Making `candidate` optional here (as an earlier
    # fix did) left the fence opt-in and unused by every real caller -- exactly the same class of
    # gap round 7 found and fixed for target_of.
    candidate_rev = _effective_source_revision(candidate)
    if not candidate_rev or coverage.get("candidate_source_revision") != candidate_rev:
        return {"status": "UNKNOWN", "reason": "scope_mismatch"}
    if (
        coverage.get("status") == "COMPLETE"
        and not coverage.get("uncovered_change_refs")
        and is_host_or_runtime_acquisition(coverage.get("acquisition"))
    ):
        return {"status": "PASS"}
    return {"status": "UNKNOWN", "reason": "incomplete_coverage"}


def validate_build_provenance(
    candidate: Mapping[str, Any], provenance: Optional[Mapping[str, Any]]
) -> MutableMapping[str, Any]:
    candidate = as_mapping(candidate)
    provenance = as_mapping(provenance) if provenance is not None else None
    source_revision = _effective_source_revision(candidate)
    # Mirrors _has_minimum_candidate_identity's exact MR-shape test: nested-first via target_of
    # (a candidate declaring its MR identity only under assessment_target must not be treated as
    # having no separate deployable-digest concept, landing on the wrong UNKNOWN-forever branch
    # below), then ALL THREE fields with a truthy (not merely non-None) project/head_sha --
    # `is not None` alone would accept junk like head_sha="" or merge_request_iid=0 with no
    # project at all as "MR-shaped."
    mr_probe = target_of(candidate) or candidate
    is_mr_shaped = any(
        bool(probe.get("project") and probe.get("merge_request_iid") is not None and probe.get("head_sha"))
        for probe in (mr_probe, candidate)
    )
    nested_head_revision_or_digest = mr_probe.get("head_revision_or_digest")
    if nested_head_revision_or_digest is not None:
        # Nested-first, same as is_mr_shaped just above: a flat top-level field must never be
        # preferred over (or allowed to shadow) a real nested declaration of the same identity
        # concept -- a forged/stale flat value colliding with source_revision must not mask a
        # genuinely different nested digest and the real build evidence behind it. `is not None`,
        # not mere key presence: a nested carrier that explicitly declares this field `None` (a
        # producer that always emits the full field set) has not actually declared a value and
        # must fall back to the flat sibling, matching _effective_head_digest's own precedence.
        head_revision_or_digest = nested_head_revision_or_digest
    elif "head_revision_or_digest" in candidate:
        head_revision_or_digest = candidate.get("head_revision_or_digest")
    elif provenance is not None and "deployable_digest" in provenance:
        # A supplied provenance record naming a deployable digest is itself proof a build
        # step exists for this candidate, even though the candidate never carried a
        # head_revision_or_digest field of its own -- that evidence must be consulted before
        # falling back to "no separate build step," or a real build (success or failure) for an
        # MR-shaped candidate is discarded as NOT_APPLICABLE without ever being read. Presence,
        # not truthiness: a falsy-but-present value (""/0, a malformed record) must still route
        # here rather than silently falling through to the MR-shape default -- it correctly lands
        # on the missing-identity UNKNOWN below instead of a wrongful NOT_APPLICABLE.
        head_revision_or_digest = provenance.get("deployable_digest")
    elif is_mr_shaped:
        # An MR-shaped candidate with no provenance record and no head_revision_or_digest field
        # has no separate deployable-digest concept at all -- defaulting to source_revision itself
        # correctly lands on the NOT_APPLICABLE branch below instead of UNKNOWN forever. This must
        # NOT apply to a release-candidate-shaped input that simply failed to resolve a digest
        # (e.g. a host.build.provenance.read lookup that came back empty): that case has a real,
        # distinct deployable identity concept and must stay UNKNOWN, never silently NOT_APPLICABLE.
        head_revision_or_digest = source_revision
    else:
        head_revision_or_digest = None
    if not source_revision or not head_revision_or_digest:
        return {"status": "UNKNOWN", "reason": "missing_candidate_identity"}
    if head_revision_or_digest == source_revision:
        return {"status": "NOT_APPLICABLE", "build_provenance_ref": "NOT_APPLICABLE"}
    if provenance is None:
        return {"status": "UNKNOWN", "reason": "missing_build_provenance"}
    if provenance.get("source_revision") != source_revision:
        return {"status": "UNKNOWN", "reason": "source_mismatch"}
    if provenance.get("deployable_digest") != head_revision_or_digest:
        return {"status": "UNKNOWN", "reason": "digest_mismatch"}
    if not is_host_or_runtime_acquisition(provenance.get("acquisition")):
        # Matching validate_ci/validate_code_review_coverage's own acquisition gate: a
        # caller-asserted (or acquisition-less) build-success claim is not itself proof a build
        # actually ran and succeeded -- gates both PASS and FAIL uniformly, the same as CI's own
        # acquisition check, since an untrusted record can't be relied on for either outcome.
        return {"status": "UNKNOWN", "reason": "untrusted_acquisition"}
    build_status = provenance.get("build_status")
    if build_status == "SUCCESS":
        evidence_ref = provenance.get("evidence_ref")
        if not evidence_ref:
            return {"status": "UNKNOWN", "reason": "missing_build_provenance_ref"}
        return {"status": "PASS", "build_provenance_ref": evidence_ref}
    if build_status == "FAILED":
        return {"status": "FAIL", "reason": "build_failed"}
    return {"status": "UNKNOWN", "reason": "build_status_unknown"}


def evaluate_build_provenance(fixture: Mapping[str, Any]) -> GateResult:
    fixture = as_mapping(fixture)
    policy_requires_attestation = fixture.get("policy_requires_attestation")
    if not isinstance(policy_requires_attestation, bool):
        # A non-boolean value (None, an absent key) means the attestation policy itself was never
        # resolved -- reading it with bare truthiness would treat "couldn't determine" the same as
        # a confirmed "not required," silently discarding a known attestation result (including a
        # FAILED one) below.
        return GateResult("UNKNOWN", "attestation_policy_unresolved")
    if policy_requires_attestation:
        attestation = fixture.get("attestation")
        if attestation is None:
            return GateResult("UNKNOWN", "attestation_missing")
        if attestation == "FAILED":
            return GateResult("FAIL", "attestation_failed")
        if attestation != "SUCCESS":
            return GateResult("UNKNOWN", "attestation_unknown")

    candidate = fixture.get("candidate")
    if not candidate:
        # No candidate (None, or an unresolved {}) to bind the (possibly-satisfied) attestation
        # policy to a source/digest pair -- absence of evidence is never PASS, even when the
        # attestation control itself succeeded.
        return GateResult("UNKNOWN", "missing_candidate")
    base = validate_build_provenance(candidate, fixture.get("provenance"))
    return GateResult(base["status"], base.get("reason", ""))


# ---------------------------------------------------------------------------
# Authoritative SCM policy gate (Task 5.5)
# ---------------------------------------------------------------------------


_SCM_POLICY_KEYS = ("required_approvals", "codeowners_required", "blocking_threads_must_resolve")


def evaluate_scm_policy(
    policy: Mapping[str, Any], observed: Mapping[str, Any], candidate: Optional[Mapping[str, Any]] = None
) -> GateResult:
    policy = as_mapping(policy)
    observed = as_mapping(observed)
    candidate = as_mapping(candidate) if candidate is not None else None
    if not policy or not observed:
        return GateResult("UNKNOWN", "missing_scm_policy_evidence")
    if any(key not in policy for key in _SCM_POLICY_KEYS):
        # A partially-resolved policy document (a rule that could not be read) must not silently
        # default to "not required" -- an unread rule is an evidence gap, never a permissive
        # default.
        return GateResult("UNKNOWN", "scm_policy_incompletely_read")

    if candidate is not None:
        # Approvals/CODEOWNERS/blocking-thread state is the same kind of live, force-push-
        # sensitive SCM fact as code-review coverage -- validate_code_review_coverage's own
        # mandatory scope fence exists specifically because "code review evidence computed for a
        # different revision (e.g. the pre-force-push head) must never validate as this
        # candidate's own coverage." `observed` is an evidence record (flat-only, like
        # dependency_ci/advisory_evidence), not an identity-declaring object. Inert when no
        # candidate is supplied, matching this module's established convention.
        candidate_rev = _effective_source_revision(candidate)
        observed_rev = observed.get("source_revision")
        if not candidate_rev or observed_rev != candidate_rev:
            return GateResult("UNKNOWN", "scope_mismatch")

    bypass_refs = observed.get("policy_bypass_refs") or []
    if bypass_refs:
        approved = observed.get("bypass_approved")
        bypass_authority = observed.get("bypass_approval_authority", "caller")
        evidence_ref = observed.get("bypass_approval_ref")
        # A caller-supplied "yes it was approved" claim needs an authoritative approver and an
        # evidence ref behind it -- bare truthiness must never suppress a real policy-bypass
        # finding.
        if approved is not True or not _is_strong_authority(bypass_authority) or not evidence_ref:
            return GateResult("FAIL", "unapproved_policy_bypass")

    required_approvals = policy["required_approvals"]
    if isinstance(required_approvals, bool) or not isinstance(required_approvals, int):
        # A non-numeric (or boolean) required_approvals value is a malformed/unread policy field,
        # not a legitimate "0 required" -- comparing it below would also raise TypeError.
        return GateResult("UNKNOWN", "scm_policy_incompletely_read")
    if required_approvals:
        approvals = observed.get("approvals")
        # Evidence never gathered (key absent, or present as None) is an evidence gap, not an
        # affirmative "zero approvals" finding -- it must land on UNKNOWN, never FAIL.
        if approvals is None:
            return GateResult("UNKNOWN", "approvals_unknown")
        if not isinstance(approvals, int) or isinstance(approvals, bool):
            return GateResult("UNKNOWN", "approvals_not_numeric")
        if approvals < required_approvals:
            return GateResult("FAIL", "insufficient_approvals")

    codeowners_required = policy["codeowners_required"]
    if not isinstance(codeowners_required, bool):
        # A non-boolean value (None, a string) is an unresolved policy rule, not a legitimate
        # "not required" -- the presence-only fence above doesn't distinguish a resolved False
        # from a rule the policy-read tool simply couldn't determine.
        return GateResult("UNKNOWN", "scm_policy_incompletely_read")
    if codeowners_required:
        satisfied = observed.get("codeowners_satisfied")
        if satisfied == "unknown" or satisfied is None:
            return GateResult("UNKNOWN", "codeowners_unknown")
        if not isinstance(satisfied, bool):
            # A non-boolean, non-"unknown" value (a string like "false"/"pending", a list of
            # missing owners) is a malformed signal, not a confirmed PASS -- bare truthiness would
            # treat "false" as satisfied.
            return GateResult("UNKNOWN", "codeowners_status_not_boolean")
        if not satisfied:
            return GateResult("FAIL", "codeowners_not_satisfied")

    blocking_threads_must_resolve = policy["blocking_threads_must_resolve"]
    if not isinstance(blocking_threads_must_resolve, bool):
        # Same rule as codeowners_required just above: an unresolved policy rule must not default
        # to "not required" via bare truthiness on a None/malformed value.
        return GateResult("UNKNOWN", "scm_policy_incompletely_read")
    if blocking_threads_must_resolve:
        blocking_open = observed.get("blocking_threads_open")
        if blocking_open is None:
            return GateResult("UNKNOWN", "blocking_threads_unknown")
        if not isinstance(blocking_open, int) or isinstance(blocking_open, bool):
            return GateResult("UNKNOWN", "blocking_threads_not_numeric")
        if blocking_open > 0:
            return GateResult("FAIL", "blocking_threads_open")

    return GateResult("PASS")


# ---------------------------------------------------------------------------
# Environment-sensitive evidence matching (Task 7.25) + evidence scope (Task 7)
# ---------------------------------------------------------------------------


def _effective_environment(obj: Any) -> Any:
    """Best-effort environment read: a nested assessment_target/target's own `environment` first,
    falling back to the object's own flat top-level field when the nested target doesn't declare
    one.

    Mirrors `_effective_source_revision`'s nested-first precedence, applied uniformly to every
    side of every environment-sensitivity check in this module (the four operational gates,
    capacity, `_environment_conflict`'s own candidate resolution, `match_dimension_evidence`'s
    candidate/artifact resolution, `accept_child_result`'s child resolution). Unlike a revision
    field -- where a nested target's silence is uniformly safe, since every validator fails closed
    on an absent revision either way -- letting a nested target's silence shadow a real flat
    `environment` would be fail-OPEN: it would silently disable the relevant check instead of
    falling back to the object's own known environment. A single shared helper exists specifically
    so this fallback is applied identically everywhere, rather than re-derived (and inevitably
    missed somewhere) at each call site.
    """
    obj = as_mapping(obj)
    target = target_of(obj) or {}
    env = target.get("environment")
    if env is None:
        env = obj.get("environment")
    return env


def _environment_conflict(fixture: Any, candidate: Optional[Mapping[str, Any]]) -> bool:
    """True when `candidate` declares an environment that conflicts with `fixture`'s own.

    Applied to every `ENV_SENSITIVE_DIMENSIONS` member per operational-gates.md and
    child-input-map.md (the four operational gates, capacity, observability, deployment_risk):
    evidence collected for one environment (a staging on-call rotation) must not silently stand in
    for another (production). Only fires when BOTH sides resolve an environment and they actually
    disagree -- a caller not supplying `candidate`, or a fixture with no declared environment
    (nested or flat), leaves this check inert rather than retroactively blocking every existing
    caller that never had environment context to give.

    Takes the whole `fixture`/`candidate` object (not a pre-extracted flat field) specifically so
    both sides resolve nested-first via `_effective_environment` -- passing an already-flat-read
    value here reopens the exact laundering hole this function exists to close.
    """
    if candidate is None or fixture is None:
        return False
    fixture_env = _effective_environment(fixture)
    candidate_env = _effective_environment(candidate)
    if fixture_env is None or candidate_env is None:
        return False
    return not safe_same_environment(candidate_env, fixture_env)


def match_dimension_evidence(
    dimension_name: str,
    *,
    candidate: Mapping[str, Any],
    artifact: Mapping[str, Any],
) -> GateResult:
    candidate = as_mapping(candidate)
    artifact = as_mapping(artifact)
    # Same nested-first resolution target_of gives identity: the canonical assessment_target
    # carrier declares `environment` alongside source_revision/head_revision_or_digest, and a
    # flat top-level field must never be read in preference to (or in ignorance of) it -- identity
    # already resolves nested via accept_child_result below, so environment must agree.
    candidate_env = _effective_environment(candidate)
    artifact_env = _effective_environment(artifact)
    artifact_target = target_of(artifact) or artifact
    # Same nested-first-with-flat-fallback resolution as the environment fields themselves --
    # a nested target's silence on `environment_specific` must not shadow a real flat declaration.
    env_specific = bool(artifact_target.get("environment_specific"))
    if not env_specific and "environment_specific" not in artifact_target:
        env_specific = bool(artifact.get("environment_specific"))
    env_sensitive = dimension_name in ENV_SENSITIVE_DIMENSIONS or env_specific

    if candidate_env is not None and artifact_env is not None:
        # Two explicitly-declared environments that conflict are never silently accepted, even
        # for a dimension that is otherwise environment-agnostic -- a directly conflicting field
        # is evidence of the wrong target, not something applicability rules get to ignore.
        if not safe_same_environment(candidate_env, artifact_env):
            return GateResult("UNKNOWN", "environment_mismatch")
    elif env_sensitive:
        return GateResult("UNKNOWN", "environment_mismatch")

    accepted = accept_child_result(artifact, candidate=candidate, dimension=dimension_name)
    if not accepted.trusted_for_gate:
        return GateResult("UNKNOWN", accepted.reason)
    return GateResult(accepted.status, accepted.reason)


# ---------------------------------------------------------------------------
# Operational evidence-authority policy (Task 7.5)
# ---------------------------------------------------------------------------


def evaluate_ownership(
    owner: Mapping[str, Any], criticality: str = "unknown", candidate: Optional[Mapping[str, Any]] = None
) -> GateResult:
    owner = as_mapping(owner)
    if _environment_conflict(owner, candidate):
        return GateResult("UNKNOWN", "environment_mismatch")
    authority = owner.get("owner_authority", "caller")
    if owner.get("unowned"):
        # An authoritative negative finding is FAIL at any tier; a caller-only "nobody owns this"
        # assertion is not itself proof and must not sink the verdict to NOT_READY on its own.
        if _is_strong_authority(authority):
            return GateResult("FAIL", "authoritative_unowned")
        return GateResult("UNKNOWN", "unowned_claim_not_authoritative")
    if owner.get("conflicting"):
        return GateResult("UNKNOWN", "conflicting_ownership")

    has_owner_evidence = bool(owner.get("owner")) and bool(owner.get("escalation_route"))
    if not has_owner_evidence:
        return GateResult("UNKNOWN", "incomplete_ownership_evidence")

    if _is_strong_authority(authority):
        return GateResult("PASS")
    if _tier_requires_strict_unknown(criticality):
        return GateResult("UNKNOWN", "caller_only_owner")
    return GateResult("CONDITIONAL", "caller_only_owner")


_ROLLBACK_REQUIRED_FIELDS = frozenset({"trigger", "action", "actor", "decision_window_minutes"})


def evaluate_rollback_abort(
    plan: Mapping[str, Any], criticality: str = "unknown", candidate: Optional[Mapping[str, Any]] = None
) -> GateResult:
    plan = as_mapping(plan)
    if _environment_conflict(plan, candidate):
        return GateResult("UNKNOWN", "environment_mismatch")
    authority = plan.get("authority", "caller")
    if plan.get("unsafe_irreversible_no_recovery"):
        # Checked before the completeness gate: an authoritative proven-unsafe finding is FAIL
        # at any tier, including when the rollback plan itself is incomplete -- that is exactly
        # the scenario this rule exists to catch, not a reason to soften it to UNKNOWN.
        if _is_strong_authority(authority):
            return GateResult("FAIL", "unsafe_irreversible")
        return GateResult("UNKNOWN", "unsafe_claim_not_authoritative")

    # Symmetric with the sibling post-deploy/ownership/recovery gates: a "complete" flag alone is
    # not evidence of a concrete plan -- operational-gates.md defines this dimension as "a
    # concrete, verified way to stop or reverse this change," so the plan's own content fields
    # must actually be present. `decision_window_minutes` may legitimately be 0 (an immediate
    # decision window), so presence is checked via `is None`, not truthiness.
    if not plan or any(plan.get(field) is None for field in _ROLLBACK_REQUIRED_FIELDS):
        return GateResult("UNKNOWN", "incomplete_plan")
    if not _is_true(plan.get("complete")):
        return GateResult("UNKNOWN", "incomplete_plan")

    if _is_strong_authority(authority):
        return GateResult("PASS")
    if _tier_requires_strict_unknown(criticality):
        return GateResult("UNKNOWN", "caller_only_rollback")
    return GateResult("CONDITIONAL", "caller_only_rollback")


_POST_DEPLOY_REQUIRED_FIELDS = frozenset(
    {"signals", "observation_window", "success_criteria", "abort_criteria", "decision_owner"}
)


def evaluate_post_deploy_plan(
    plan: Mapping[str, Any], criticality: str = "unknown", candidate: Optional[Mapping[str, Any]] = None
) -> GateResult:
    plan = as_mapping(plan)
    if _environment_conflict(plan, candidate):
        return GateResult("UNKNOWN", "environment_mismatch")
    if not plan or not all(plan.get(field) for field in _POST_DEPLOY_REQUIRED_FIELDS):
        return GateResult("UNKNOWN", "incomplete_plan")
    if not _is_true(plan.get("complete")):
        return GateResult("UNKNOWN", "incomplete_plan")

    authority = plan.get("signal_authority", "caller")
    if _is_strong_authority(authority):
        return GateResult("PASS")
    if _tier_requires_strict_unknown(criticality):
        return GateResult("UNKNOWN", "caller_only_signals")
    return GateResult("CONDITIONAL", "caller_only_signals")


def evaluate_recovery(
    fixture: Mapping[str, Any], criticality: str = "unknown", candidate: Optional[Mapping[str, Any]] = None
) -> GateResult:
    fixture = as_mapping(fixture)
    if _environment_conflict(fixture, candidate):
        return GateResult("UNKNOWN", "environment_mismatch")
    mechanism_authority = fixture.get("mechanism_authority", "caller")

    if fixture.get("destructive_no_recovery"):
        # Checked first: an authoritative destructive-without-recovery finding is FAIL at any
        # tier, and must not be masked by a "reversible"/NOT_APPLICABLE shortcut below.
        if _is_strong_authority(mechanism_authority):
            return GateResult("FAIL", "destructive_no_recovery")
        return GateResult("UNKNOWN", "destructive_claim_not_authoritative")

    if fixture.get("stateful") is False and _is_true(fixture.get("reversible")):
        # `stateful` must be an explicit, confirmed `False` -- an omitted field (evidence that
        # never actually determined statefulness) must not be silently treated as a confirmed
        # non-stateful finding just because `not None` is truthy. A caller-only "this is
        # reversible" assertion with no authoritative statefulness evidence must not delete the
        # recovery dimension from the required set entirely either way.
        if _is_strong_authority(mechanism_authority):
            return GateResult("NOT_APPLICABLE")
        # Falls through to the normal completeness/tier ladder below rather than short-circuiting
        # straight to UNKNOWN -- claiming reversibility must never make the verdict WORSE than not
        # claiming it at all (the non-reversible path below can still reach tier2/tier3
        # CONDITIONAL for the same caller-only evidence).

    # Completeness is checked before authority/tier, matching the sibling ownership/rollback/
    # post-deploy gates -- otherwise upgrading incomplete evidence from a caller assertion to an
    # authoritative source would perversely make the verdict WORSE (CONDITIONAL -> UNKNOWN),
    # since the authority branch below would then also see the same missing fields.
    if not fixture.get("policy_freshness"):
        return GateResult("UNKNOWN", "missing_recovery_policy_freshness")
    if not fixture.get("rpo_rto_policy"):
        return GateResult("UNKNOWN", "missing_rpo_rto")
    if not fixture.get("last_exercise"):
        return GateResult("UNKNOWN", "missing_exercise_evidence")

    if not _is_strong_authority(mechanism_authority):
        # Tier-sensitive per operational-gates.md: caller-only evidence is UNKNOWN at
        # tier0/tier1/unknown, but at most CONDITIONAL (never PASS) at tier2/tier3 -- the same
        # rule already applied to the sibling ownership/rollback/post-deploy gates above.
        if _tier_requires_strict_unknown(criticality):
            return GateResult("UNKNOWN", "caller_only_mechanism")
        return GateResult("CONDITIONAL", "caller_only_mechanism")
    return GateResult("PASS")


# ---------------------------------------------------------------------------
# Capacity + dependency gates (Task 7.4)
# ---------------------------------------------------------------------------


def evaluate_capacity_gate(
    report: Mapping[str, Any], criticality: str = "unknown", candidate: Optional[Mapping[str, Any]] = None
) -> GateResult:
    report = as_mapping(report)
    if _environment_conflict(report, candidate):
        return GateResult("UNKNOWN", "environment_mismatch")
    if report.get("producer_trusted", True) is not True:
        return GateResult("UNKNOWN", "untrusted_producer")
    status = report.get("status", "UNKNOWN")
    if status not in DIMENSION_STATUSES:
        status = "UNKNOWN"
    if status in ("FAIL", "UNKNOWN"):
        # An already-negative or already-unresolved child status is never relabeled by the
        # capacity-specific authority check below -- that check exists to keep an under-evidenced
        # PASS/CONDITIONAL from being trusted, not to re-score a status the child already reported.
        return GateResult(status)

    evidence_authorities = as_mapping(report.get("evidence_authorities"))
    # `_minimum_authority_met` checks EVERY entry in the map, not just "demand"/"baseline" -- a
    # third weakly-authoritative entry (e.g. "headroom_model": {"caller"}) must not be ignored
    # just because the two named keys happen to be strong.
    has_required_keys = "demand" in evidence_authorities and "baseline" in evidence_authorities
    if status == "NOT_APPLICABLE":
        # Claiming inapplicability deletes this dimension from the required set entirely -- the
        # MORE favorable outcome than PASS -- so it must never require LESS authority than PASS
        # would, matching accept_child_result's own rule. It must NOT additionally require the
        # PASS-specific "demand"/"baseline" evidence keys, though: those keys are, by definition,
        # absent when the dimension genuinely doesn't apply (a config-only change has no demand
        # forecast at all) -- requiring them here would make a fully-authoritative NOT_APPLICABLE
        # claim impossible to ever satisfy.
        if _minimum_authority_met(evidence_authorities):
            return GateResult("NOT_APPLICABLE")
        return GateResult("UNKNOWN", "not_applicable_claim_not_authoritative")
    if has_required_keys and _minimum_authority_met(evidence_authorities):
        return GateResult(status)
    if _tier_requires_strict_unknown(criticality):
        return GateResult("UNKNOWN", "caller_only_basis")
    return GateResult("CONDITIONAL", "caller_only_basis")


def evaluate_dependency_gate(
    report: Mapping[str, Any],
    advisory_evidence: Optional[Mapping[str, Any]] = None,
    dependency_ci: Optional[Mapping[str, Any]] = None,
    candidate: Optional[Mapping[str, Any]] = None,
) -> GateResult:
    report = as_mapping(report)
    advisory_evidence = as_mapping(advisory_evidence) if advisory_evidence is not None else None
    dependency_ci = as_mapping(dependency_ci) if dependency_ci is not None else None
    candidate = as_mapping(candidate) if candidate is not None else None
    if report.get("producer_trusted", True) is not True:
        return GateResult("UNKNOWN", "untrusted_producer")
    status = report.get("status", "UNKNOWN")
    if status not in DIMENSION_STATUSES:
        status = "UNKNOWN"
    if status in ("FAIL", "UNKNOWN"):
        # An already-negative or already-unresolved child status is never relabeled by a
        # substitute CVE-currency check below -- a substitute cures missing/weak CVE evidence, it
        # does not re-score a status the child already reported.
        return GateResult(status)

    evidence_authorities = as_mapping(report.get("evidence_authorities"))
    # Same all-entries rule as the capacity gate above: a weak entry elsewhere in the map (e.g.
    # "version_delta": {"caller"}) must not be ignored just because "cve" itself is strong.
    has_cve_key = "cve" in evidence_authorities
    if status == "NOT_APPLICABLE":
        # Same rule as the capacity gate: claiming inapplicability must never require LESS
        # authority than PASS would, and must NOT additionally require the PASS-specific "cve" key
        # -- that key is, by definition, absent when no dependency change makes CVE evidence
        # relevant at all. A substitute (advisory_evidence/dependency_ci) proves CVE currency
        # specifically -- it doesn't bear on whether "no vulnerability check applies" is itself a
        # trustworthy claim, so it is not consulted here.
        if _minimum_authority_met(evidence_authorities):
            return GateResult("NOT_APPLICABLE")
        return GateResult("UNKNOWN", "not_applicable_claim_not_authoritative")
    if has_cve_key and _minimum_authority_met(evidence_authorities):
        return GateResult(status)

    if not evidence_authorities:
        # The child declared NO evidence trail at all -- not even a weak "cve" entry. A substitute
        # can cure missing/weak CVE evidence specifically, but it cannot vouch for a report that
        # discloses nothing whatsoever about its own basis (accept_child_result treats an empty/
        # absent evidence_authorities map the same way, via _minimum_authority_met's own
        # empty-map-is-False rule).
        return GateResult("UNKNOWN", "no_current_vulnerability_evidence")

    # A substitute (advisory_evidence / dependency_ci) only cures the "cve" entry specifically --
    # every OTHER entry already in the report's own evidence_authorities (e.g. version_delta,
    # breaking_changes) still has to independently meet the same authority bar, per the no-
    # laundering rule the primary branch above applies to the whole map.
    other_authorities = {k: v for k, v in evidence_authorities.items() if k != "cve"}
    other_entries_ok = _minimum_authority_met(other_authorities) if other_authorities else True

    if other_entries_ok and advisory_evidence is not None:
        # capability_catalog.yaml describes host.dependency.advisories.read as delivering
        # "current vulnerability/advisory evidence for changed dependencies AT THE EXACT SOURCE
        # REVISION" -- the same scope concept dependency_ci carries. This scope fence was
        # previously entirely absent (unlike dependency_ci's, which was merely miscategorized as
        # nested-first): a cached/forged/reused advisory blob for an unrelated revision was
        # accepted with no binding to the candidate under review at all. Flat-only, matching every
        # other evidence-record parameter in this module (dependency_ci, ci, coverage, provenance)
        # -- advisory_evidence doesn't declare its own canonical identity carrier either.
        candidate_rev = _effective_source_revision(candidate) if candidate is not None else None
        advisory_rev = advisory_evidence.get("source_revision")
        scope_ok = candidate is None or (bool(candidate_rev) and advisory_rev == candidate_rev)
        if (
            scope_ok
            and advisory_evidence.get("status") == "CURRENT"
            and _is_strong_authority(advisory_evidence.get("acquisition"))
        ):
            # A substitute for the child's own CVE evidence needs the same authority bar the
            # child's own evidence would have needed -- a caller-forged "status: CURRENT" claim
            # with no acquisition behind it must not launder a weakly-authoritative report into a
            # PASS.
            return GateResult(status)

    if other_entries_ok and dependency_ci is not None:
        # The candidate side resolves nested-first (it's an identity-declaring object, same as
        # everywhere else in this module) -- and, requires BOTH sides to actually name an
        # identity: two None revisions must never vacuously match. `dependency_ci` itself, though,
        # is a live-CI-style EVIDENCE RECORD, the same kind of object as validate_ci's `ci`,
        # validate_code_review_coverage's `coverage`, and validate_build_provenance's
        # `provenance` -- all three of those are read flat-only, deliberately, because an
        # evidence record isn't a child artifact declaring its own canonical identity carrier.
        # Routing it through the nested-first `_effective_source_revision` (as an earlier version
        # of this check did) let a dependency-CI run genuinely scoped to the WRONG commit carry a
        # nested assessment_target/target agreeing with the candidate and launder its (out-of-
        # scope) success into this candidate's own CVE-currency evidence -- a real, fail-open gap.
        candidate_rev = _effective_source_revision(candidate) if candidate is not None else None
        dependency_ci_rev = dependency_ci.get("source_revision")
        scope_ok = candidate is None or (bool(candidate_rev) and dependency_ci_rev == candidate_rev)
        if (
            scope_ok
            and _is_true(dependency_ci.get("required"))
            and _is_true(dependency_ci.get("scope_covers_changed_manifest"))
            and dependency_ci.get("conclusion") == "success"
            and _is_strong_authority(dependency_ci.get("acquisition"))
        ):
            return GateResult(status)

    return GateResult("UNKNOWN", "no_current_vulnerability_evidence")


# ---------------------------------------------------------------------------
# Child gate policy + bounded dispatch (Task 8)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ChildGatePolicy:
    posting_decision: str = "HOLD"
    remote_writes_allowed: bool = False
    merge_allowed: bool = False


def child_gate_policy(child_name: str) -> ChildGatePolicy:
    del child_name  # policy is uniform across every child: no child may post, merge, or deploy.
    return ChildGatePolicy()


# Caller-settable fields that must never reach a child unmodified: gate-policy.md requires this
# skill to never forward a caller-controllable "authorized to merge/deploy/rollback" or posting
# field to any child, regardless of what the caller supplied in `inputs`.
_CALLER_CONTROLLED_AUTHORITY_KEYS = frozenset(
    {
        "posting_policy",
        "posting_decision",
        "posting_mode",
        "auto_post_authorized",
        "authorized_to_merge",
        "authorized_to_deploy",
        "authorized_to_rollback",
        "merge_allowed",
        "remote_writes_allowed",
    }
)


def _sanitized_child_inputs(child_name: str, inputs: Mapping[str, Any]) -> Mapping[str, Any]:
    """Strip caller-controllable authority/posting fields and enforce this skill's fixed policy.

    A fabricated `posting_policy: allow` (or any other authority-shaped field) in the caller's
    inputs must be dropped, not forwarded -- every child always dispatches with this skill's own
    fixed, uniform gate policy, never one the caller can override.
    """
    sanitized = dict(inputs)
    for key in _CALLER_CONTROLLED_AUTHORITY_KEYS:
        sanitized.pop(key, None)
    sanitized["posting_policy"] = "forbidden"
    if child_name == "pr-review":
        # child-input-map.md: pr-review is always dispatched retrospective/read-only.
        sanitized["review_mode"] = "retrospective"
        sanitized["audit_type"] = "retrospective"
    return sanitized


@dataclasses.dataclass(frozen=True)
class ReadinessAuthority:
    deploy: bool = False
    merge: bool = False
    rollback: bool = False


def readiness_authority() -> ReadinessAuthority:
    return ReadinessAuthority()


@dataclasses.dataclass(frozen=True)
class DispatchResult:
    dispatched: bool
    dimension_status: str
    result: Optional[Mapping[str, Any]] = None


def dispatch_child(
    child_name: str,
    inputs: Optional[Mapping[str, Any]] = None,
    invoke: Optional[Callable[[str, Mapping[str, Any]], Optional[Mapping[str, Any]]]] = None,
    expected_target: Optional[Mapping[str, Any]] = None,
    candidate: Optional[Mapping[str, Any]] = None,
) -> DispatchResult:
    inputs = as_mapping(inputs) if inputs is not None else {}
    if not _child_mandatory_inputs_satisfied(child_name, inputs):
        return DispatchResult(dispatched=False, dimension_status="UNKNOWN")

    if invoke is None:
        return DispatchResult(dispatched=False, dimension_status="UNKNOWN")

    result = invoke(child_name, _sanitized_child_inputs(child_name, inputs))
    if result is None:
        return DispatchResult(dispatched=False, dimension_status="UNKNOWN")

    # A child's result must be bound to the identity this dispatch was actually for -- otherwise
    # a PASS reported for a different commit/environment is recorded as this candidate's PASS.
    # Precedence: an explicit expected_target always wins; otherwise fall back to the candidate
    # under assessment (this binds EVERY child, not just pr-review -- the old code only had an
    # automatic fallback for pr-review's own mandatory expected_head_sha input, leaving every
    # other child unbound unless the caller remembered to pass expected_target manually);
    # pr-review's expected_head_sha remains a last-resort fallback for a caller that supplies
    # neither expected_target nor candidate.
    target_ref = expected_target
    if target_ref is None:
        target_ref = candidate
    if target_ref is None and inputs.get("expected_head_sha"):
        target_ref = {"source_revision": inputs["expected_head_sha"]}

    accepted = accept_child_result(result, expected_target=target_ref)
    return DispatchResult(dispatched=True, dimension_status=accepted.status, result=result)


# ---------------------------------------------------------------------------
# Top-level orchestration entry + final freshness fence (Task 9.5)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ProductionReadinessResult:
    verdict: str
    skill_result: SkillResult
    dimension_statuses: Sequence[Dimension] = ()

    @property
    def skill_result_status(self) -> str:
        return self.skill_result.status


def _has_minimum_candidate_identity(candidate: Mapping[str, Any]) -> bool:
    candidate = as_mapping(candidate)
    if not candidate:
        return False
    # Nested-first, matching target_of/_effective_source_revision: a candidate whose identity
    # lives entirely in its own declared assessment_target must not be BLOCKED at the entry gate
    # just because it carries no flat top-level identity field. Falls back to the flat candidate
    # itself when the nested target doesn't declare either identity shape -- a nested carrier that
    # legitimately declares OTHER fields (e.g. `environment`) without declaring identity must not
    # shadow a real flat identity and get treated as "no identity at all."
    target = target_of(candidate) or candidate
    for probe in (target, candidate):
        if probe.get("source_revision") or probe.get("head_revision_or_digest"):
            return True
        if probe.get("project") and probe.get("merge_request_iid") is not None and probe.get("head_sha"):
            return True
    return False


def production_readiness(
    candidate: Mapping[str, Any],
    *,
    scm_change_read: Optional[Callable[..., Any]] = None,
    dimensions: Optional[Sequence[Dimension]] = None,
    waivers: Optional[Sequence[Mapping[str, Any]]] = None,
) -> ProductionReadinessResult:
    if not _has_minimum_candidate_identity(candidate):
        return ProductionReadinessResult(
            verdict="UNKNOWN",
            skill_result=SkillResult(status="BLOCKED", evidence_status="UNKNOWN"),
        )

    # Any ONE of these fields, not all three, marks the candidate as MR-shaped: a caller must not
    # be able to skip the live scm_change_read fence just by omitting one of them while still
    # supplying enough identity (e.g. head_sha + source_revision) to pass the check above. Nested-
    # first via target_of, matching _has_minimum_candidate_identity immediately above -- an MR
    # expressed through the canonical assessment_target carrier must not skip this fence just
    # because these fields aren't also duplicated at the candidate's own flat top level.
    mr_probe = target_of(candidate) or candidate
    is_remote_mr = any(
        bool(probe.get("project") or probe.get("merge_request_iid") is not None or probe.get("head_sha"))
        for probe in (mr_probe, candidate)
    )
    if is_remote_mr and scm_change_read is None:
        return ProductionReadinessResult(
            verdict="UNKNOWN",
            skill_result=SkillResult(status="PARTIAL", evidence_status="UNKNOWN"),
        )

    if dimensions is None:
        # No evidence collection was ever attempted for this candidate -- never default that
        # silently to READY.
        return ProductionReadinessResult(
            verdict="UNKNOWN",
            skill_result=SkillResult(status="PARTIAL", evidence_status="UNKNOWN"),
        )

    if not dimensions or not any(_is_required(d) for d in dimensions):
        # An empty list, or a set with no REQUIRED dimension left after applicability/status
        # filtering (matching _is_required's own rule: NOT_APPLICABLE by either applicability OR
        # status is excluded), carries zero required evidence -- aggregate_verdict's worst-first
        # ladder is vacuously READY over an empty required set, but report-format.md is explicit
        # that NOT_APPLICABLE dimensions never count as evidence toward PASS, and this skill's own
        # definition of done says a check that never ran must never be folded into READY. A caller
        # cannot get a clean verdict just by supplying no dimensions, or by marking all of them
        # inapplicable via either field.
        return ProductionReadinessResult(
            verdict="UNKNOWN",
            skill_result=SkillResult(status="PARTIAL", evidence_status="UNKNOWN"),
            dimension_statuses=tuple(dimensions),
        )

    readiness = aggregate_readiness(dimensions, waivers=waivers)
    return ProductionReadinessResult(
        verdict=readiness.verdict,
        skill_result=SkillResult(status=readiness.skill_result_status, evidence_status=readiness.evidence_status),
        dimension_statuses=readiness.dimensions,
    )


def check_final_freshness(
    initial: Mapping[str, Any],
    final: Mapping[str, Any],
) -> GateResult:
    """Compare identity/CI/policy snapshots taken before dispatch vs immediately before report emission."""

    initial = as_mapping(initial)
    final = as_mapping(final)
    if not initial or not final:
        return GateResult("UNKNOWN", "missing_freshness_snapshot")

    if initial.get("head") is None or final.get("head") is None:
        return GateResult("UNKNOWN", "missing_head_identity")
    if initial.get("head") != final.get("head"):
        return GateResult("UNKNOWN", "head_changed_during_review")
    if initial.get("release_resolution") != final.get("release_resolution"):
        return GateResult("UNKNOWN", "release_ref_resolved_inconsistently")

    # Strict `is True`/`is False`/`is None` identity checks throughout: a non-bool value (e.g.
    # the string "false", or an integer 0) must never be treated as a confirmed state -- it must
    # not fall through the ladder below to the terminal PASS just because it is neither `is
    # False` nor `is None`.
    initial_ci_green = initial.get("ci_green")
    final_ci_green = final.get("ci_green")
    if not isinstance(final_ci_green, bool) and final_ci_green is not None:
        return GateResult("UNKNOWN", "ci_signal_not_boolean")
    if not isinstance(initial_ci_green, bool) and initial_ci_green is not None:
        return GateResult("UNKNOWN", "ci_signal_not_boolean")
    if final_ci_green is False:
        if initial_ci_green is not False:
            # Covers both "confirmed green, now red" and "never confirmed, now
            # observed red" -- the latter must not silently fall through to PASS
            # just because there was no earlier snapshot to regress against.
            reason = "ci_regressed" if initial_ci_green is True else "ci_red_at_final_check"
            return GateResult("FAIL", reason)
    elif initial_ci_green is not None and final_ci_green is None:
        # The re-read could not reconfirm CI state -- that's an evidence gap, not proof it
        # stayed green, and must not silently fall through to the PASS at the end.
        return GateResult("UNKNOWN", "ci_could_not_be_reconfirmed")

    initial_approvals_ok = initial.get("approvals_ok")
    final_approvals_ok = final.get("approvals_ok")
    if not isinstance(final_approvals_ok, bool) and final_approvals_ok is not None:
        return GateResult("UNKNOWN", "approvals_signal_not_boolean")
    if not isinstance(initial_approvals_ok, bool) and initial_approvals_ok is not None:
        return GateResult("UNKNOWN", "approvals_signal_not_boolean")
    if final_approvals_ok is False:
        if initial_approvals_ok is not False:
            reason = (
                "approval_dismissed"
                if initial_approvals_ok is True
                else "approvals_rejected_at_final_check"
            )
            return GateResult("FAIL", reason)
    elif initial_approvals_ok is not None and final_approvals_ok is None:
        return GateResult("UNKNOWN", "approvals_could_not_be_reconfirmed")

    return GateResult("PASS")
