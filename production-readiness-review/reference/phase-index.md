# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `assessment_target`, `criticality`, `source_revision`, `build_provenance_ref` |
| **Collect evidence** | [workflow/collect-evidence.md](../workflow/collect-evidence.md) | `ci_evidence`, `scm_policy_evidence`, `build_provenance_evidence`, `change_impact_evidence`, `deployment_risk_evidence` |
| **Dispatch** | [workflow/dispatch.md](../workflow/dispatch.md) | `dimension_evidence`, `dispatch_log` |
| **Aggregate** | [workflow/aggregate.md](../workflow/aggregate.md) | `dimension_statuses`, `operational_evidence`, `verdict` |
| **Report** | [workflow/report.md](../workflow/report.md) | `production_readiness_report` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `assessment_target` with a clean, low-risk diff | Inputs → Collect evidence → Dispatch (pr-review only; every specialist `NOT_APPLICABLE`) → Aggregate → Report → `READY` |
| A diff touching a schema/API/security/dependency surface | Dispatch invokes the matching specialist(s) per [child-input-map.md](child-input-map.md) |
| A specialist's mandatory input can't be fully assembled | Dispatch records that dimension `UNKNOWN` — never invoked with a partial input |
| `host.ci.status` or another `host.*` capability unavailable | Its dimension is `UNKNOWN` in Aggregate — never assumed `PASS` |
| `criticality` is `tier0`/`tier1`/`unknown` with only caller-asserted operational evidence | Aggregate records the affected operational gate `UNKNOWN`, not `PASS` |
| `assessment_target` missing | Inputs HARD STOP — ask, no Collect evidence |
