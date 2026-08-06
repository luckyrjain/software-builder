---
workflow_version: 1.0
phase: triage
produces:
  - triage_doc
consumes:
  - service
  - triggered_at
  - alert_title
  - alert_id
  - severity
  - workspace_root
---

# Triage — fast root cause + owning team for on-call

**Goal:** Within minutes of a page, tell on-call what likely broke and who owns it. No new investigation
or ownership logic here — see § Non-goals in the
[design spec](../../docs/superpowers/specs/2026-08-05-incident-triage-agent-design.md#non-goals-explicitly-out-of-scope-for-this-item)
and [reference/unattended-gate-policy.md](../reference/unattended-gate-policy.md).

## Steps

1. **Construct the window** — `from_time = triggered_at − 20m`, `to_time = triggered_at + 10m` (30
   minutes total, **weighted toward before the page** — 20 minutes pre-trigger to catch the actual cause,
   10 minutes post-trigger to catch immediate fallout; not symmetric around `triggered_at`) — per
   [reference/unattended-gate-policy.md § Per-mode window construction](../reference/unattended-gate-policy.md#per-mode-window-construction).
   Never use wall-clock "now" — invocation latency must not shrink the window below the 30-minute
   guarantee.

2. **Invoke incident-rca**, following its own canonical invocation phrasing verbatim, with no invented
   trailing directives ([incident-rca/reference/smoke-test.md](../../incident-rca/reference/smoke-test.md)):
   `"RCA for <service> between <from_time> and <to_time> UTC — <alert_title/symptom, if present>
   (PagerDuty alert <alert_id>, severity <severity>)."` incident-rca has no documented mechanism for a
   leading "skip investigation steps" instruction — the actual speed lever for this mode is the Phase 2
   checkpoint reply in the next step, not the opening message.

3. **Answer every gate incident-rca stops at**, per
   [reference/unattended-gate-policy.md § incident-rca gates](../reference/unattended-gate-policy.md#incident-rca-gates) —
   deterministically, never guessing beyond that table. **This is where triage mode's speed comes from:**
   when Phase 2's checkpoint fires (it does on essentially every run), always reply `"skip Phase 3"` —
   gate #8 in that table — which jumps straight to Phase 4 ranking without Jira/recurrence search.

4. **Invoke squad-map** for `service` (single-repo/service lookup, per
   [squad-map/workflow/inputs.md](../../squad-map/workflow/inputs.md) § Repo scope), scoped to
   `workspace_root`. If squad-map is unreachable or HARD STOPs, apply
   [reference/unattended-gate-policy.md § squad-map gates](../reference/unattended-gate-policy.md#squad-map-gates) —
   proceed with owner `UNKNOWN`, never block the triage doc on this.

5. **Assemble the triage doc** per
   [reference/triage-doc-format.md](../reference/triage-doc-format.md) — incident-rca's executive summary
   + top hypothesis (or its "No defensible root cause" conclusion) + squad-map's owning team (or
   `UNKNOWN`) + severity + a pointer to the full incident-rca report for follow-up. Decline any
   Post-RCA-actions Jira/Slack offer incident-rca surfaces — render the paste-ready block into the triage
   doc instead, per
   [reference/unattended-gate-policy.md § Post-report offers](../reference/unattended-gate-policy.md#post-report-offers-both-skills-always-declined).

6. **Return the finished triage doc** for delivery to the configured notification target — see
   [SETUP.md](../SETUP.md) § Config. This skill's own workflow never calls a Slack/Jira/PagerDuty API
   itself; the calling handler (per [SETUP.md](../SETUP.md) § Integration contract) performs the one,
   final delivery of the completed doc as a new message to whatever destination it's configured with —
   distinct from the live mid-investigation writes the Read-only boundary below forbids.

## Read-only boundary

Same as both wrapped skills: read + investigate + comment only. Never remediate (deploy/rollback/scale),
never change paging-system state. **"Never post live" (P1 fix — precise scope):** neither this skill's
own workflow nor the wrapped incident-rca/squad-map skills ever autonomously write into Jira, PagerDuty,
or Slack *during* the investigation — every such offer either skill surfaces (a Jira comment, a Slack
brief, a PagerDuty update) is declined and rendered as a paste-ready block in the doc instead, per
[reference/unattended-gate-policy.md § Post-report offers](../reference/unattended-gate-policy.md#post-report-offers-both-skills-always-declined).
This is separate from step 6's final doc handoff: a single, human-configured, terminal delivery performed
by the calling handler, not a live write this skill's own agentic workflow makes mid-run.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| `triage_doc` | Returned to caller / routed notification | Top hypothesis (or no-root-cause conclusion), owning team (or UNKNOWN), severity, gaps | Triage incomplete |

## Completion summary (chat)

When run inside an interactive agent session (e.g. for testing), state: service, window used, top
hypothesis + confidence, owning team, any gates that fired and how they were answered.
