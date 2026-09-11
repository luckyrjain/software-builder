# Phase index

Read one `workflow/` file per active phase; do not bulk-load the workflow or references.

| Step | Read now | Produces |
|------|----------|-----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `initiative_description` |
| **Decompose** | [workflow/decompose.md](../workflow/decompose.md) | `decision_tickets`, `sequencing` |
| **Report** | [workflow/report.md](../workflow/report.md) | `INITIATIVE_MAP.md`, `initiative_map` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller situation | Behavior |
|-------------------|----------|
| A large, foggy effort with real sub-questions is named | Inputs → Decompose → Report |
| No `initiative_description` named | Inputs HARD STOP — ask; no Decompose phase |
| Description is already one bounded, scoped idea | Inputs rejects mapping; points at `prd-architect` directly |
| A ticket has no clear ready-for skill yet | Decompose leaves it unresolved; Report marks it unresolved, not force-fit |
| A ticket is one unresolved decision, PRD-ready, or design-ready | Report names the applicable downstream skill (`engineering-decision-discovery`, `prd-architect`, `implementation-planner`) per ticket |
| Caller asks the skill to write a ticket, PRD, or plan directly | Reject the direct write; the map only recommends a separate, explicitly authorized invocation |
