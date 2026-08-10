---
workflow_version: 1.1
phase: "0b"
produces: {from_time: string, analysis_from_time: string, to_time: string, service: string, symptom: string}
consumes:
  required: {jira_key: string, mcp_profile: string}
  optional: {}
  conditional: {}
---

# Phase 0b — Anchor the window from Jira

**Read this file** only when `jira_key` is given. Run **before** any observability query so the window is correct.

1. `getJiraIssue` for the key (after resolving `cloudId` via `getAccessibleAtlassianResources`).
2. Parse description and comments for the reported incident start/end time and affected service. **Warning:** the ticket `created` field is when the ticket was opened — typically 15–60 minutes after the incident actually started. Never use `created` as `from_time` directly; use it only as a fallback upper bound if no start time appears in the description or comments.
3. Set / refine `from_time`, `to_time`, `service`, and `symptom` from the ticket, then proceed to
   Phase 1. If the ticket lacks a clear window, ask the user before guessing — minimum information needed: **(1)** approximate incident start time (UTC), **(2)** affected service name, **(3)** symptom observed (error type or user impact description).

4. **Backstroke 15 minutes:** after anchoring `from_time`, automatically subtract 15 minutes:

   ```
   analysis_from_time = from_time − 15m
   ```

   Use `analysis_from_time` for **all Phase 1 observability queries**. Report both values clearly:

   > **Window:** Incident start (reported): `<from_time>` | Query start (backstroke): `<analysis_from_time>` | End: `<to_time>`

   **Rationale:** on-call response lag and human reporting delay mean the reporter's first timestamp
   is often 10–20 minutes after the first abnormal signal. The backstroke exposes the pre-ticket
   degradation period where the earliest root-cause signal typically lives.

   Do not expand `to_time` — the backstroke applies to the start only.

**Timezone (same rule as [inputs.md](inputs.md)):** when parsing timestamps from the ticket description
or comments, if a timestamp has **no timezone suffix** (no `Z` or `±HH:MM`), ask the user to confirm
**UTC** or their **local timezone** before anchoring the window — do not assume UTC silently. Jira
timestamps are often in the reporter's local time.
