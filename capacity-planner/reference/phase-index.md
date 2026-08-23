# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `demand_data`, `forecast_horizon`, `current_baseline`, `growth_rate`, `peak_avg_ratio` |
| **Analyze** | [workflow/analyze.md](../workflow/analyze.md) | RPS/concurrency targets, CPU/memory sizing, DB load, queue throughput, storage growth, replica requirements, assumptions, evidence gaps |
| **Report** | [workflow/report.md](../workflow/report.md) | `CAPACITY_PLAN.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `demand_data` + `forecast_horizon`, clean trend, `current_baseline` supplied | Inputs → Analyze → Report → full Headroom verdict |
| `demand_data` or `forecast_horizon` missing | Inputs HARD STOP — ask, no Analyze |
| `demand_data` has no derivable trend and no `growth_rate` supplied | Analyze records the gap → Report surfaces `Unknown — insufficient historical data`, not a silent `Sufficient` |
| A specific check can't be completed (e.g. no DB or queue numbers supplied) | Analyze records that section's gap → Report surfaces it as an explicit Unknown for that section, not folded into the overall verdict silently |
