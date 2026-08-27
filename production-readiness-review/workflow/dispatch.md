---
workflow_version: 1.0
phase: dispatch
produces:
  - dimension_evidence
  - dispatch_log
consumes:
  - assessment_target
  - criticality
  - ci_evidence
  - scm_policy_evidence
  - build_provenance_evidence
  - change_impact_evidence
  - deployment_risk_evidence
---

# Dispatch — pr-review always, specialists per change-impact evidence

## 1. pr-review — always invoked, posting forbidden

Invoke **pr-review** with explicit typed fields — the same retrospective-audit pattern
`release-readiness-checker` uses over pr-review's own real posting-gate policy, not a conversational
exchange:

- `merge_request_iid`, `project` (or the equivalent PR identifier) — exact scope
- `review_mode: retrospective`, `audit_type: retrospective`
- `expected_head_sha`: the exact `head_sha` resolved in Inputs
- `posting_policy: forbidden`

Every other ask-point pr-review may still hit (baseline staleness, pagination cap, Jira/Slack
write-back offers) is answered per pr-gatekeeper's own enumerated policy, reused verbatim — decline
every write-back offer. Nothing is ever posted, regardless of which posting mode pr-review's own
Phase 0 detects. Full protocol: [reference/gate-policy.md § pr-review](../reference/gate-policy.md#pr-review-always-invoked-posting-held).

## 2. Determine applicable specialists from change-impact evidence

For each specialist below, dispatch it **only** when `change_impact_evidence.change_classes` or
`impacted_*` fields name the corresponding surface. A specialist with no triggering change class is
recorded `NOT_APPLICABLE`, not `UNKNOWN` and not silently omitted from the report.

| Specialist | Triggering change-impact signal |
|---|---|
| security-review | Auth/authz, input handling, secrets, cryptography, or tenant-isolation surface touched |
| observability-review | Metrics/logs/tracing/dashboards/alerts/SLO definitions touched, or a service with none previously covered |
| resilience-review | Timeout/retry/circuit-breaker/queue/dependency-path behavior touched |
| api-design-review | A public API contract (REST/GraphQL/proto/event schema) touched |
| database-review | Schema, migration, or query surface touched |
| performance-review | Hot-path code, query, or service content touched |
| capacity-planner | A demand-affecting change (new traffic path, scaling config) with forecast-relevant data available |
| dependency-upgrade-review | A dependency version bump present in the diff |

`change_impact_evidence.coverage_status` not `COMPLETE` is a `change_impact` dimension gap recorded
in Aggregate, and per [collect-evidence.md § 4](collect-evidence.md), it also means "no triggering
signal found" for a given specialist is not itself proof that specialist doesn't apply — absence of
a signal in an admittedly-incomplete scan is "cannot determine," never "assume inapplicable." So
with incomplete coverage: dispatch a specialist whose signal IS present (or whose applicability the
caller's `assessment_context` already asserts) as usual; for every other specialist, record
`UNKNOWN` (not `NOT_APPLICABLE`) unless its own mandatory input can't be assembled either, which is
`UNKNOWN` regardless. `NOT_APPLICABLE` for "no triggering signal" is reserved for the case where
`coverage_status` **is** `COMPLETE` and the scan can be trusted to have found every applicable
surface.

## 3. Assemble each applicable specialist's mandatory input — or dispatch nothing

Per [reference/child-input-map.md](../reference/child-input-map.md), assemble every mandatory input
field for each applicable specialist from the evidence already collected (the diff, the repository, or
an explicit caller-supplied field). **Never dispatch a specialist with a knowingly-incomplete mandatory
input.** When a mandatory field cannot be assembled, do not invoke that specialist at all — record its
dimension `UNKNOWN` directly with the missing-field reason in `dispatch_log`, per
[reference/gate-policy.md § Never dispatch incomplete](../reference/gate-policy.md#never-dispatch-a-specialist-with-a-knowingly-incomplete-mandatory-input).

Invoke each applicable, fully-assembled specialist with its own typed `assessment_context`
(`assessment_target`, `inputs`, `input_provenance`, `evidence_refs`, `unresolved`) — never a bare
conversational phrase.

## 4. No merge/deploy/rollback authority; BLOCKED propagation

No invocation in this phase grants any child merge, deploy, or rollback authority — every child stays
within its own read-only contract. If a dispatched child would otherwise render an interactive
question to the caller, it returns `BLOCKED` to this skill instead; treat that as the dimension's
outcome (`UNKNOWN`, with the block reason retained) rather than surfacing the prompt mid-aggregation.
See [reference/gate-policy.md](../reference/gate-policy.md).

## Required outputs

| Output | Required fields |
|--------|------------------|
| `dimension_evidence` | Per-dimension: pr-review findings; each specialist's own report or `NOT_APPLICABLE`/`UNKNOWN` with reason |
| `dispatch_log` | Which specialists were dispatched, which were skipped as `NOT_APPLICABLE`, which were skipped as `UNKNOWN` for an incomplete mandatory input, and any child `BLOCKED` outcome |
