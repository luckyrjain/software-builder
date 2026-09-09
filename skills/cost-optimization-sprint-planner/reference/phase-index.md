# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `sweep_scope`, `cost_rate`, `max_deployments_per_run`, `deadline`, `session_token_budget` |
| **Run sweep** | [workflow/run-sweep.md](../workflow/run-sweep.md) | `COST_OPTIMIZATION_SPRINT_REPORT.md`, `cost_optimization_sprint_rollup.json` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `sweep_scope.deployments: [...]`, `cost_rate: {...}` | Inputs → Run sweep (loop k8s-overprovisioning-datadog per deployment per gate-policy.md, join, rank, render) → report + rollup JSON |
| `sweep_scope.namespace_prefilter: {...}`, `cost_rate: {...}` | Inputs → Run sweep § 1 runs the namespace/deployment ranking queries first, then loops the resulting candidate list |
| A deployment hits `insufficient_metrics` | Run sweep § 2 records it as a sweep gap — not a stop for the whole sweep |
| `sweep_scope` missing `env`, missing both `deployments` and `namespace_prefilter`, or `namespace_prefilter` set (and `deployments` absent) but missing `top_n_namespaces`/`top_n_deployments_per_namespace`; or `cost_rate` absent/incomplete (missing `provider`, `dollars_per_core_month`, or `dollars_per_gib_month`) | Inputs HARD STOP — ask, no Run sweep |
