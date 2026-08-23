# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `debt_items`, `repo_context`, `effort_unit` |
| **Analyze** | [workflow/analyze.md](../workflow/analyze.md) | per-item `business_impact`, `engineering_drag`, `operational_risk`, `effort`, `priority_score` |
| **Report** | [workflow/report.md](../workflow/report.md) | `TECH_DEBT_ASSESSMENT.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| A backlog of debt items with descriptions and affected areas | Inputs → Analyze → Report → full ranked verdict list |
| `debt_items` absent or empty | Inputs HARD STOP — ask, no Analyze |
| An item too vague to score one or more dimensions | Analyze records the gap → Report surfaces it as an explicit "Unknown — insufficient evidence" row, not a silent `Won't-fix now` |
