# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `event_type`, `service`, `triggered_at`, `resolved_at`, `alert_title`, `alert_id`, `severity`, `workspace_root` |
| **Triage** (`event_type: page_triggered`) | [workflow/triage.md](../workflow/triage.md) | `triage_doc` |
| **Postmortem** (`event_type: incident_resolved`) | [workflow/postmortem.md](../workflow/postmortem.md) | `postmortem_draft` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Webhook event | Phases |
|-----------------|--------|
| `page_triggered` | Inputs → Triage → routed triage doc |
| `incident_resolved` | Inputs → Postmortem → routed postmortem draft |
| Any other paging event (ack, escalate, snooze) | Inputs short-circuit — no-op |
| Missing `service` or `triggered_at` (or `resolved_at` on a resolved event) | Inputs HARD STOP — log and exit |
