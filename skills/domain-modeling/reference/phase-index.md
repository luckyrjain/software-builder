# Phase index

Read one `workflow/` file per active phase; do not bulk-load the workflow or references.

| Step | Read now | Produces |
|------|----------|-----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `domain_focus`, `existing_context`, `change_goal` |
| **Challenge** | [workflow/challenge.md](../workflow/challenge.md) | `terminology_findings`, `scenario_findings`, `code_cross_reference`, `adr_readiness` |
| **Report** | [workflow/report.md](../workflow/report.md) | `DOMAIN_MODEL_UPDATE.md`, `domain_model_update` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller situation | Behavior |
|-------------------|----------|
| A term/decision/scenario is under discussion | Inputs → Challenge → Report |
| No term, relationship, or decision named | Inputs HARD STOP — ask; no Challenge phase |
| Decision point exists (choice + rejected alternative + consequence) | Challenge sets `adr_readiness: true`; Report drafts an ADR |
| No decision point, only a definition | Challenge sets `adr_readiness: false`; Report states so, no fabricated ADR |
| Scope becomes a full unfamiliar-domain reconstruction, one module's contract, or an architecture-wide verdict | Offer the one applicable escalation; do not invoke it |
