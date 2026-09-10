# Phase index

Read one `workflow/` file per active phase; do not bulk-load the workflow or references.

| Step | Read now | Produces |
|------|----------|-----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `issues` |
| **Classify** | [workflow/classify.md](../workflow/classify.md) | `issues_classified` |
| **Report** | [workflow/report.md](../workflow/report.md) | `ISSUE_TRIAGE_REPORT.md`, `issue_triage_report` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller situation | Behavior |
|-------------------|----------|
| One or more raw issues are supplied | Inputs → Classify → Report |
| No raw issue text named | Inputs HARD STOP — ask; no Classify phase |
| An issue describes active, ongoing user-facing impact right now | Classify flags it; Report names it under "Incident-shaped issues" and offers `incident-rca` |
| A duplicate claim has no matching symptom/stack-trace/repro evidence | Classify records `duplicate_of: none found`; Report never fills it with a proximity guess |
| Scope becomes a live paging-webhook incident, an already-scoped tracker query, a PRD, a debt-ranking pass, or an ownership lookup | Offer the one applicable escalation; do not invoke it |
