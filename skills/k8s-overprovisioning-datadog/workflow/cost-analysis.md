---
workflow_version: 3.5
phase: cost
produces: {cost_estimate: object}
consumes:
  required: {validated_decisions: list, cost_gate: boolean}
  optional: {}
  conditional: {}
---

# Cost analysis

Run **only after** [validate.md](validate.md) cost gate passes.

## When to skip

Report `cost_skipped: <reason>` when:

- Any Critical `STOP_REASON`
- `optimization_not_feasible`
- User intent is replicas-only or throttle-only without cost ask
- No ALLOW/DEFER dimension with savings potential

## Steps

1. Search `Kubernetes Cost by Service` dashboard (if dashboards collected), then CCM `aws.cost.amortized.*` with `use_cloud_cost: true`, sum, 30d ([queries.md](../queries.md#cost-metrics)).
2. Derive `$/core`, `$/GiB` — [cost-estimation.md](../cost-estimation.md#calibrating-core-and-gib). No ×730.
3. CCM empty → **resource-only**; no fallback $ without user confirmation.
4. Savings + node packing — [cost-estimation.md](../cost-estimation.md#node-packing). One combined delta for request + replica changes.
5. Cluster Autoscaler activity — [queries.md](../queries.md#node-packing-cost-savings-sanity-check).

Reserved reduction ≠ cloud savings without node removal.
