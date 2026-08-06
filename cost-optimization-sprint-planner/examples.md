# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|--------------|----------|
| 1 | `sweep_scope: {env: production, deployments: [svc-a, svc-b]}`, `cost_rate: {...}` | Inputs → Run sweep → both deployments assessed, joined, ranked → `COST_OPTIMIZATION_SPRINT_REPORT.md` + `cost_optimization_sprint_rollup.json` |
| 2 | `sweep_scope: {env: production, namespace_prefilter: {top_n_namespaces: 5, top_n_deployments_per_namespace: 5}}`, `cost_rate: {...}` | Inputs → Run sweep § 1 runs the waste-ranking queries first, produces a ≤25-deployment candidate list, then loops it |
| 3 | A deployment resolves to `insufficient_metrics` | Recorded as a sweep gap — not a stop, every other candidate still assessed |
| 4 | A deployment has no `SQUAD_MAP.md`/`ownership.datadog.service_aliases` match | Joins as `squad: UNKNOWN` — squad-map is never invoked to fill the gap |
| 5 | A deployment's graph has no `appendix.cost` block | Falls back to `cost-estimation.md`'s formulas applied against the graph's own `observations`/`recommendations`, using the once-resolved `cost_rate` |
| 6 | `sweep_scope` missing `env`, missing both `deployments` and `namespace_prefilter`, or `namespace_prefilter` set (and `deployments` absent) but missing `top_n_namespaces`/`top_n_deployments_per_namespace`; or `cost_rate` absent/incomplete (missing `provider`, `dollars_per_core_month`, or `dollars_per_gib_month`) | Inputs HARD STOP — ask, no Run sweep |
| 7 | Datadog auth fails during an explicit-deployment assessment, but Kubernetes MCP supplies sufficient evidence | Source-scoped failure is retained in the wrapped result; assessment and sweep continue |
| 8 | Datadog auth fails during direct namespace pre-filter discovery, or all viable sources for required assessment evidence are unauthorized | Sweep stops immediately with `stopped_reason: AUTH_FAILURE`; report identifies which scope failed |
| 9 | "Is checkout-api overprovisioned?" | **Wrong skill** → k8s-overprovisioning-datadog directly |
| 10 | "Who owns checkout-api?" | **Wrong skill** → squad-map directly |

---

### Scenario: Explicit deployment list — happy path

**Caller:** `sweep_scope: {env: production, deployments: [api-disbursement, api-payouts]}`,
`cost_rate: {provider: aws, dollars_per_core_month: 24.00, dollars_per_gib_month: 3.50, cost_basis: "AWS
us-east-1 m6i, on-demand"}`

**Agent:**

1. Inputs — sweep scope and cost rate parsed, resolved once
2. Run sweep § 1–2 — both deployments assessed via k8s-overprovisioning-datadog, sequentially
3. Run sweep § 3 — joined into `org_rollup_item`s via `SQUAD_MAP.md`
4. Run sweep § 4 — ranked by `monthly_savings_total` descending, grouped by squad
5. Run sweep § 5 — report + rollup JSON written

**Expected fragment:**

```
# Cost optimization sprint — 2026-08-05

**Sweep config:** `api-disbursement, api-payouts` · **Cost basis:** `AWS us-east-1 m6i, on-demand` ·
**Deployments assessed:** `2 of 2` · **Stopped reason:** `COMPLETED`

## disbursement

| Service | Monthly savings | Status | Priority | Confidence | Notes |
|---------|------------------|--------|----------|------------|-------|
| api-disbursement | $340.00 | READY | P1 | HIGH | estimated (fallback rate) |

## payouts

| Service | Monthly savings | Status | Priority | Confidence | Notes |
|---------|------------------|--------|----------|------------|-------|
| api-payouts | $0.00 | COMPLETED | — | HIGH | — |
```

---

### Scenario: Namespace pre-filter — bounded candidate list

**Caller:** `sweep_scope: {env: production, namespace_prefilter: {top_n_namespaces: 3,
top_n_deployments_per_namespace: 5}}`, `cost_rate: {...}`

**Agent:** Run sweep § 1 runs the namespace/deployment waste-ranking queries directly against Datadog MCP
(never a delegated k8s-overprovisioning-datadog invocation — that mode isn't documented as standalone,
see the [design spec](../docs/superpowers/specs/2026-08-05-cost-optimization-sprint-planner-design.md)),
producing at most 15 candidate deployments, then loops the sweep over exactly that list.

---

### Scenario: Cross-skill — wrong entry point

**Caller:** "Is checkout-api overprovisioned?"

**Agent:** Routes to **k8s-overprovisioning-datadog** directly — this is a single-deployment question,
not an org-wide sweep (see [SKILL.md](SKILL.md) § When to use / NOT to use).
