"""Shared test fixtures/harnesses for scripts/tests/test_production_readiness_contract.py.

Plain builder functions, matching this repo's existing convention (see
scripts/tests/test_change_impact_analyzer.py / test_resilience_review.py) of
module-level helper functions rather than pytest fixtures.
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.registry.canonical_manifest import load_canonical_manifest
from scripts.registry.load import load_registry
from scripts.evals.dispatcher import dispatch_prompt
from scripts import production_readiness as pr

ROOT = Path(__file__).resolve().parents[2]

_DEFAULT_REVISION = "a" * 40


# ---------------------------------------------------------------------------
# Dimension fixtures
# ---------------------------------------------------------------------------


def dimension(name: str, status: str, *, applicability: str = "REQUIRED", evidence_status: str | None = None) -> pr.Dimension:
    return pr.Dimension(name=name, status=status, applicability=applicability, evidence_status=evidence_status)


dim = dimension


def readiness_fixture_dimensions() -> list[pr.Dimension]:
    return [
        dimension("security", "PASS"),
        dimension("api", "CONDITIONAL"),
        dimension("capacity", "PASS"),
        dimension("observability", "UNKNOWN"),
    ]


def deterministic_permutations(items: Sequence[Any], limit: int = 24) -> list[list[Any]]:
    items = list(items)
    if len(items) <= 4:
        perms = [list(p) for p in itertools.permutations(items)]
    else:
        perms = [items, list(reversed(items))]
    return perms[:limit]


def summarize_required_passes(dims: Sequence[pr.Dimension]) -> int:
    return sum(1 for d in dims if d.applicability != "NOT_APPLICABLE" and d.status != "NOT_APPLICABLE" and d.status == "PASS")


# ---------------------------------------------------------------------------
# Candidate fixtures
# ---------------------------------------------------------------------------


def source_candidate(
    source_revision: str = _DEFAULT_REVISION,
    *,
    environment: str | None = None,
    repo: str = "acme/checkout",
    service: str = "checkout",
    criticality: str = "unknown",
) -> dict[str, Any]:
    return {
        "repo": repo,
        "service": service,
        "environment": environment,
        "source_revision": source_revision,
        "head_revision_or_digest": source_revision,
        "source_type": "pr",
        "criticality": criticality,
    }


def image_candidate(
    *,
    source_revision: str = _DEFAULT_REVISION,
    digest: str = "sha256:" + "b" * 64,
    environment: str | None = None,
    repo: str = "acme/checkout",
    service: str = "checkout",
    criticality: str = "unknown",
) -> dict[str, Any]:
    return {
        "repo": repo,
        "service": service,
        "environment": environment,
        "source_revision": source_revision,
        "head_revision_or_digest": digest,
        "source_type": "release_candidate",
        "criticality": criticality,
    }


def mr_context(*, project: str = "acme/checkout", iid: int = 1, head_sha: str = _DEFAULT_REVISION) -> dict[str, Any]:
    return {"project": project, "merge_request_iid": iid, "head_sha": head_sha}


def assessment_context_fixture(
    *,
    assessment_target: Mapping[str, Any] | None = None,
    inputs: Mapping[str, Any] | None = None,
    input_provenance: Mapping[str, Any] | None = None,
    evidence_refs: Sequence[str] | None = None,
    unresolved: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "assessment_target": dict(assessment_target or source_candidate()),
        "inputs": dict(inputs or {}),
        "input_provenance": dict(input_provenance or {}),
        "evidence_refs": list(evidence_refs or []),
        "unresolved": list(unresolved or []),
    }


# ---------------------------------------------------------------------------
# Child result fixtures
# ---------------------------------------------------------------------------


def trusted_child_result(
    artifact_type: str = "generic_report",
    *,
    status: str = "PASS",
    target: Mapping[str, Any] | None = None,
    source_revision: str | None = None,
    environment: Any = "__unset__",
    evidence_authorities: Mapping[str, Any] | None = None,
    producer_trusted: bool = True,
    coverage_status: str | None = None,
    environment_specific: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    if target is not None:
        resolved_revision = source_revision or target.get("source_revision", _DEFAULT_REVISION)
    else:
        resolved_revision = source_revision or _DEFAULT_REVISION

    result: dict[str, Any] = {
        "artifact_type": artifact_type,
        "status": status,
        "source_revision": resolved_revision,
        "target": target,
        "evidence_authorities": dict(evidence_authorities) if evidence_authorities is not None else {"result": {"repository"}},
        "producer_trusted": producer_trusted,
        "environment_specific": environment_specific,
    }
    if environment != "__unset__":
        result["environment"] = environment
    else:
        result["environment"] = None
    if coverage_status is not None:
        result["coverage_status"] = coverage_status
    result.update(extra)
    return result


def caller_supplied_impact(*, source_revision: str = _DEFAULT_REVISION, coverage_status: str = "COMPLETE", **extra: Any) -> dict[str, Any]:
    return trusted_child_result(
        "change_impact_report",
        source_revision=source_revision,
        coverage_status=coverage_status,
        evidence_authorities={"result": {"caller"}},
        **extra,
    )


def trusted_impact(*, source_revision: str = _DEFAULT_REVISION, coverage_status: str = "COMPLETE", **extra: Any) -> dict[str, Any]:
    return trusted_child_result(
        "change_impact_report",
        source_revision=source_revision,
        coverage_status=coverage_status,
        evidence_authorities={"result": {"repository"}},
        **extra,
    )


# ---------------------------------------------------------------------------
# CI / build provenance / SCM policy fixtures
# ---------------------------------------------------------------------------


def trusted_ci(
    *,
    head_revision: str = _DEFAULT_REVISION,
    all_required_green: bool = True,
    acquisition: str = "authoritative_host",
    **extra: Any,
) -> dict[str, Any]:
    return {
        "provider": "github",
        "repo": "acme/checkout",
        "head_revision": head_revision,
        "required_checks": ["build", "test"],
        "observed_checks": ["build", "test"],
        "all_required_green": all_required_green,
        "observed_at": "2026-08-24T12:00:00Z",
        "acquisition": acquisition,
        "evidence_ref": "ci:1",
        **extra,
    }


def ci_green(**overrides: Any) -> dict[str, Any]:
    return trusted_ci(all_required_green=True, **overrides)


def ci_failed(**overrides: Any) -> dict[str, Any]:
    return trusted_ci(all_required_green=False, **overrides)


def build_provenance(
    *,
    source_revision: str = _DEFAULT_REVISION,
    digest: str = "sha256:" + "b" * 64,
    build_status: str = "SUCCESS",
    **extra: Any,
) -> dict[str, Any]:
    return {
        "provider": "github-actions",
        "repo": "acme/checkout",
        "source_revision": source_revision,
        "deployable_digest": digest,
        "build_run_id": "run-1",
        "build_status": build_status,
        "observed_at": "2026-08-24T12:00:00Z",
        "acquisition": "authoritative_host",
        "evidence_ref": "build:1",
        **extra,
    }


def build_fixture(
    *,
    policy_requires_attestation: bool = False,
    attestation: str | None = None,
    candidate: Mapping[str, Any] | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "policy_requires_attestation": policy_requires_attestation,
        "attestation": attestation,
        "candidate": candidate,
        "provenance": provenance,
    }


def code_review_coverage(
    *,
    status: str = "COMPLETE",
    candidate_source_revision: str = _DEFAULT_REVISION,
    uncovered_change_refs: Sequence[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "candidate_source_revision": candidate_source_revision,
        "status": status,
        "included_change_refs": [],
        "trusted_review_refs": [],
        "uncovered_change_refs": list(uncovered_change_refs or []),
        "evidence_refs": [],
        "acquisition": "authoritative_host",
        **extra,
    }


def policy(**overrides: Any) -> dict[str, Any]:
    base = {
        "required_approvals": 0,
        "codeowners_required": False,
        "blocking_threads_must_resolve": False,
        "require_review": False,
    }
    base.update(overrides)
    return base


def observed(**overrides: Any) -> dict[str, Any]:
    base = {
        "approvals": 0,
        "codeowners_satisfied": True,
        "blocking_threads_open": 0,
        "policy_bypass_refs": [],
        "bypass_approved": None,
    }
    base.update(overrides)
    return base


def policy_state(*, approvals_ok: bool = True) -> dict[str, Any]:
    return {"approvals_ok": approvals_ok}


def dependency_ci_fixture(
    *,
    source_revision: str = _DEFAULT_REVISION,
    required: bool = True,
    scope_covers_changed_manifest: bool = True,
    conclusion: str = "success",
) -> dict[str, Any]:
    return {
        "source_revision": source_revision,
        "required": required,
        "scope_covers_changed_manifest": scope_covers_changed_manifest,
        "conclusion": conclusion,
    }


# ---------------------------------------------------------------------------
# Operational-gate fixtures (Task 7.5)
# ---------------------------------------------------------------------------


def caller_owner() -> dict[str, Any]:
    return {"owner_authority": "caller", "owner": "someone", "escalation_route": "#on-call"}


def authoritative_unowned() -> dict[str, Any]:
    return {"owner_authority": "authoritative_host", "unowned": True}


def tier1_stateful_fixture(
    *, policy_freshness: str | None = "2026-08-01T00:00:00Z", mechanism_authority: str = "authoritative_host"
) -> dict[str, Any]:
    return {
        "stateful": True,
        "reversible": False,
        "mechanism_authority": mechanism_authority,
        "rpo_rto_policy": {"rpo_minutes": 15, "rto_minutes": 60},
        "last_exercise": {"date": "2026-07-01", "result": "success"},
        "policy_freshness": policy_freshness,
    }


def stateless_reversible_fixture() -> dict[str, Any]:
    return {"stateful": False, "reversible": True}


def rollback_fixture(*, authority: str = "caller", complete: bool = True, **extra: Any) -> dict[str, Any]:
    base = {
        "authority": authority,
        "complete": complete,
        "trigger": "error rate > 5%",
        "action": "revert to previous revision",
        "actor": "on-call engineer",
        "decision_window_minutes": 15,
    }
    base.update(extra)
    return base


def post_deploy_fixture(*, signal_authority: str = "caller", complete: bool = True, **extra: Any) -> dict[str, Any]:
    base = {
        "signals": ["error_rate", "latency_p99"],
        "observation_window": "30m",
        "success_criteria": "error_rate < 1%",
        "abort_criteria": "error_rate > 5%",
        "decision_owner": "on-call engineer",
        "signal_authority": signal_authority,
        "complete": complete,
    }
    base.update(extra)
    return base


# ---------------------------------------------------------------------------
# Dispatch / gate-policy fixtures
# ---------------------------------------------------------------------------


def spy(*, return_value: Any = None, unavailable: bool = False):
    calls = {"count": 0}

    def _spy(*args: Any, **kwargs: Any) -> Any:
        calls["count"] += 1
        if unavailable:
            return None
        return return_value

    class _Spy:
        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            return _spy(*args, **kwargs)

        @property
        def calls(self) -> int:
            return calls["count"]

    return _Spy()


def child_gate_policy(child_name: str) -> pr.ChildGatePolicy:
    return pr.child_gate_policy(child_name)


def readiness_authority() -> pr.ReadinessAuthority:
    return pr.readiness_authority()


# ---------------------------------------------------------------------------
# Registry helpers (read the real canonical manifest/runtime)
# ---------------------------------------------------------------------------


def registry():
    return load_registry(ROOT)


def invoked_skills(skill_id: str) -> list[str]:
    return list(registry().skills[skill_id].composition.invokes)


def runtime_handoff_artifacts(parent: str, child: str) -> list[str]:
    manifest = load_canonical_manifest(ROOT)
    handoffs = manifest["contracts"]["composition_runtime"]["handoffs"]
    return list(handoffs.get(parent, {}).get(child, []))


def consumes(skill_id: str, artifact_type: str) -> bool:
    manifest = load_canonical_manifest(ROOT)
    contract = manifest["contracts"]["composition"]["skills"].get(skill_id, {})
    return artifact_type in contract.get("consumes", [])


def dispatch_prompt_owner(prompt: str) -> str | None:
    result = dispatch_prompt(ROOT, load_registry(ROOT), prompt)
    assert result.status == "selected", result
    return result.owner


# ---------------------------------------------------------------------------
# End-to-end harnesses
# ---------------------------------------------------------------------------


def run_readiness(*, candidate: Mapping[str, Any] | None = None, **kwargs: Any) -> pr.ProductionReadinessResult:
    return pr.production_readiness(candidate or {}, **kwargs)


def readiness_run(
    *,
    start_head: str = _DEFAULT_REVISION,
    final_head: str = _DEFAULT_REVISION,
    start_ci=None,
    final_ci=None,
    start_policy: Mapping[str, Any] | None = None,
    final_policy: Mapping[str, Any] | None = None,
    start_release_resolution: str | None = None,
    final_release_resolution: str | None = None,
    dimensions: Sequence[pr.Dimension] | None = None,
) -> pr.ProductionReadinessResult:
    initial = {
        "head": start_head,
        "release_resolution": start_release_resolution,
        "ci_green": (start_ci or {}).get("all_required_green") if start_ci is not None else None,
        "approvals_ok": (start_policy or {}).get("approvals_ok") if start_policy is not None else None,
    }
    final = {
        "head": final_head,
        "release_resolution": final_release_resolution,
        "ci_green": (final_ci or {}).get("all_required_green") if final_ci is not None else None,
        "approvals_ok": (final_policy or {}).get("approvals_ok") if final_policy is not None else None,
    }
    freshness = pr.check_final_freshness(initial, final)

    dims = list(dimensions if dimensions is not None else [dimension("security", "PASS")])
    if freshness.status != "PASS":
        dims.append(dimension("__freshness__", freshness.status))

    readiness = pr.aggregate_readiness(dims)
    return pr.ProductionReadinessResult(
        verdict=readiness.verdict,
        skill_result=pr.SkillResult(status=readiness.skill_result_status, evidence_status=readiness.evidence_status),
        dimension_statuses=readiness.dimensions,
    )
