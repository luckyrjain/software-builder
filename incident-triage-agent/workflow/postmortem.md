---
workflow_version: 1.0
phase: postmortem
produces:
  - postmortem_draft
consumes:
  - service
  - triggered_at
  - resolved_at
  - alert_title
  - alert_id
  - workspace_root
---

# Postmortem — full investigation + pre-assigned follow-ups

**Goal:** Once an incident resolves, produce a drafted postmortem using incident-rca's own full report,
with follow-up owners pre-filled from squad-map. No new investigation, ownership, or action-item schema
here — see [SKILL.md](../SKILL.md) Non-goals and
[reference/unattended-gate-policy.md](../reference/unattended-gate-policy.md).

## Steps

1. **Construct the window** — `from_time = triggered_at`, `to_time = resolved_at`; if that span is
   < 30 minutes, extend `to_time` to `triggered_at + 30m` — per
   [reference/unattended-gate-policy.md § Per-mode window construction](../reference/unattended-gate-policy.md#per-mode-window-construction).
   Unlike triage mode, this is the **actual incident duration**, not a narrow snapshot.

2. **Invoke incident-rca**, following its own canonical invocation phrasing
   ([incident-rca/reference/smoke-test.md](../../incident-rca/reference/smoke-test.md)):
   `"RCA for <service> between <from_time> and <to_time> UTC — <alert_title/symptom, if present>
   (PagerDuty alert <alert_id>) — post-incident review, full investigation."` **No Jira-search or
   query-investigation skip here** — postmortem mode runs incident-rca at full thoroughness, unlike
   triage.

3. **Answer every gate incident-rca stops at**, per
   [reference/unattended-gate-policy.md § incident-rca gates](../reference/unattended-gate-policy.md#incident-rca-gates) —
   including gate #8 (Jira project keys unknown), which can genuinely fire in this mode since Phase 3
   Jira search runs here. Pre-configured `jira_project_keys` ([SETUP.md](../SETUP.md) § Config) avoids
   it; if it still fires, answer "skip Jira ticket search" and note the gap.

4. **Invoke squad-map** for `service`, same as triage mode Step 4 — proceed with owner `UNKNOWN` on a
   squad-map HARD STOP, never block the postmortem on it.

5. **Assemble the postmortem draft** per
   [reference/postmortem-format.md](../reference/postmortem-format.md) — incident-rca's full report
   verbatim, with the **Corrective actions**, **Preventive actions**, and **Post-RCA actions** tables'
   Owner columns filled from squad-map's resolved team (replacing the `<team>` placeholder) instead of
   left as-is. Decline any Jira/Slack/Confluence offer incident-rca surfaces — render the paste-ready
   blocks into the draft instead, per
   [reference/unattended-gate-policy.md § Post-report offers](../reference/unattended-gate-policy.md#post-report-offers-both-skills-always-declined).

6. **Route the postmortem draft** to the configured notification path — see [SETUP.md](../SETUP.md) §
   Config.

## Read-only boundary

Same as both wrapped skills: read + investigate + comment only. Never remediate, never change
paging-system state, never post live to Jira/Slack/PagerDuty.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| `postmortem_draft` | Returned to caller / routed notification | Full incident-rca report + filled action-table owners | Postmortem incomplete |

## Completion summary (chat)

When run inside an interactive agent session (e.g. for testing), state: service, full window used,
conclusion, owning team, action items with owners, any gates that fired and how they were answered.
