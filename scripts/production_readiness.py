"""Pure evidence-aggregation and gating logic for the production-readiness-review orchestrator.

This module holds only deterministic, side-effect-free logic: verdict aggregation,
evidence-authority policy, prerequisite reuse/refresh decisions, and the individual
readiness gates (CI, build provenance, SCM policy, operational evidence, capacity,
dependency). Registry wiring, dispatcher integration, and child invocation live
outside this module; `dispatch_child` here is a policy-level adapter only.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable, Mapping, MutableMapping, Optional, Sequence

# ---------------------------------------------------------------------------
# Canonical vocab
# ---------------------------------------------------------------------------

DIMENSION_STATUSES = ("PASS", "CONDITIONAL", "FAIL", "UNKNOWN", "NOT_APPLICABLE")
VERDICTS = ("READY", "CONDITIONAL", "NOT_READY", "UNKNOWN")

STRONG_AUTHORITIES = frozenset({"repository", "authoritative_host", "trusted_runtime"})
WEAK_AUTHORITIES = frozenset({"caller", "model_knowledge"})

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

CHILD_MANDATORY_INPUTS: Mapping[str, Sequence[str]] = {
    "security-review": ("review_target",),
    "observability-review": ("service_name", "observability_material"),
    "resilience-review": (
        "current_failure_behavior",
        "proposed_failure_behavior",
        "affected_dependency_paths",
    ),
    "api-design-review": ("api_spec",),
    "performance-review": ("reviewed_content",),
    "capacity-planner": ("demand_data", "forecast_horizon"),
    "dependency-upgrade-review": ("dependency_name", "current_version", "target_version"),
}

DATABASE_REVIEW_ONE_OF = ("schema", "migration_script", "queries")


@dataclasses.dataclass(frozen=True)
class GateResult:
    """Generic gate outcome: status plus an optional machine-readable reason."""

    status: str
    reason: str = ""


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
            now = datetime.datetime.now(datetime.timezone.utc)
            if expiry < now:
                return False
        except ValueError:
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


def _minimum_authority_met(evidence_authorities: Optional[Mapping[str, Any]]) -> bool:
    if not evidence_authorities:
        return False
    for authorities in evidence_authorities.values():
        authorities_set = set(authorities) if not isinstance(authorities, str) else {authorities}
        if authorities_set & STRONG_AUTHORITIES:
            return True
    return False


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
    if expected_rev and child_rev and expected_rev != child_rev:
        return True
    if expected_head and child_head and expected_head != child_head:
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
    if not _minimum_authority_met(child.get("evidence_authorities")):
        status = "UNKNOWN"
    return AcceptedChildResult(status=status, trusted_for_gate=True, reason="")


@dataclasses.dataclass(frozen=True)
class AssessmentContextTrust:
    context: Mapping[str, Any]
    acquisition: str

    def effective_authority(self, field: str) -> str:
        if self.acquisition != "trusted_runtime":
            return "caller"
        provenance = (self.context.get("input_provenance") or {}).get(field) or {}
        return provenance.get("authority", "caller")


def classify_assessment_context_trust(
    ctx: Mapping[str, Any], acquisition: str = "caller_supplied"
) -> AssessmentContextTrust:
    return AssessmentContextTrust(context=ctx, acquisition=acquisition)


# ---------------------------------------------------------------------------
# Trusted prerequisite resolution (slice 4)
# ---------------------------------------------------------------------------


def _mandatory_inputs_available(artifact_type: str, mandatory_inputs: Optional[Mapping[str, Any]]) -> bool:
    if mandatory_inputs is None:
        return False
    child_name = {
        "change_impact_report": "change-impact-analyzer",
        "deployment_risk_report": "deployment-risk-review",
    }.get(artifact_type)
    if child_name is None:
        return bool(mandatory_inputs)
    required = CHILD_MANDATORY_INPUTS.get(child_name, ())
    return all(key in mandatory_inputs for key in required) if required else bool(mandatory_inputs)


def resolve_prerequisite(
    artifact_type: str,
    *,
    supplied: Optional[Mapping[str, Any]] = None,
    candidate: Optional[Mapping[str, Any]] = None,
    invoke_spy: Optional[Callable[..., Any]] = None,
    mandatory_inputs: Optional[Mapping[str, Any]] = None,
) -> MutableMapping[str, Any]:
    if supplied is not None:
        accepted = accept_child_result(supplied, candidate=candidate)
        coverage_status = supplied.get("coverage_status")
        if coverage_status is not None and coverage_status != "COMPLETE":
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
    if ci.get("head_revision") != candidate.get("source_revision"):
        return {"status": "UNKNOWN", "reason": "scope_mismatch"}
    if ci.get("acquisition") not in {"authoritative_host", "trusted_runtime"}:
        return {"status": "UNKNOWN", "reason": "untrusted_acquisition"}
    if not ci.get("all_required_green"):
        return {"status": "FAIL", "reason": "required_checks_not_green"}
    return {"status": "PASS"}


def validate_code_review_coverage(coverage: Optional[Mapping[str, Any]]) -> MutableMapping[str, Any]:
    if coverage is None:
        return {"status": "UNKNOWN", "reason": "missing_coverage_evidence"}
    if coverage.get("status") == "COMPLETE" and not coverage.get("uncovered_change_refs"):
        return {"status": "PASS"}
    return {"status": "UNKNOWN", "reason": "incomplete_coverage"}


def validate_build_provenance(
    candidate: Mapping[str, Any], provenance: Optional[Mapping[str, Any]]
) -> MutableMapping[str, Any]:
    if candidate.get("head_revision_or_digest") == candidate.get("source_revision"):
        return {"status": "NOT_APPLICABLE", "build_provenance_ref": "NOT_APPLICABLE"}
    if provenance is None:
        return {"status": "UNKNOWN", "reason": "missing_build_provenance"}
    if provenance.get("source_revision") != candidate.get("source_revision"):
        return {"status": "UNKNOWN", "reason": "source_mismatch"}
    if provenance.get("deployable_digest") != candidate.get("head_revision_or_digest"):
        return {"status": "UNKNOWN", "reason": "digest_mismatch"}
    build_status = provenance.get("build_status")
    if build_status == "SUCCESS":
        return {"status": "PASS", "build_provenance_ref": provenance.get("evidence_ref")}
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
    if candidate is not None:
        base = validate_build_provenance(candidate, fixture.get("provenance"))
        return GateResult(base["status"], base.get("reason", ""))
    return GateResult("PASS")


# ---------------------------------------------------------------------------
# Authoritative SCM policy gate (Task 5.5)
# ---------------------------------------------------------------------------


def evaluate_scm_policy(policy: Mapping[str, Any], observed: Mapping[str, Any]) -> GateResult:
    bypass_refs = observed.get("policy_bypass_refs") or []
    if bypass_refs and not observed.get("bypass_approved"):
        return GateResult("FAIL", "unapproved_policy_bypass")

    required_approvals = policy.get("required_approvals", 0)
    if required_approvals and observed.get("approvals", 0) < required_approvals:
        return GateResult("FAIL", "insufficient_approvals")

    if policy.get("codeowners_required"):
        satisfied = observed.get("codeowners_satisfied")
        if satisfied == "unknown":
            return GateResult("UNKNOWN", "codeowners_unknown")
        if not satisfied:
            return GateResult("FAIL", "codeowners_not_satisfied")

    if policy.get("blocking_threads_must_resolve") and observed.get("blocking_threads_open", 0) > 0:
        return GateResult("FAIL", "blocking_threads_open")

    return GateResult("PASS")


# ---------------------------------------------------------------------------
# Environment-sensitive evidence matching (Task 7.25) + evidence scope (Task 7)
# ---------------------------------------------------------------------------


def match_dimension_evidence(
    dimension_name: str,
    *,
    candidate: Mapping[str, Any],
    artifact: Mapping[str, Any],
) -> GateResult:
    candidate_env = candidate.get("environment")
    artifact_env = artifact.get("environment")
    env_specific = bool(artifact.get("environment_specific"))

    if dimension_name in ENV_SENSITIVE_DIMENSIONS or env_specific:
        if candidate_env is None or artifact_env is None or candidate_env != artifact_env:
            return GateResult("UNKNOWN", "environment_mismatch")

    accepted = accept_child_result(artifact, candidate=candidate, dimension=dimension_name)
    if not accepted.trusted_for_gate:
        return GateResult("UNKNOWN", accepted.reason)
    return GateResult(accepted.status, accepted.reason)


# ---------------------------------------------------------------------------
# Operational evidence-authority policy (Task 7.5)
# ---------------------------------------------------------------------------


def evaluate_ownership(owner: Mapping[str, Any], criticality: str = "unknown") -> GateResult:
    if owner.get("conflicting"):
        return GateResult("UNKNOWN", "conflicting_ownership")
    if owner.get("unowned"):
        return GateResult("FAIL", "authoritative_unowned")

    authority = owner.get("owner_authority", "caller")
    if authority in STRONG_AUTHORITIES:
        return GateResult("PASS")
    if criticality in ("tier0", "tier1", "unknown"):
        return GateResult("UNKNOWN", "caller_only_owner")
    return GateResult("CONDITIONAL", "caller_only_owner")


def evaluate_rollback_abort(plan: Mapping[str, Any], criticality: str = "unknown") -> GateResult:
    if not plan.get("complete"):
        return GateResult("UNKNOWN", "incomplete_plan")
    if plan.get("unsafe_irreversible_no_recovery"):
        return GateResult("FAIL", "unsafe_irreversible")

    authority = plan.get("authority", "caller")
    if authority in STRONG_AUTHORITIES:
        return GateResult("PASS")
    if criticality in ("tier0", "tier1", "unknown"):
        return GateResult("UNKNOWN", "caller_only_rollback")
    return GateResult("CONDITIONAL", "caller_only_rollback")


_POST_DEPLOY_REQUIRED_FIELDS = frozenset(
    {"signals", "observation_window", "success_criteria", "abort_criteria", "decision_owner"}
)


def evaluate_post_deploy_plan(plan: Mapping[str, Any], criticality: str = "unknown") -> GateResult:
    if not plan or not _POST_DEPLOY_REQUIRED_FIELDS.issubset(plan.keys()):
        return GateResult("UNKNOWN", "incomplete_plan")
    if not plan.get("complete", True):
        return GateResult("UNKNOWN", "incomplete_plan")

    authority = plan.get("signal_authority", "caller")
    if authority in STRONG_AUTHORITIES:
        return GateResult("PASS")
    if criticality in ("tier0", "tier1", "unknown"):
        return GateResult("UNKNOWN", "caller_only_signals")
    return GateResult("CONDITIONAL", "caller_only_signals")


def evaluate_recovery(fixture: Mapping[str, Any]) -> GateResult:
    if not fixture.get("stateful") and fixture.get("reversible"):
        return GateResult("NOT_APPLICABLE")
    if fixture.get("destructive_no_recovery"):
        return GateResult("FAIL", "destructive_no_recovery")
    if fixture.get("policy_freshness") is None:
        return GateResult("UNKNOWN", "missing_recovery_policy_freshness")

    mechanism_authority = fixture.get("mechanism_authority", "caller")
    if mechanism_authority not in STRONG_AUTHORITIES:
        return GateResult("UNKNOWN", "caller_only_mechanism")
    if not fixture.get("rpo_rto_policy"):
        return GateResult("UNKNOWN", "missing_rpo_rto")
    if not fixture.get("last_exercise"):
        return GateResult("UNKNOWN", "missing_exercise_evidence")
    return GateResult("PASS")


# ---------------------------------------------------------------------------
# Capacity + dependency gates (Task 7.4)
# ---------------------------------------------------------------------------


def evaluate_capacity_gate(report: Mapping[str, Any], criticality: str = "unknown") -> GateResult:
    evidence_authorities = report.get("evidence_authorities") or {}
    demand_auth = set(evidence_authorities.get("demand", ()))
    baseline_auth = set(evidence_authorities.get("baseline", ()))
    both_strong = bool(demand_auth & STRONG_AUTHORITIES) and bool(baseline_auth & STRONG_AUTHORITIES)

    if both_strong:
        return GateResult(report.get("status", "PASS"))
    if criticality in ("tier0", "tier1", "unknown"):
        return GateResult("UNKNOWN", "caller_only_basis")
    return GateResult("CONDITIONAL", "caller_only_basis")


def evaluate_dependency_gate(
    report: Mapping[str, Any],
    advisory_evidence: Optional[Mapping[str, Any]] = None,
    dependency_ci: Optional[Mapping[str, Any]] = None,
) -> GateResult:
    evidence_authorities = report.get("evidence_authorities") or {}
    cve_auth = set(evidence_authorities.get("cve", STRONG_AUTHORITIES))
    if cve_auth & STRONG_AUTHORITIES:
        return GateResult(report.get("status", "PASS"))

    if advisory_evidence is not None and advisory_evidence.get("status") == "CURRENT":
        return GateResult(report.get("status", "PASS"))

    if (
        dependency_ci is not None
        and dependency_ci.get("required")
        and dependency_ci.get("scope_covers_changed_manifest")
        and dependency_ci.get("conclusion") == "success"
    ):
        return GateResult(report.get("status", "PASS"))

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


def _child_mandatory_inputs_satisfied(child_name: str, inputs: Mapping[str, Any]) -> bool:
    if child_name == "database-review":
        return any(key in inputs for key in DATABASE_REVIEW_ONE_OF)
    required = CHILD_MANDATORY_INPUTS.get(child_name, ())
    return all(key in inputs for key in required)


def dispatch_child(
    child_name: str,
    inputs: Optional[Mapping[str, Any]] = None,
    invoke: Optional[Callable[[str, Mapping[str, Any]], Optional[Mapping[str, Any]]]] = None,
) -> DispatchResult:
    inputs = inputs or {}
    if not _child_mandatory_inputs_satisfied(child_name, inputs):
        return DispatchResult(dispatched=False, dimension_status="UNKNOWN")

    if invoke is None:
        return DispatchResult(dispatched=False, dimension_status="UNKNOWN")

    result = invoke(child_name, inputs)
    if result is None:
        return DispatchResult(dispatched=False, dimension_status="UNKNOWN")

    accepted = accept_child_result(result)
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

    is_remote_mr = "project" in candidate and "merge_request_iid" in candidate
    if is_remote_mr and scm_change_read is None:
        return ProductionReadinessResult(
            verdict="UNKNOWN",
            skill_result=SkillResult(status="PARTIAL", evidence_status="UNKNOWN"),
        )

    dims = dimensions if dimensions is not None else []
    readiness = aggregate_readiness(dims, waivers=waivers)
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

    if initial.get("head") != final.get("head"):
        return GateResult("UNKNOWN", "head_changed_during_review")
    if initial.get("release_resolution") != final.get("release_resolution"):
        return GateResult("UNKNOWN", "release_ref_resolved_inconsistently")

    initial_ci_green = initial.get("ci_green")
    final_ci_green = final.get("ci_green")
    if initial_ci_green and final_ci_green is False:
        return GateResult("FAIL", "ci_regressed")

    initial_approvals_ok = initial.get("approvals_ok")
    final_approvals_ok = final.get("approvals_ok")
    if initial_approvals_ok and final_approvals_ok is False:
        return GateResult("FAIL", "approval_dismissed")

    return GateResult("PASS")
