---
workflow_version: 1.0
phase: collect-evidence
produces:
  - ci_evidence
  - scm_policy_evidence
  - build_provenance_evidence
  - change_impact_evidence
  - deployment_risk_evidence
  - freshness_snapshot
consumes:
  - assessment_target
  - criticality
  - source_revision
  - build_provenance_ref
---

# Collect evidence — CI, SCM policy, build provenance, change-impact, deployment-risk

Gather every foundational evidence source before deciding which specialists to dispatch. Each source
below is independently optional — a missing one degrades only its own dimension to `UNKNOWN` in
Aggregate, never blocks the others and never fabricates a `PASS`.

Record a `freshness_snapshot` here too — the candidate's head identity, CI status, and approval
state as read in this phase — for [report.md § Final freshness re-check](report.md) to compare
against immediately before the report is emitted.

## 1. CI status — `host.ci.status`

Read the exact source revision's required-check results. Record pass/fail per required check. A check
still running, or the capability unavailable, is `UNKNOWN` for the CI dimension — never assumed
passing.

## 2. SCM policy — `host.scm.policy.read`

Read approvals, CODEOWNERS coverage, branch-protection rules, and unresolved review threads at the
exact source revision. An unresolved required thread or a missing required approval is a genuine
finding, not an evidence gap; capability unavailability is `UNKNOWN`. A policy document that could
only be partially read (a required-approvals/CODEOWNERS/blocking-threads rule that didn't resolve)
is `UNKNOWN`, never a permissive "not required" default. A recorded branch-protection bypass is a
`FAIL` unless it carries an authoritative approver and an evidence reference — a caller's bare "yes
it was approved" claim never suppresses it.

## 3. Build provenance — `host.build.provenance.read`

When `build_provenance_ref` is not `NOT_APPLICABLE`, resolve the link from `source_revision` to its
deployable digest. A `source_revision` with a known build step but no resolvable digest is `UNKNOWN`
for this dimension — never silently treated as `NOT_APPLICABLE`.

## 4. Change impact — reuse or refresh via `change-impact-analyzer.invoke`

Prefer a fresh, trusted `change_impact_report` already produced for this exact `source_revision`. When
none is available or it is stale, invoke **change-impact-analyzer** with the exact `assessment_target`
as its own `assessment_context` (see [child-input-map.md](../reference/child-input-map.md)). Its `change_classes`
and `impacted_*` fields are the sole basis for deciding which specialists Dispatch invokes — never
inferred from the PR/MR title or description text. Missing or `UNKNOWN` coverage here means every
specialist-applicability decision downstream defaults to "cannot determine — treat as applicable and
dispatch, or record `UNKNOWN` if the specialist's own mandatory input can't be assembled either,"
never "assume no specialists apply."

## 5. Deployment risk — reuse or refresh via `deployment-risk-review.invoke`

Same reuse-or-refresh rule as change-impact: prefer a fresh trusted `deployment_risk_report`; otherwise
invoke **deployment-risk-review** with the change description and evidence already collected. Its own
`Risk` verdict and `deployment_confidence` are recorded as-is — this skill never re-labels them.

## Required outputs

| Output | Required fields |
|--------|------------------|
| `ci_evidence` | Per-required-check pass/fail, or `UNKNOWN` |
| `scm_policy_evidence` | Approvals, CODEOWNERS, unresolved-thread state, or `UNKNOWN` |
| `build_provenance_evidence` | Resolved digest, `NOT_APPLICABLE`, or `UNKNOWN` |
| `change_impact_evidence` | `change_classes`, `impacted_*`, `coverage_status`, `material_unknowns` |
| `deployment_risk_evidence` | `Risk` verdict, `deployment_confidence`, evidence gaps |
| `freshness_snapshot` | Head identity, CI status, and approval state as read in this phase, for report.md's final freshness re-check |

Every evidence source's own provenance (`caller`, `model_knowledge`, `repository`,
`authoritative_host`, or `trusted_runtime`) is preserved alongside its value — Aggregate applies
the ladder in [reference/evidence-authority-policy.md](../reference/evidence-authority-policy.md),
it is not re-derived here.
