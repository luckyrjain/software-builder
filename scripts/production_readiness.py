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

from scripts.registry.assessment_target import same_environment

# ---------------------------------------------------------------------------
# Canonical vocab
# ---------------------------------------------------------------------------

DIMENSION_STATUSES = ("PASS", "CONDITIONAL", "FAIL", "UNKNOWN", "NOT_APPLICABLE")

STRONG_AUTHORITIES = frozenset({"repository", "authoritative_host", "trusted_runtime"})
WEAK_AUTHORITIES = frozenset({"caller", "model_knowledge"})
_ALL_AUTHORITIES = STRONG_AUTHORITIES | WEAK_AUTHORITIES

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
# contract), documented alongside the other three in reference/child-input-map.md.
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


def _as_authority_map(value: Any) -> Mapping[str, Any]:
    """Coerce a claimed evidence_authorities value to a mapping, or {} for any other shape.

    A malformed shape (a list, a string, ...) from an untrusted or buggy child must degrade to
    "no authoritative evidence", never raise -- a crash here would take down the whole aggregation
    instead of failing closed on just the affected dimension.
    """
    return value if isinstance(value, Mapping) else {}


def _minimum_authority_met(evidence_authorities: Optional[Mapping[str, Any]]) -> bool:
    """True only when EVERY evidence entry backing a conclusion is *purely* strongly authoritative.

    A single weakly-authoritative entry must not be laundered into a strong conclusion merely
    because some unrelated entry in the same map happens to be strong (round-3 fix). Nor may an
    entry that mixes a strong and a weak authority together (`{"caller", "repository"}`) pass on
    the strength of its strong half alone -- per evidence-authority-policy.md rule 4, mixed
    evidence downgrades the whole entry, so each entry's authority set must be a *subset* of
    `STRONG_AUTHORITIES`, not merely intersect it.
    """
    evidence_authorities = _as_authority_map(evidence_authorities)
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
    if criticality not in _KNOWN_CRITICALITY_TIERS:
        return True
    return criticality in ("tier0", "tier1", "unknown")


def _normalize_child_status(report: Mapping[str, Any]) -> str:
    """Validate + trust-check a child result's own status, matching accept_child_result's rules.

    Used by gates (capacity, dependency) that apply their own dimension-specific authority check
    ahead of this, rather than routing through accept_child_result's generic identity/authority
    pipeline -- but the child's raw status string still needs the same two guards: never pass
    through an unrecognized value (a typo, or a child-specific vocabulary like "BLOCKED"), and
    never trust an explicitly untrusted producer.
    """
    if not report.get("producer_trusted", True):
        return "UNKNOWN"
    status = report.get("status", "UNKNOWN")
    return status if status in DIMENSION_STATUSES else "UNKNOWN"


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
        except (ValueError, TypeError):
            return False
    return True


def aggregate_report(
    dims: Sequence[Dimension],
    waivers: Optional[Sequence[Mapping]] = None,
) -> MutableMapping[str, Any]:
    verdict = aggregate_verdict(dims, waivers=waivers)
    valid_waivers = [w for w in (waivers or []) if _is_valid_waiver(w)]
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
    any_unknown_evidence = any(d.evidence_status == "UNKNOWN" or d.status == "UNKNOWN" for d in required)
    skill_result_status = "PARTIAL" if any_unknown_evidence else "SUCCESS"
    evidence_status = "UNKNOWN" if any_unknown_evidence else "OBSERVED"
    return ReadinessResult(
        verdict=verdict,
        skill_result_status=skill_result_status,
        evidence_status=evidence_status,
        dimensions=tuple(required_dimensions),
    )


# ---------------------------------------------------------------------------
# Evidence-authority policy (Task 7.2) + assessment_context trust (slice 4)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class AcceptedChildResult:
    status: str
    trusted_for_gate: bool
    reason: str = ""


def _target_of(obj: Any) -> Optional[Mapping[str, Any]]:
    if obj is None:
        return None
    if isinstance(obj, Mapping) and ("source_revision" in obj or "head_revision_or_digest" in obj):
        return obj
    if isinstance(obj, Mapping):
        return obj.get("target")
    return None


def _identity_mismatch(child: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    child_target = _target_of(child) or {}
    child_rev = child.get("source_revision") or child_target.get("source_revision")
    child_head = child_target.get("head_revision_or_digest") or child_rev
    expected_rev = expected.get("source_revision")
    expected_head = expected.get("head_revision_or_digest") or expected_rev
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
    target_ref = expected_target if expected_target is not None else candidate
    if target_ref is not None and _identity_mismatch(child, target_ref):
        return AcceptedChildResult(status="UNKNOWN", trusted_for_gate=False, reason="target_mismatch")

    if not child.get("producer_trusted", True):
        return AcceptedChildResult(status="UNKNOWN", trusted_for_gate=False, reason="untrusted_producer")

    status = child.get("status", "UNKNOWN")
    if status not in DIMENSION_STATUSES:
        # An unrecognized status (a typo, a child-specific vocabulary like "BLOCKED") must never
        # silently fall through an aggregator's status-string comparisons as an implicit PASS.
        status = "UNKNOWN"
    elif status in ("PASS", "CONDITIONAL") and not _minimum_authority_met(child.get("evidence_authorities")):
        # The no-laundering rule applies to PASS and CONDITIONAL alike: per evidence-authority-
        # policy.md rule 3, evidence that is only caller/model_knowledge-authoritative is UNKNOWN
        # -- not CONDITIONAL either, since CONDITIONAL implies some authoritative signal exists.
        # A FAIL a child already reported is not softened just because it lacked authority.
        status = "UNKNOWN"
    return AcceptedChildResult(status=status, trusted_for_gate=True, reason="")


@dataclasses.dataclass(frozen=True)
class AssessmentContextTrust:
    context: Mapping[str, Any]
    acquisition: str

    def effective_authority(self, field: str) -> str:
        if self.acquisition not in STRONG_AUTHORITIES:
            return "caller"
        provenance = (self.context.get("input_provenance") or {}).get(field) or {}
        authority = provenance.get("authority", "caller")
        return authority if authority in _ALL_AUTHORITIES else "caller"


def classify_assessment_context_trust(
    ctx: Mapping[str, Any], acquisition: str = "caller_supplied"
) -> AssessmentContextTrust:
    return AssessmentContextTrust(context=ctx, acquisition=acquisition)


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

    if supplied is not None:
        accepted = accept_child_result(supplied, candidate=candidate)
        # coverage_status is a change_impact_report-specific field (composition_contracts.yaml);
        # other prerequisite artifacts (e.g. deployment_risk_report) have no such field and must
        # not be required to carry it.
        if artifact_type == "change_impact_report" and supplied.get("coverage_status") != "COMPLETE":
            return {"status": "UNKNOWN", "mode": None}
        return {"status": accepted.status, "mode": "REUSE"}

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
    source_revision = candidate.get("source_revision")
    head_revision = ci.get("head_revision")
    if not source_revision or not head_revision or head_revision != source_revision:
        return {"status": "UNKNOWN", "reason": "scope_mismatch"}
    if ci.get("acquisition") not in {"authoritative_host", "trusted_runtime"}:
        return {"status": "UNKNOWN", "reason": "untrusted_acquisition"}
    all_required_green = ci.get("all_required_green")
    if all_required_green is not True and all_required_green is not False:
        # A non-boolean value (a string like "false", a missing field) is not a trustworthy
        # affirmative signal either way -- never coerce it via truthiness into FAIL or PASS.
        return {"status": "UNKNOWN", "reason": "all_required_green_not_boolean"}
    if not all_required_green:
        return {"status": "FAIL", "reason": "required_checks_not_green"}
    return {"status": "PASS"}


def validate_code_review_coverage(coverage: Optional[Mapping[str, Any]]) -> MutableMapping[str, Any]:
    if coverage is None:
        return {"status": "UNKNOWN", "reason": "missing_coverage_evidence"}
    if (
        coverage.get("status") == "COMPLETE"
        and not coverage.get("uncovered_change_refs")
        and coverage.get("acquisition") in {"authoritative_host", "trusted_runtime"}
    ):
        return {"status": "PASS"}
    return {"status": "UNKNOWN", "reason": "incomplete_coverage"}


def validate_build_provenance(
    candidate: Mapping[str, Any], provenance: Optional[Mapping[str, Any]]
) -> MutableMapping[str, Any]:
    source_revision = candidate.get("source_revision")
    head_revision_or_digest = candidate.get("head_revision_or_digest")
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
    if fixture.get("policy_requires_attestation"):
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


def evaluate_scm_policy(policy: Mapping[str, Any], observed: Mapping[str, Any]) -> GateResult:
    if not policy or not observed:
        return GateResult("UNKNOWN", "missing_scm_policy_evidence")
    if any(key not in policy for key in _SCM_POLICY_KEYS):
        # A partially-resolved policy document (a rule that could not be read) must not silently
        # default to "not required" -- an unread rule is an evidence gap, never a permissive
        # default.
        return GateResult("UNKNOWN", "scm_policy_incompletely_read")

    bypass_refs = observed.get("policy_bypass_refs") or []
    if bypass_refs:
        approved = observed.get("bypass_approved")
        bypass_authority = observed.get("bypass_approval_authority", "caller")
        evidence_ref = observed.get("bypass_approval_ref")
        # A caller-supplied "yes it was approved" claim needs an authoritative approver and an
        # evidence ref behind it -- bare truthiness must never suppress a real policy-bypass
        # finding.
        if not approved or bypass_authority not in STRONG_AUTHORITIES or not evidence_ref:
            return GateResult("FAIL", "unapproved_policy_bypass")

    required_approvals = policy["required_approvals"]
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

    if policy["codeowners_required"]:
        satisfied = observed.get("codeowners_satisfied")
        if satisfied == "unknown" or satisfied is None:
            return GateResult("UNKNOWN", "codeowners_unknown")
        if not satisfied:
            return GateResult("FAIL", "codeowners_not_satisfied")

    if policy["blocking_threads_must_resolve"]:
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


def _safe_same_environment(candidate_env: Any, artifact_env: Any) -> bool:
    try:
        return same_environment(candidate_env, artifact_env)
    except (TypeError, AttributeError):
        return False


def match_dimension_evidence(
    dimension_name: str,
    *,
    candidate: Mapping[str, Any],
    artifact: Mapping[str, Any],
) -> GateResult:
    candidate_env = candidate.get("environment")
    artifact_env = artifact.get("environment")
    env_specific = bool(artifact.get("environment_specific"))
    env_sensitive = dimension_name in ENV_SENSITIVE_DIMENSIONS or env_specific

    if candidate_env is not None and artifact_env is not None:
        # Two explicitly-declared environments that conflict are never silently accepted, even
        # for a dimension that is otherwise environment-agnostic -- a directly conflicting field
        # is evidence of the wrong target, not something applicability rules get to ignore.
        if not _safe_same_environment(candidate_env, artifact_env):
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


def evaluate_ownership(owner: Mapping[str, Any], criticality: str = "unknown") -> GateResult:
    authority = owner.get("owner_authority", "caller")
    if owner.get("unowned"):
        # An authoritative negative finding is FAIL at any tier; a caller-only "nobody owns this"
        # assertion is not itself proof and must not sink the verdict to NOT_READY on its own.
        if authority in STRONG_AUTHORITIES:
            return GateResult("FAIL", "authoritative_unowned")
        return GateResult("UNKNOWN", "unowned_claim_not_authoritative")
    if owner.get("conflicting"):
        return GateResult("UNKNOWN", "conflicting_ownership")

    has_owner_evidence = bool(owner.get("owner")) and bool(owner.get("escalation_route"))
    if not has_owner_evidence:
        return GateResult("UNKNOWN", "incomplete_ownership_evidence")

    if authority in STRONG_AUTHORITIES:
        return GateResult("PASS")
    if _tier_requires_strict_unknown(criticality):
        return GateResult("UNKNOWN", "caller_only_owner")
    return GateResult("CONDITIONAL", "caller_only_owner")


def evaluate_rollback_abort(plan: Mapping[str, Any], criticality: str = "unknown") -> GateResult:
    authority = plan.get("authority", "caller")
    if plan.get("unsafe_irreversible_no_recovery"):
        # Checked before the completeness gate: an authoritative proven-unsafe finding is FAIL
        # at any tier, including when the rollback plan itself is incomplete -- that is exactly
        # the scenario this rule exists to catch, not a reason to soften it to UNKNOWN.
        if authority in STRONG_AUTHORITIES:
            return GateResult("FAIL", "unsafe_irreversible")
        return GateResult("UNKNOWN", "unsafe_claim_not_authoritative")

    if not plan.get("complete"):
        return GateResult("UNKNOWN", "incomplete_plan")

    if authority in STRONG_AUTHORITIES:
        return GateResult("PASS")
    if _tier_requires_strict_unknown(criticality):
        return GateResult("UNKNOWN", "caller_only_rollback")
    return GateResult("CONDITIONAL", "caller_only_rollback")


_POST_DEPLOY_REQUIRED_FIELDS = frozenset(
    {"signals", "observation_window", "success_criteria", "abort_criteria", "decision_owner"}
)


def evaluate_post_deploy_plan(plan: Mapping[str, Any], criticality: str = "unknown") -> GateResult:
    if not plan or not all(plan.get(field) for field in _POST_DEPLOY_REQUIRED_FIELDS):
        return GateResult("UNKNOWN", "incomplete_plan")
    if not plan.get("complete"):
        return GateResult("UNKNOWN", "incomplete_plan")

    authority = plan.get("signal_authority", "caller")
    if authority in STRONG_AUTHORITIES:
        return GateResult("PASS")
    if _tier_requires_strict_unknown(criticality):
        return GateResult("UNKNOWN", "caller_only_signals")
    return GateResult("CONDITIONAL", "caller_only_signals")


def evaluate_recovery(fixture: Mapping[str, Any], criticality: str = "unknown") -> GateResult:
    mechanism_authority = fixture.get("mechanism_authority", "caller")

    if fixture.get("destructive_no_recovery"):
        # Checked first: an authoritative destructive-without-recovery finding is FAIL at any
        # tier, and must not be masked by a "reversible"/NOT_APPLICABLE shortcut below.
        if mechanism_authority in STRONG_AUTHORITIES:
            return GateResult("FAIL", "destructive_no_recovery")
        return GateResult("UNKNOWN", "destructive_claim_not_authoritative")

    if not fixture.get("stateful") and fixture.get("reversible"):
        # A caller-only "this is reversible" assertion with no authoritative statefulness
        # evidence must not delete the recovery dimension from the required set entirely.
        if mechanism_authority in STRONG_AUTHORITIES:
            return GateResult("NOT_APPLICABLE")
        return GateResult("UNKNOWN", "reversible_claim_not_authoritative")

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

    if mechanism_authority not in STRONG_AUTHORITIES:
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


def evaluate_capacity_gate(report: Mapping[str, Any], criticality: str = "unknown") -> GateResult:
    evidence_authorities = _as_authority_map(report.get("evidence_authorities"))
    # `_minimum_authority_met` checks EVERY entry in the map, not just "demand"/"baseline" -- a
    # third weakly-authoritative entry (e.g. "headroom_model": {"caller"}) must not be ignored
    # just because the two named keys happen to be strong.
    has_required_keys = "demand" in evidence_authorities and "baseline" in evidence_authorities
    if has_required_keys and _minimum_authority_met(evidence_authorities):
        return GateResult(_normalize_child_status(report))
    if _tier_requires_strict_unknown(criticality):
        return GateResult("UNKNOWN", "caller_only_basis")
    return GateResult("CONDITIONAL", "caller_only_basis")


def evaluate_dependency_gate(
    report: Mapping[str, Any],
    advisory_evidence: Optional[Mapping[str, Any]] = None,
    dependency_ci: Optional[Mapping[str, Any]] = None,
    candidate: Optional[Mapping[str, Any]] = None,
) -> GateResult:
    evidence_authorities = _as_authority_map(report.get("evidence_authorities"))
    # Same all-entries rule as the capacity gate above: a weak entry elsewhere in the map (e.g.
    # "version_delta": {"caller"}) must not be ignored just because "cve" itself is strong.
    has_cve_key = "cve" in evidence_authorities
    if has_cve_key and _minimum_authority_met(evidence_authorities):
        return GateResult(_normalize_child_status(report))

    if (
        advisory_evidence is not None
        and advisory_evidence.get("status") == "CURRENT"
        and advisory_evidence.get("acquisition") in STRONG_AUTHORITIES
    ):
        # A substitute for the child's own CVE evidence needs the same authority bar the child's
        # own evidence would have needed -- a caller-forged "status: CURRENT" claim with no
        # acquisition behind it must not launder a weakly-authoritative report into a PASS.
        return GateResult(_normalize_child_status(report))

    if (
        dependency_ci is not None
        and dependency_ci.get("required")
        and dependency_ci.get("scope_covers_changed_manifest")
        and dependency_ci.get("conclusion") == "success"
        and dependency_ci.get("acquisition") in STRONG_AUTHORITIES
        and (candidate is None or dependency_ci.get("source_revision") == candidate.get("source_revision"))
    ):
        # Same authority bar, plus a scope check when a candidate is supplied: dependency CI
        # evidence collected for a different commit must not stand in for this one's.
        return GateResult(_normalize_child_status(report))

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
) -> DispatchResult:
    inputs = inputs or {}
    if not _child_mandatory_inputs_satisfied(child_name, inputs):
        return DispatchResult(dispatched=False, dimension_status="UNKNOWN")

    if invoke is None:
        return DispatchResult(dispatched=False, dimension_status="UNKNOWN")

    result = invoke(child_name, _sanitized_child_inputs(child_name, inputs))
    if result is None:
        return DispatchResult(dispatched=False, dimension_status="UNKNOWN")

    # A child's result must be bound to the identity this dispatch was actually for -- otherwise
    # a PASS reported for a different commit/environment is recorded as this candidate's PASS.
    # pr-review's own mandatory `expected_head_sha` input is exactly that declared identity, so
    # it binds automatically even when the caller doesn't separately pass expected_target.
    target_ref = expected_target
    if target_ref is None and inputs.get("expected_head_sha"):
        target_ref = {"source_revision": inputs["expected_head_sha"]}

    accepted = accept_child_result(result, expected_target=target_ref)
    return DispatchResult(dispatched=True, dimension_status=accepted.status, result=result)


# ---------------------------------------------------------------------------
# Top-level orchestration entry + final freshness fence (Task 9.5)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SkillResult:
    status: str
    evidence_status: str = "UNKNOWN"


@dataclasses.dataclass(frozen=True)
class ProductionReadinessResult:
    verdict: str
    skill_result: SkillResult
    dimension_statuses: Sequence[Dimension] = ()

    @property
    def skill_result_status(self) -> str:
        return self.skill_result.status


def _has_minimum_candidate_identity(candidate: Mapping[str, Any]) -> bool:
    if not candidate:
        return False
    if candidate.get("source_revision") or candidate.get("head_revision_or_digest"):
        return True
    if candidate.get("project") and candidate.get("merge_request_iid") is not None and candidate.get("head_sha"):
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
    # supplying enough identity (e.g. head_sha + source_revision) to pass the check above.
    is_remote_mr = bool(
        candidate.get("project") or candidate.get("merge_request_iid") is not None or candidate.get("head_sha")
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

    if not dimensions or all(d.status == "NOT_APPLICABLE" for d in dimensions):
        # An empty list, or a set where every dimension resolved NOT_APPLICABLE, carries zero
        # required evidence -- aggregate_verdict's worst-first ladder is vacuously READY over an
        # empty required set, but report-format.md is explicit that NOT_APPLICABLE dimensions
        # never count as evidence toward PASS, and this skill's own definition of done says a
        # check that never ran must never be folded into READY. A caller cannot get a clean
        # verdict just by supplying no dimensions, or by marking all of them inapplicable.
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
