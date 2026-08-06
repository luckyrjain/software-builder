---
workflow_version: 1.0
phase: run-sweep
produces:
  - cost_optimization_sprint_report
  - cost_optimization_sprint_rollup
consumes:
  - sweep_scope
  - cost_rate
  - max_deployments_per_run
  - deadline
  - session_token_budget
---

# Run sweep — pre-filter, loop, join, rank, render

## 1. Build the candidate deployment list

Per [reference/sweep-policy.md § 2](../reference/sweep-policy.md#2-candidate-deployment-list) — either
`sweep_scope.deployments` verbatim, or the namespace/deployment waste-ranking queries run directly against
Datadog MCP (never a delegated k8s-overprovisioning-datadog invocation asked to rank-and-stop), capped by
`max_deployments_per_run`.

## 2. Loop k8s-overprovisioning-datadog once per candidate, sequentially

Per [reference/sweep-policy.md § 3–4](../reference/sweep-policy.md#3-invoking-k8s-overprovisioning-datadog-one-deployment-per-invocation-sequential):

1. Invoke k8s-overprovisioning-datadog with the deployment name + `sweep_scope.env` (+ namespace, when
   known from the pre-filter).
2. Answer every live gate that invocation hits per [reference/gate-policy.md](../reference/gate-policy.md)
   — the cost-rate gate is **never** re-asked here, it was already resolved once before this loop started
   (§ 0 below).
3. Record the outcome (`ASSESSED` / `INSUFFICIENT_METRICS` / `AMBIGUOUS_UNRESOLVED`) in `sweep_run.deployments`
   per the state shape in [reference/sweep-policy.md § 1](../reference/sweep-policy.md#1-session-level-state-new-layered-outside-k8s-overprovisioning-datadog-which-has-none).
4. Check [reference/sweep-policy.md § 5](../reference/sweep-policy.md#5-session-level-stop-conditions-circuit-breakers)'s
   stop conditions **between** deployments, never mid-assessment — an in-flight assessment always
   finishes.

### 0. Cost-rate resolution (runs once, before step 1's loop starts)

`cost_rate` (from [workflow/inputs.md](inputs.md)) is the pre-confirmed fallback for every deployment in
this sweep — resolved once here, supplied to every invocation in step 2, never re-derived. See
[reference/gate-policy.md § Cost-rate gate](../reference/gate-policy.md#cost-rate-gate-resolved-once-sweep-wide-before-the-loop-starts).

## 3. Join each `decision_graph` into an `org_rollup_item`

Per [org-rollup-schema.md § 4](../../docs/skill-framework/shared/org-rollup-schema.md#4-adapters-per-source-skill)'s
`k8s_waste` adapter — `service` from the graph's `metadata` block, `status`/`priority` from
`recommendations[]`, `value` preferring `appendix.cost` when present (never guaranteed — see
[design spec § Non-goals](../../docs/superpowers/specs/2026-08-05-cost-optimization-sprint-planner-design.md#non-goals-explicitly-out-of-scope)),
falling back to `cost-estimation.md`'s formulas applied against `observations`/`recommendations` directly
when `appendix.cost` is absent. Squad match against `SQUAD_MAP.md`'s `Datadog service` column first,
falling back to `ownership.datadog.service_aliases` (squad-map's own existing config field) when the
graph's `metadata.service` doesn't match verbatim — the real, documented `metadata.service` vs.
`scope`'s `kube_deployment:` tag mismatch org-rollup-schema.md itself flags.

## 4. Rank and group

Per squad: sort by `value.monthly_savings_total` descending. `squad: UNKNOWN` items form their own group,
always rendered last — never silently merged into a named squad's section. A deployment whose
`INSUFFICIENT_METRICS`/`AMBIGUOUS_UNRESOLVED` outcome (§ 2) produced no `decision_graph` at all is never
included as a rollup item — it's a sweep gap, rendered separately (see
[reference/report-format.md](../reference/report-format.md)), not a `$0`-savings row.

## 5. Render `COST_OPTIMIZATION_SPRINT_REPORT.md`

Per [reference/report-format.md](../reference/report-format.md). Every candidate deployment appears —
either as a ranked rollup item or a sweep-gap entry, never silently dropped. Always produced regardless of
`stopped_reason` per [reference/sweep-policy.md § 6](../reference/sweep-policy.md#6-report-always-produced).

## Required outputs

| Output | Location | Required fields |
|--------|----------|-----------------|
| Cost optimization sprint report | `COST_OPTIMIZATION_SPRINT_REPORT.md` | Per-squad ranked sections, UNKNOWN-squad group, sweep gaps, sweep-config summary (which selection mode ran, `stopped_reason`) |
| Machine-readable rollup | `cost_optimization_sprint_rollup.json` | Full `org_rollup_item` list per org-rollup-schema.md |
