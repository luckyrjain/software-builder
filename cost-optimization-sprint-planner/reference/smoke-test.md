# Smoke test — expected minimal output

Run after install or any edit to this skill. Use a `sweep_scope.deployments` list of ≥2 real deployments
(see [k8s-overprovisioning-datadog/reference/smoke-test.md](../../k8s-overprovisioning-datadog/reference/smoke-test.md)
to confirm k8s-overprovisioning-datadog itself is configured first), at least one with a `SQUAD_MAP.md`
`Datadog service` match and one without (to exercise both join paths), plus a `cost_rate`.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> `sweep_scope: {env: production, deployments: [<svc1>, <svc2>]}`, `cost_rate: {provider: aws,
> dollars_per_core_month: 24.00, dollars_per_gib_month: 3.50, cost_basis: "<your provider/region/node
> type>"}`

## Expected first output

The resolved sweep config announced (selection mode, candidate count, cost basis) before the first
k8s-overprovisioning-datadog invocation starts.

## A correct minimal output contains

1. **Every candidate deployment appears** in either a ranked squad section or the Sweep gaps section —
   never dropped.
2. **A deployment with no `SQUAD_MAP.md`/`ownership.datadog.service_aliases` match** produces
   `squad: UNKNOWN` — squad-map is never invoked to fill it.
3. **`COST_OPTIMIZATION_SPRINT_REPORT.md` and `cost_optimization_sprint_rollup.json` both produced**, per
   [reference/report-format.md](report-format.md).
4. **The cost-rate confirmation is asked at most once**, before the first deployment is assessed — never
   re-asked per deployment.

## Pass criteria

- k8s-overprovisioning-datadog's own read-only behavior is unchanged — this skill never applies a
  recommended cut.
- A deployment that hits `insufficient_metrics` doesn't abort the sweep — the next deployment still runs.
- Ranking within each squad section is by `monthly_savings_total` descending.

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| A deployment resolves to `insufficient_metrics` | Recorded in Sweep gaps, sweep continues to the next deployment |
| CCM has real cost data for a deployment | CCM wins for that deployment; `cost_rate` fallback not used |
| `sweep_scope.namespace_prefilter` set with no matching namespaces | Empty candidate list, `stopped_reason: SCOPE_EXHAUSTED`, report still produced (empty, honestly) |
| VPA active, recommendation unconfirmed on a deployment | That deployment still produces a real `decision_graph` with the affected dimension `DEFERRED` — not a sweep gap |
| Datadog authentication fails during an explicit-deployment assessment, but Kubernetes MCP supplies sufficient evidence | Source-scoped failure is retained in the wrapped graph; assessment and sweep continue |
| Datadog authentication fails during direct namespace pre-filter discovery | Sweep stops before the loop with `stopped_reason: AUTH_FAILURE`; report suggests `ddsetup`/`ddconfig` or an explicit deployments list |
| All viable sources for required assessment evidence are unauthorized | Sweep stops immediately with `stopped_reason: AUTH_FAILURE`; no further candidates attempted and the report identifies every attempted source |
| `cost_rate.provider != aws` | CCM never queried for the whole sweep; every deployment falls straight through to the pre-resolved `cost_rate` fallback |
