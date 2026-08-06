---
workflow_version: 1.1
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
  - output_dir
  - squad_map_config_path
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
   known from the pre-filter), **explicitly requesting the JSON file artifact** per
   [render/json.md](../../k8s-overprovisioning-datadog/render/json.md) ("optionally write to
   `decision-graph.json` if user requests a file artifact"). k8s-overprovisioning-datadog's own renderer
   only documents that one hardcoded filename — it has no parameter for a caller-specified path or name —
   so **this skill's own workflow, immediately after that invocation returns**, moves/renames the
   resulting `decision-graph.json` to `<output_dir>/decision-graph-<deployment>.json` (from
   [workflow/inputs.md](inputs.md)'s `output_dir`) before starting the next candidate. This is a plain
   file-move step this skill performs itself, not a capability requested of
   k8s-overprovisioning-datadog — it never needs to know a sweep is even running. Skip this step entirely
   for an outcome that never reaches COST/RENDER (`INSUFFICIENT_METRICS`/`AMBIGUOUS_UNRESOLVED`/
   `AUTH_FAILURE` — no file to move).
2. Answer every live gate that invocation hits per [reference/gate-policy.md](../reference/gate-policy.md)
   — the cost-rate gate is **never** re-asked here, it was already resolved once before this loop started
   (§ 0 below); a `STOP_REASON: auth_failure` is **not** answered per-deployment — it stops the whole
   sweep, see [reference/gate-policy.md § Sweep-wide stop](../reference/gate-policy.md#sweep-wide-stop-not-per-deployment-isolation-the-auth-failure-gate).
3. Record the outcome (`ASSESSED` / `INSUFFICIENT_METRICS` / `AMBIGUOUS_UNRESOLVED` / `AUTH_FAILURE`) and,
   when `ASSESSED`, the `decision-graph-<deployment>.json` path as `decision_graph_ref`, in
   `sweep_run.deployments` per the state shape in
   [reference/sweep-policy.md § 1](../reference/sweep-policy.md#1-session-level-state-new-layered-outside-k8s-overprovisioning-datadog-which-has-none).
4. Check [reference/sweep-policy.md § 5](../reference/sweep-policy.md#5-session-level-stop-conditions-circuit-breakers)'s
   stop conditions **between** deployments, never mid-assessment — an in-flight assessment always
   finishes. `AUTH_FAILURE` stops immediately, before starting the next candidate.

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
when `appendix.cost` is absent.

**Squad match, in order:**

1. `SQUAD_MAP.md`'s `Datadog service` column, matched against the graph's `metadata.service` verbatim.
   `squad_confidence` = that row's own `Confidence` column value, **normalized** — an empty or
   whitespace-only cell is `UNKNOWN` directly; otherwise take the leading token, uppercased
   (`HIGH`/`MEDIUM`/`LOW`), falling back to `UNKNOWN` for anything else. Never copy the cell verbatim: a
   real `SQUAD_MAP.md` Confidence cell can carry an annotation (e.g. `MEDIUM
   ⚠️` on a Conflicts-adjacent row, per
   [squad-map/reference/gold-squad-map-excerpt.md](../../squad-map/reference/gold-squad-map-excerpt.md)),
   which would otherwise violate `org-rollup-schema.md`'s own `HIGH | MEDIUM | LOW | UNKNOWN` enum — the
   exact bug migration-program-manager's own `normalize_confidence()` was built to close on this same
   schema; reuse that fix's shape here rather than re-discovering it.
2. **Else**, when `squad_map_config_path` is supplied (see [workflow/inputs.md](inputs.md)): a **reverse**
   lookup against that config's `ownership.datadog.service_aliases` map
   ([squad-map/reference/config-schema.md](../../squad-map/reference/config-schema.md) —
   `<repo-name>: <service-name>`) — search the map's **values** for one matching `metadata.service`, take
   the corresponding **key** (the repo name), then re-join that repo name against `SQUAD_MAP.md`'s `Repo`
   column. This is the real, documented `metadata.service` vs. `scope`'s `kube_deployment:` tag mismatch
   org-rollup-schema.md itself flags — the alias map exists specifically to bridge it, but only in this
   reverse direction, since `service_aliases` is authored as repo→service (squad-map's own resolution
   direction when it first builds `SQUAD_MAP.md`), not service→repo. **If more than one key maps to the
   same service-name value** (plausible in a monorepo-heavy org — `config-schema.md`'s own
   `<repo-name>/<subdir>` keys can collide on the same Datadog service name), the match is ambiguous —
   treat it the same as no match at all (fall through to step 3) rather than silently picking whichever
   key the search hits first. `squad_confidence` for a genuine (non-ambiguous) reverse-lookup match is
   **MEDIUM**, never HIGH — it's an indirect match through a config file, not a direct `SQUAD_MAP.md` row.
3. **Else** `squad: UNKNOWN`, `squad_confidence: UNKNOWN` — never guessed, never silently dropped.

A `squad_confidence` of `LOW` or `UNKNOWN` is surfaced in the report's Notes section (see
[reference/report-format.md](../reference/report-format.md)), not just carried silently in the JSON.

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
