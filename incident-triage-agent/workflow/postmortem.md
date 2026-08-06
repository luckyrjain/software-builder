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

1. **Construct the window** — `from_time = triggered_at`, `to_time = resolved_at` (already validated as
   a positive span by [workflow/inputs.md](../workflow/inputs.md)'s HARD STOP on `resolved_at ≤
   triggered_at` — this step never has to handle an inverted window); if that span is
   < 30 minutes, extend `to_time` to `triggered_at + 30m` — per
   [reference/unattended-gate-policy.md § Per-mode window construction](../reference/unattended-gate-policy.md#per-mode-window-construction).
   Unlike triage mode, this is the **actual incident duration**, not a narrow snapshot.

2. **Invoke incident-rca**, following its own canonical invocation phrasing verbatim, with no invented
   trailing directives ([incident-rca/reference/smoke-test.md](../../incident-rca/reference/smoke-test.md)):
   `"RCA for <service> between <from_time> and <to_time> UTC — <alert_title/symptom, if present>
   (PagerDuty alert <alert_id>)."`

3. **Answer every gate incident-rca stops at**, per
   [reference/unattended-gate-policy.md § incident-rca gates](../reference/unattended-gate-policy.md#incident-rca-gates) —
   **this mode runs at full thoroughness**: when Phase 2's checkpoint fires (gate #8), always reply
   `"continue to Phase 3"` (never `"skip Phase 3"` — that's triage mode's answer, not this mode's).
   Continuing means gate #9 (Jira project keys unknown) can genuinely fire since Phase 3 Jira search
   actually runs here. Pre-configured `jira_project_keys` ([SETUP.md](../SETUP.md) § Config) avoids it;
   if it still fires, answer "skip Jira ticket search" and note the gap.

4. **Invoke squad-map** for `service`, same as triage mode Step 4 — proceed with owner `UNKNOWN` if
   squad-map is unreachable or HARD STOPs, never block the postmortem on it.

5. **Assemble the postmortem draft** per
   [reference/postmortem-format.md](../reference/postmortem-format.md) — incident-rca's full report
   verbatim, with the applicable Owner-column placeholders in the **Corrective actions**, **Preventive
   actions**, and **Post-RCA actions** tables filled from squad-map's resolved team (the exact
   placeholder string differs per table — see the format spec's mapping, not a uniform `<team>`
   everywhere). Decline any Jira/Slack/Confluence offer incident-rca surfaces — render the paste-ready
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
