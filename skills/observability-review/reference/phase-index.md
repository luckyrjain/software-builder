# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `service_name`, `observability_material`, `critical_path`, `correlation_id_field` |
| **Analyze** | [workflow/analyze.md](../workflow/analyze.md) | Per-category coverage findings (Metrics, Logs, Tracing, Dashboards, Alerts, SLOs, Correlation IDs) |
| **Report** | [workflow/report.md](../workflow/report.md) | `OBSERVABILITY_REVIEW_REPORT.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `service_name` + `observability_material` covering all six categories | Inputs → Analyze → Report → full verdict |
| `service_name` or `observability_material` missing | Inputs HARD STOP — ask, no Analyze |
| `observability_material` covers only some categories (e.g. no alert rules supplied) | Analyze records the uncovered category as a gap in evidence → Report surfaces it as an explicit Unknown, not a silent pass |
