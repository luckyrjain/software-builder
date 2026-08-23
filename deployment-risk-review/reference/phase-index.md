# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `change_description`, `affected_services`, `migration_steps`, `rollback_plan`, `traffic_pattern` |
| **Analyze** | [workflow/analyze.md](../workflow/analyze.md) | `blast_radius_finding`, `migration_risk_finding`, `rollback_complexity_finding`, `dependency_risk_finding`, `traffic_risk_finding` |
| **Report** | [workflow/report.md](../workflow/report.md) | `DEPLOYMENT_RISK_REPORT.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| Full change description, migration steps, rollback plan, traffic pattern | Inputs → Analyze → Report → full verdict |
| `change_description` missing | Inputs HARD STOP — ask, no Analyze |
| `rollback_plan`/`migration_steps`/`traffic_pattern` missing or not discoverable in the repository | Analyze records the gap → Report surfaces it as an explicit Unknown in the relevant section, not a silent Low |
