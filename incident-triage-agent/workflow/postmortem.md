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
   triggered_at` — this step never has to handle an inverted window). Unlike triage mode, this is the
   **actual incident duration**, not a narrow snapshot.

   **If that span is < 30 minutes**, extend the *query* `to_time` to `triggered_at + 30m` so
   incident-rca's own short-window gate never fires on a genuinely short incident — but this is padding
   for the query, not a redefinition of when the incident ended. Keep both values distinct: record
   `incident_resolved_at` (the real `resolved_at`) separately from the padded `to_time` actually sent to
   incident-rca, and carry both into the assembled draft (step 5) — any signal incident-rca surfaces
   between the real `resolved_at` and the padded `to_time` is **post-resolution context**, not part of
   the incident's causal window, and must be labeled as such in the draft rather than presented
   identically to signals from during the incident. See
   [reference/unattended-gate-policy.md § Per-mode window construction](../reference/unattended-gate-policy.md#per-mode-window-construction).

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
   everywhere).

   **Owners are proposed, not assigned (P1 fix):** squad-map's own match confidence
   (`HIGH`/`MEDIUM`/`LOW`/`UNKNOWN`, per [squad-map/reference/squad-mapping.md](../../squad-map/reference/squad-mapping.md))
   is carried alongside every filled Owner cell, and the table header/caption states explicitly that
   these are **proposed owners pending confirmation**, not settled work assignments — squad-map matches
   repo/service *names*, it does not confirm a team's capacity or agreement to own a specific action
   item. This draft is routed to a notification channel (step 6) that a human has not yet reviewed;
   presenting a name in an Owner column with no confidence or pending-confirmation marker reads as a
   completed assignment to whoever sees the channel post first, not a draft awaiting review. A
   `LOW`/`UNKNOWN` match is called out by name in the draft's own gaps section, not just left as a bare
   cell.

   **Window line states both timestamps** — `resolved_at` (the real incident end) and the padded
   query `to_time` when they differ (step 1) — and any incident-rca finding that falls in the padded
   gap is labeled *"post-resolution — outside the incident's own causal window"* rather than presented
   as an incident-time finding.

   Decline any Jira/Slack/Confluence offer incident-rca surfaces — render the paste-ready
   blocks into the draft instead, per
   [reference/unattended-gate-policy.md § Post-report offers](../reference/unattended-gate-policy.md#post-report-offers-both-skills-always-declined).

6. **Return the finished postmortem draft** for delivery to the configured notification target — see
   [SETUP.md](../SETUP.md) § Config. This skill's own workflow never calls a Slack/Jira/PagerDuty API
   itself; the calling handler (per [SETUP.md](../SETUP.md) § Integration contract) performs the one,
   final delivery of the completed draft as a new message to whatever destination it's configured with —
   distinct from the live mid-investigation writes the Read-only boundary below forbids.

## Read-only boundary

Same as both wrapped skills: read + investigate + comment only. Never remediate, never change
paging-system state. **"Never post live" (P1 fix — precise scope):** neither this skill's own workflow
nor the wrapped incident-rca/squad-map skills ever autonomously write into Jira, PagerDuty, or Slack
*during* the investigation — every such offer either skill surfaces (a Jira comment, a Slack brief, a
Confluence export, a PagerDuty update) is declined and rendered as a paste-ready block in the draft
instead, per
[reference/unattended-gate-policy.md § Post-report offers](../reference/unattended-gate-policy.md#post-report-offers-both-skills-always-declined).
This is separate from step 6's final draft handoff: a single, human-configured, terminal delivery
performed by the calling handler, not a live write this skill's own agentic workflow makes mid-run.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| `postmortem_draft` | Returned to caller / routed notification | Full incident-rca report + filled action-table owners | Postmortem incomplete |

## Completion summary (chat)

When run inside an interactive agent session (e.g. for testing), state: service, full window used,
conclusion, owning team, action items with owners, any gates that fired and how they were answered.
