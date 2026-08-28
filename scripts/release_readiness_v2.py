"""Backward-compatible release manifest v2 parsing, trusted production-readiness
reuse, and conditional production-readiness invocation for release-readiness-checker.

Manifest v1 behavior (repo/service/since/release_ref, never invoking production
readiness) is completely preserved -- this module only adds behavior for entries
that carry v2-only fields. Everything here is pure, side-effect-free evidence
logic; registry wiring, dispatcher integration, and the real production-readiness-
review invocation live outside this module (`production_invoke` here is a
policy-level adapter only, matching scripts/production_readiness.py's own
`dispatch_child` convention).
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable, Mapping, MutableMapping, Optional, Sequence

from scripts import production_readiness as pr
from scripts.registry.assessment_target import (
    normalize_repo_identity,
    normalize_service_identity,
    same_environment,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_VERDICT_SEVERITY = {"READY": 0, "CONDITIONAL": 1, "UNKNOWN": 2, "NOT_READY": 3}

# Existing v1 checks (pr-review / k8s / incident) map their own outcome vocabulary
# onto the same four-state release verdict release-readiness-checker's Markdown
# contract already defines (reference/report-format.md) -- this table exists so
# the pure-python harness below can fold a per-check outcome into the overall
# release verdict the same way the real skill's fixed precedence does.
_CHECK_STATUS_VERDICT = {
    "PASS": "READY",
    "CLEAR": "READY",
    "READY": "READY",
    "CONDITIONAL": "CONDITIONAL",
    "FLAGGED": "CONDITIONAL",
    "NOT_READY": "NOT_READY",
    "BLOCKED": "NOT_READY",
    "FAIL": "NOT_READY",
    "UNKNOWN": "UNKNOWN",
    "NOT_RUN": "UNKNOWN",
}


def cap_release_verdict(current: str, production_verdict: str) -> str:
    """Worst-first cap: a release verdict is never better than production readiness's own.

    NOT_READY caps to NOT_READY, UNKNOWN caps to UNKNOWN, CONDITIONAL caps to at
    most CONDITIONAL, READY never downgrades an already-worse existing verdict.
    An unrecognized production verdict is never treated as the permissive READY.
    """
    if production_verdict not in _VERDICT_SEVERITY:
        production_verdict = "UNKNOWN"
    if current not in _VERDICT_SEVERITY:
        current = "UNKNOWN"
    return current if _VERDICT_SEVERITY[current] >= _VERDICT_SEVERITY[production_verdict] else production_verdict


# ---------------------------------------------------------------------------
# Manifest v1/v2 parsing (Included implementation slice 2)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ReleaseEntry:
    repo: Optional[str]
    service: Optional[str]
    since: Optional[str]
    release_ref: Optional[str] = None
    environment: Optional[str] = None
    source_revision: Optional[str] = None
    criticality: Optional[str] = None
    production_readiness_required: bool = False
    production_readiness_ref: Optional[str] = None

    def compatibility_projection(self) -> Mapping[str, Any]:
        """The exact v1 field/shape projection -- must equal `legacy_parse(entry)`
        for any v1-shaped entry, so v1 behavior is provably unchanged by the v2 parser.
        """
        return {
            "repo": self.repo,
            "service": self.service,
            "since": self.since,
            "release_ref": self.release_ref,
        }


def parse_release_entry(entry: Mapping[str, Any]) -> ReleaseEntry:
    entry = pr._as_mapping(entry)
    return ReleaseEntry(
        repo=entry.get("repo"),
        service=entry.get("service"),
        since=entry.get("since"),
        release_ref=entry.get("release_ref"),
        environment=entry.get("environment"),
        source_revision=entry.get("source_revision"),
        criticality=entry.get("criticality"),
        production_readiness_required=entry.get("production_readiness_required") is True,
        production_readiness_ref=entry.get("production_readiness_ref"),
    )


def _normalize_manifest(manifest: Any) -> list:
    if manifest is None:
        return []
    if isinstance(manifest, Mapping):
        return [manifest]
    if isinstance(manifest, Sequence) and not isinstance(manifest, (str, bytes)):
        return list(manifest)
    return []


# ---------------------------------------------------------------------------
# Trusted reuse / matching (Included implementation slice 3)
# ---------------------------------------------------------------------------


def classify_report_for_release(report: Mapping[str, Any]) -> MutableMapping[str, Any]:
    """A schema-valid production_readiness_report is not automatically gate-trusted.

    Only a runtime-validated/direct-child acquisition can satisfy a release gate --
    a caller-supplied or repository-file artifact is discovery evidence only, per
    the design's "no generic artifact store / file self-attestation" invariant.
    """
    report = pr._as_mapping(report)
    if report.get("producer_trusted", True) is not True:
        return {"trusted_for_gate": False, "reason": "untrusted_producer"}
    acquisition = report.get("acquisition")
    trusted = acquisition in ("direct_child", "runtime_validated", "trusted_runtime", "authoritative_host")
    return {
        "trusted_for_gate": trusted,
        "reason": "" if trusted else "untrusted_acquisition",
    }


def match_release_report(entry: Any, report: Mapping[str, Any]) -> MutableMapping[str, Any]:
    """Deployable-scoped identity match: canonical repo/service, exact environment
    when the entry declares one, exact release_ref == report's deployable target,
    and exact source_revision when the entry declares one. No fuzzy matching.
    """
    parsed = entry if isinstance(entry, ReleaseEntry) else parse_release_entry(entry)
    report = pr._as_mapping(report)
    target = pr._target_of(report) or report

    if not parsed.repo or not parsed.service:
        return {"status": "UNKNOWN", "reason": "missing_candidate_identity"}

    report_repo = target.get("repo")
    if not report_repo or normalize_repo_identity(report_repo) != normalize_repo_identity(parsed.repo):
        return {"status": "UNKNOWN", "reason": "repo_mismatch"}

    report_service = target.get("service")
    if not report_service or normalize_service_identity(report_service) != normalize_service_identity(parsed.service):
        return {"status": "UNKNOWN", "reason": "service_mismatch"}

    if parsed.environment is not None:
        report_env = target.get("environment")
        if report_env is None or not same_environment(parsed.environment, report_env):
            return {"status": "UNKNOWN", "reason": "environment_mismatch"}

    if not parsed.release_ref:
        return {"status": "UNKNOWN", "reason": "missing_release_ref"}
    report_head = target.get("head_revision_or_digest")
    if not report_head or report_head != parsed.release_ref:
        return {"status": "UNKNOWN", "reason": "release_ref_mismatch"}

    if parsed.source_revision is not None:
        report_source_revision = report.get("source_revision") or target.get("source_revision")
        if report_source_revision != parsed.source_revision:
            return {"status": "UNKNOWN", "reason": "source_revision_mismatch"}

    return {"status": "MATCH"}


# ---------------------------------------------------------------------------
# Conditional production-readiness invocation (Included implementation slice 4)
# ---------------------------------------------------------------------------


def _looks_like_digest(ref: str) -> bool:
    return ":" in ref


def _candidate_identity_sufficient(entry: ReleaseEntry) -> bool:
    """True only when enough identity exists to safely invoke production readiness.

    A release_ref that is itself a source revision needs nothing else. A release_ref
    shaped like a build/image digest (contains ':', e.g. `sha256:...`) needs an
    explicit source_revision -- without one, there is no way to prove code-review/CI
    evidence about *this* deployable, so invocation must not be attempted at all.
    """
    if not entry.release_ref:
        return False
    if entry.source_revision:
        return True
    return not _looks_like_digest(entry.release_ref)


def _candidate_from_entry(entry: ReleaseEntry) -> MutableMapping[str, Any]:
    return {
        "repo": entry.repo,
        "service": entry.service,
        "environment": entry.environment,
        "source_revision": entry.source_revision,
        "head_revision_or_digest": entry.release_ref,
        "source_type": "release_candidate",
        "criticality": entry.criticality or "unknown",
    }


def _coverage_is_trustworthy_and_complete(coverage: Optional[Mapping[str, Any]]) -> bool:
    """A release-assembled code_review_coverage bundle is usable only when it is
    both complete AND carries a host/runtime-authoritative acquisition.

    `coverage` must NEVER be sourced from a caller-supplied/manifest-text channel
    (see `resolve_production_readiness`'s own `code_review_coverage` parameter,
    which is deliberately kept separate from the parsed manifest entry) -- but
    even so, this checks the acquisition field defensively, the same way
    `scripts/production_readiness.py`'s `validate_code_review_coverage` gates its
    own `coverage.get("acquisition")` via `_is_host_or_runtime_acquisition`. A
    bundle claiming `status: COMPLETE` with no (or a weak) acquisition is never
    trusted merely because it claims completeness -- that is exactly the
    self-attestation this whole module exists to prevent.
    """
    coverage = pr._as_mapping(coverage) if coverage is not None else None
    if not coverage:
        return False
    if coverage.get("status") != "COMPLETE":
        return False
    return pr._is_host_or_runtime_acquisition(coverage.get("acquisition"))


def build_assessment_context(
    entry: ReleaseEntry,
    *,
    code_review_coverage: Optional[Mapping[str, Any]] = None,
) -> MutableMapping[str, Any]:
    candidate = _candidate_from_entry(entry)
    inputs: MutableMapping[str, Any] = {}
    input_provenance: MutableMapping[str, Any] = {}
    evidence_refs: list = []
    if entry.since:
        # Release base/since context for the child's own impact discovery
        # (design v10 Sec9.2) -- contextual scoping data, not a trust-bearing
        # claim, so "caller" authority is the honest label for it.
        inputs["since"] = entry.since
        input_provenance["since"] = {"authority": "caller", "evidence_refs": []}
    if code_review_coverage is not None:
        inputs["code_review_coverage"] = code_review_coverage
        authority = "trusted_runtime" if _coverage_is_trustworthy_and_complete(code_review_coverage) else "caller"
        coverage_refs = list(pr._as_mapping(code_review_coverage).get("evidence_refs", []) or [])
        input_provenance["code_review_coverage"] = {
            "authority": authority,
            "evidence_refs": coverage_refs,
        }
        evidence_refs.extend(coverage_refs)
    return {
        "assessment_target": candidate,
        "inputs": inputs,
        "input_provenance": input_provenance,
        "evidence_refs": evidence_refs,
        "unresolved": [],
    }


def resolve_production_readiness(
    entry: Any,
    *,
    trusted_reports: Optional[Sequence[Mapping[str, Any]]] = None,
    production_invoke: Optional[Callable[..., Any]] = None,
    code_review_coverage: Optional[Mapping[str, Any]] = None,
) -> MutableMapping[str, Any]:
    """Reuse-first, conditional-invoke resolution for one v2 manifest entry.

    `code_review_coverage` is a trusted-runtime input the caller (release-
    readiness-checker's own orchestration, after real SCM enumeration) supplies
    out of band -- deliberately NOT a field read off the untrusted manifest-entry
    mapping, so a `release_manifest` author can never inject a self-attested
    "already reviewed, trust me" coverage bundle merely by adding a key to their
    YAML. See `_coverage_is_trustworthy_and_complete` for the defensive
    acquisition check applied on top of that structural separation.

    Never invoked at all for a v1 entry (production_readiness_required defaults
    False) -- callers must check that flag before calling this, matching
    `run_release`'s own behavior below.
    """
    parsed = entry if isinstance(entry, ReleaseEntry) else parse_release_entry(entry)
    if not parsed.production_readiness_required:
        return {"status": "NOT_REQUIRED", "source": None, "report": None}

    # 1. Reuse first. A trusted, fresh, deployable-scoped report always wins,
    # regardless of whether release-assembled code-review coverage is ready --
    # per release-readiness-checker/workflow/run-check.md Sec6, reuse is
    # attempted before the coverage-driven invoke gate below, never after it.
    matches = []
    for report in trusted_reports or ():
        classification = classify_report_for_release(report)
        if not classification["trusted_for_gate"]:
            continue
        match = match_release_report(parsed, report)
        if match["status"] == "MATCH":
            matches.append(report)

    if parsed.production_readiness_ref is not None:
        # An explicit pin narrows reuse to the one report it names -- other
        # identity-matching-but-unpinned reports are not silently substituted.
        matches = [r for r in matches if r.get("report_ref") == parsed.production_readiness_ref]

    if matches:
        verdicts = {r.get("verdict", "UNKNOWN") for r in matches}
        if len(verdicts) > 1:
            # Two trusted, identity-matching reports that disagree are
            # conflicting authoritative evidence -- per the evidence-authority
            # policy, this is never silently resolved by picking one; it is
            # UNKNOWN until reconciled by a fresher/pinned report.
            return {"status": "UNKNOWN", "source": None, "report": None}
        return {"status": matches[0].get("verdict", "UNKNOWN"), "source": "REUSED", "report": matches[0]}

    # 2. Otherwise, invoke only when safe.
    if not _candidate_identity_sufficient(parsed):
        return {"status": "UNKNOWN", "source": None, "report": None}

    if code_review_coverage is not None and not _coverage_is_trustworthy_and_complete(code_review_coverage):
        # Task 5.5: release-assembled code-review coverage that is known
        # incomplete (or not host/runtime-authoritative) must not trigger a
        # child invocation merely to obtain a predictable UNKNOWN -- and must
        # never be "fixed" by letting the child revisit pr-review, which would
        # both duplicate the release root's own review pass and risk defeating
        # the composition recursion guard.
        return {"status": "UNKNOWN", "source": None, "report": None}

    if production_invoke is None:
        return {"status": "UNKNOWN", "source": None, "report": None}

    candidate = _candidate_from_entry(parsed)
    assessment_context = build_assessment_context(parsed, code_review_coverage=code_review_coverage)
    invoked = production_invoke(candidate, assessment_context=assessment_context)
    if invoked is None:
        return {"status": "UNKNOWN", "source": None, "report": None}

    classification = classify_report_for_release(invoked)
    if not classification["trusted_for_gate"]:
        return {"status": "UNKNOWN", "source": None, "report": None}
    match = match_release_report(parsed, invoked)
    if match["status"] != "MATCH":
        return {"status": "UNKNOWN", "source": None, "report": None}
    return {"status": invoked.get("verdict", "UNKNOWN"), "source": "INVOKED", "report": invoked}


# ---------------------------------------------------------------------------
# Code-review coverage handoff (Task 5)
# ---------------------------------------------------------------------------


def _change_ref_id(change: Any, index: int) -> str:
    """Resolve one included-change entry to a stable ref string.

    A malformed/unresolvable entry (wrong key, non-mapping, empty string, ...)
    is never dropped -- it becomes a synthetic ref that can never appear in
    `trusted_review_refs`/`integrated_revisions`, so it always counts as
    uncovered. Silently skipping it instead would let a manifest with N real
    changes and one malformed entry look identical to one with N-1 changes,
    letting coverage read COMPLETE when a real change was never accounted for.
    """
    if isinstance(change, Mapping):
        ref = change.get("ref")
        if isinstance(ref, str) and ref:
            return ref
    elif isinstance(change, str) and change:
        return change
    return f"__unresolvable_change_{index}__"


def build_code_review_coverage(
    *,
    candidate_source_revision: str,
    included_change_refs: Sequence[Any],
    trusted_review_refs: Sequence[str],
    integrated_revisions: Optional[Mapping[str, str]] = None,
    acquisition: str = "authoritative_host",
) -> MutableMapping[str, Any]:
    """Enumerate every material change in range and its trusted review coverage.

    `included_change_refs` must include every material change type -- merged
    PR/MR objects, direct commits, cherry-picks, and reverts alike; the caller
    (release-readiness-checker's own authoritative SCM enumeration) is
    responsible for never silently omitting one of those kinds.

    `integrated_revisions` is the ONLY source of PR/MR-to-merge-commit linkage
    this function trusts -- it must come from authoritative SCM merge/squash
    metadata. A change's own claimed/forged linkage (e.g. an untrusted
    `claimed_integrated_revision` field a caller attached to a ref mapping) is
    never consulted, so a forged integrated revision has no effect.
    """
    included_refs = [_change_ref_id(change, index) for index, change in enumerate(included_change_refs)]
    reviewed = set(trusted_review_refs)
    integrated_revisions = dict(integrated_revisions or {})

    def _is_covered(ref: str) -> bool:
        if ref in reviewed:
            return True
        integrated = integrated_revisions.get(ref)
        return bool(integrated) and integrated in reviewed

    uncovered = [ref for ref in included_refs if not _is_covered(ref)]
    if not included_refs:
        status = "UNKNOWN"
    elif uncovered:
        status = "PARTIAL"
    else:
        status = "COMPLETE"

    return {
        "candidate_source_revision": candidate_source_revision,
        "status": status,
        "included_change_refs": included_refs,
        "trusted_review_refs": list(trusted_review_refs),
        "uncovered_change_refs": uncovered,
        "evidence_refs": list(trusted_review_refs),
        "acquisition": acquisition,
    }


# ---------------------------------------------------------------------------
# Release-result envelope + execution-status semantics (Task 7.5)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SkillResult:
    status: str
    evidence_status: str = "UNKNOWN"


@dataclasses.dataclass
class ReleaseResult:
    verdict: str
    skill_result: SkillResult
    production_readiness_source: Optional[str] = None
    production_readiness: Optional[str] = None
    checks: list = dataclasses.field(default_factory=list)
    candidate_changed_during_review: bool = False

    @property
    def overall(self) -> str:
        return self.verdict

    def __getitem__(self, key: str) -> Any:
        if key == "verdict":
            return self.verdict
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except AttributeError:
            return default


def finalize_release(pre: Mapping[str, Any]) -> ReleaseResult:
    """Execution status vs decision status, mirroring production_readiness.py's own
    axis split: a resolved NOT_READY is a SUCCESSFUL analysis; an unresolved
    required dimension makes the result PARTIAL regardless of what the (possibly
    already-worst-case) verdict is; an empty manifest is BLOCKED, never FAILED.
    """
    pre = pr._as_mapping(pre)
    overall = pre.get("overall", "UNKNOWN")
    unknown_dimensions = list(pre.get("unknown_dimensions") or [])
    status = "PARTIAL" if unknown_dimensions else "SUCCESS"
    evidence_status = "UNKNOWN" if unknown_dimensions else "OBSERVED"
    return ReleaseResult(
        verdict=overall,
        skill_result=SkillResult(status=status, evidence_status=evidence_status),
        production_readiness_source=pre.get("production_readiness_source"),
        production_readiness=pre.get("production_readiness"),
        checks=list(pre.get("checks", [])),
        candidate_changed_during_review=bool(pre.get("candidate_changed_during_review", False)),
    )


# ---------------------------------------------------------------------------
# Top-level orchestration entry (Task 1 + Task 6 aggregate caps + Task 6.5 fence)
# ---------------------------------------------------------------------------

_EXISTING_CHECKS = ("pr_review", "k8s", "incident")


def run_release(
    manifest: Any,
    *,
    trusted_reports: Optional[Sequence[Mapping[str, Any]]] = None,
    production_invoke: Optional[Callable[..., Any]] = None,
    check_spy: Any = None,
    start_ref: Optional[str] = None,
    final_ref: Optional[str] = None,
    code_review_coverage: Optional[Mapping[str, Any]] = None,
) -> ReleaseResult:
    """`code_review_coverage`, like `trusted_reports`/`production_invoke`, is a
    trusted-runtime input supplied by release-readiness-checker's own execution
    harness -- never sourced from `manifest` itself. It applies to whichever
    entry in this run requires production readiness (today's real orchestration
    calls this per release candidate, matching every existing test's shape).
    """
    entries = _normalize_manifest(manifest)
    if not entries:
        # HARD STOP per v1's own definition_of_done -- an empty manifest is a
        # blocked precondition, never a resolved (SUCCESS/PARTIAL) analysis and
        # never an internal execution failure (FAILED).
        return ReleaseResult(
            verdict="UNKNOWN",
            skill_result=SkillResult(status="BLOCKED", evidence_status="UNKNOWN"),
        )

    overall = "READY"
    production_readiness_source: Optional[str] = None
    production_readiness_value: Optional[str] = None
    checks: list = []
    unknown_dimensions: list = []
    candidate_changed = False

    ref_moved = start_ref is not None and final_ref is not None and start_ref != final_ref

    for raw_entry in entries:
        parsed = parse_release_entry(raw_entry)

        # Existing PR/K8s/incident checks are never skipped because of anything
        # production readiness does or doesn't find -- they always run first,
        # per entry, exactly as v1 already does.
        for name in _EXISTING_CHECKS:
            if check_spy is not None:
                outcome = check_spy.run(name)
                status = outcome.get("status", "UNKNOWN") if isinstance(outcome, Mapping) else "UNKNOWN"
                checks.append({"name": name, "status": status, "executed": True})
                mapped = _CHECK_STATUS_VERDICT.get(status, "UNKNOWN")
                overall = cap_release_verdict(overall, mapped)
                if mapped == "UNKNOWN":
                    # An executed check that itself resolved to an evidence gap
                    # is exactly as unresolved as one that never ran at all --
                    # both must be reported PARTIAL, never a false SUCCESS.
                    unknown_dimensions.append(name)
            else:
                # No wrapped-skill harness supplied -- an unexecuted check is an
                # evidence gap (UNKNOWN), never an implicit PASS.
                checks.append({"name": name, "status": "NOT_RUN", "executed": False})
                overall = cap_release_verdict(overall, "UNKNOWN")
                unknown_dimensions.append(name)

        if ref_moved:
            # Task 6.5 final freshness fence: a mutable release reference that
            # resolved differently between the start and end of this run means
            # the candidate moved mid-review -- combining evidence gathered
            # against two different identities is never safe. Applies to every
            # entry (v1 included): this is a general release-candidate identity
            # fence, independent of whether production readiness is separately
            # gated for that entry.
            candidate_changed = True
            overall = "UNKNOWN"
            unknown_dimensions.append("release_ref_freshness")
            continue

        if not parsed.production_readiness_required:
            continue

        resolution = resolve_production_readiness(
            parsed,
            trusted_reports=trusted_reports,
            production_invoke=production_invoke,
            code_review_coverage=code_review_coverage,
        )
        production_readiness_source = resolution["source"]
        production_readiness_value = resolution["status"]
        if resolution["status"] == "NOT_REQUIRED":
            continue
        if resolution["status"] not in _VERDICT_SEVERITY:
            unknown_dimensions.append("production_readiness")
            overall = cap_release_verdict(overall, "UNKNOWN")
            continue
        if resolution["status"] == "UNKNOWN":
            unknown_dimensions.append("production_readiness")
        overall = cap_release_verdict(overall, resolution["status"])

    return finalize_release(
        {
            "overall": overall,
            "unknown_dimensions": unknown_dimensions,
            "production_readiness_source": production_readiness_source,
            "production_readiness": production_readiness_value,
            "checks": checks,
            "candidate_changed_during_review": candidate_changed,
        }
    )
