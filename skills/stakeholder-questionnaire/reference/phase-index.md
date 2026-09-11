# Phase index

Read one `workflow/` file per active phase; do not bulk-load the workflow or references.

| Step | Read now | Produces |
|------|----------|-----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `decision_context`, `recipient` |
| **Draft** | [workflow/draft.md](../workflow/draft.md) | `questions` |
| **Report** | [workflow/report.md](../workflow/report.md) | `STAKEHOLDER_QUESTIONNAIRE.md`, `stakeholder_questionnaire` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller situation | Behavior |
|-------------------|----------|
| A decision and a specific recipient are named | Inputs → Draft → Report |
| No decision context named | Inputs HARD STOP — ask; no Draft phase |
| No specific recipient named | Inputs HARD STOP — ask; no Draft phase |
| A question already answered in the repository | Draft notes it, does not ask it in the questionnaire |
| Caller asks the skill to send/post/deliver the questionnaire | Reject — report-only; this skill never delivers, only drafts |
