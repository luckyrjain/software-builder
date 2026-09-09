# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `architecture_decision_or_prd`, `existing_system_context` |
| **Analyze** | [workflow/analyze.md](../workflow/analyze.md) | `components`, `apis`, `events`, `data_model`, `state_machines`, `consistency`, `retries`, `capacity`, `failure_strategy`, `observability`, `rollout_plan` |
| **Report** | [workflow/report.md](../workflow/report.md) | `SYSTEM_DESIGN_SPEC.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| An architecture decision or PRD with enough detail to design against | Inputs → Analyze → Report → full Readiness verdict |
| No architecture decision or PRD text | Inputs HARD STOP — ask, no Analyze |
| A design aspect can't be derived (e.g. no load data for capacity, no existing-system context for a migration order) | Analyze records the gap → Report surfaces it as an explicit "Open question," not a silent Ready |
