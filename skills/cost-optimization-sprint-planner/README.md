# cost-optimization-sprint-planner

**Org-wide cost/waste ranking.** Runs **k8s-overprovisioning-datadog** once per deployment across a
`sweep_scope`, joins each result against **squad-map**'s `SQUAD_MAP.md`, and ranks the fleet by
`monthly_savings_total` descending, grouped by squad — an org-wide "where's the money" view
k8s-overprovisioning-datadog has no mode to produce on its own, since it only ever assesses one
deployment per conversational run.

## What it does

1. **Optionally pre-filters** — when `sweep_scope.namespace_prefilter` is set (instead of an explicit
   `deployments` list), runs the namespace/deployment waste-ranking queries directly against Datadog MCP
   to produce a bounded candidate list before spending a full assessment on every deployment in an env.
2. **Loops k8s-overprovisioning-datadog once per candidate, sequentially** — every live gate it might hit
   (ambiguous name, insufficient metrics, VPA-active-unconfirmed, cost-rate confirmation, CCM-empty
   fallback) is answered with its own documented, non-guessing fallback, never an invented one.
   Source-scoped failures do not abort the sweep; authentication failure across all viable sources does.
3. **Resolves the cost rate once, sweep-wide** — never re-asked per deployment, the single biggest thing
   standing between this skill and running unattended over many deployments.
4. **Joins each `decision_graph` to a squad** via `SQUAD_MAP.md`'s `Datadog service` column (falling back
   to `ownership.datadog.service_aliases` — squad-map's own existing alias mechanism, not a new one).
5. **Ranks and groups by squad** — sorted by `monthly_savings_total` descending; `UNKNOWN` squad last.
6. **Writes `COST_OPTIMIZATION_SPRINT_REPORT.md`** (human-readable) and
   **`cost_optimization_sprint_rollup.json`** (machine-readable —
   [weekly-squad-digest](../weekly-squad-digest/README.md) reuses this directly).

## When to use

| Use cost-optimization-sprint-planner | Use instead |
|-----------------------------------------|--------------|
| Org-wide cost/waste ranking across many deployments | One deployment's own rightsizing question → **k8s-overprovisioning-datadog** directly |
| "Where should we focus a cost-optimization sprint?" | Squad/repo ownership lookup, no cost angle → **squad-map** directly |

## Invocation example

```
sweep_scope: {env: production, namespace_prefilter: {top_n_namespaces: 5, top_n_deployments_per_namespace: 5}}
cost_rate: {provider: aws, dollars_per_core_month: 24.00, dollars_per_gib_month: 3.50, cost_basis: "AWS us-east-1 m6i, on-demand"}
```

## What you get

`COST_OPTIMIZATION_SPRINT_REPORT.md` + `cost_optimization_sprint_rollup.json` — format spec:
[reference/report-format.md](reference/report-format.md).

## Install

```bash
cd software-builder
make install-cost-optimization-sprint-planner
```

Restart Cursor. Requires **k8s-overprovisioning-datadog** and **squad-map** installed too (the make
target chains both automatically). Per-deployment assessments inherit Kubernetes MCP or Datadog routing
from the wrapped skill. Datadog is directly required only when using `namespace_prefilter`; explicit
deployment lists do not add that requirement.

## Related skills

- **k8s-overprovisioning-datadog** — produces the per-deployment `decision_graph` this skill loops to
  collect; never modified by this skill
- **squad-map** — produces `SQUAD_MAP.md`; this skill only reads it for the join, never invokes squad-map
- **backlog-runner** — the pattern this skill's own sweep loop is modeled on (session-level state layered
  outside the wrapped skill's own, per-item failure isolation, batch-level stop conditions)

Agent instructions: [SKILL.md](SKILL.md).
