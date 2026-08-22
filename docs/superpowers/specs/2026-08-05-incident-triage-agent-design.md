# incident-triage-agent: design

**Date:** 2026-08-05
**Status:** Approved design
**Source:** Items #3+#4 of [team-facing-agents-roadmap.md](../plans/2026-08-05-team-facing-agents-roadmap.md) —
P1, "page fires → incident-rca (root cause) + squad-map (owning team) → triage doc for on-call. ...
Postmortem Drafter — incident-rca's evidence trail + squad-map ownership → drafted postmortem with
pre-assigned follow-ups. Natural extension of #3; could ship as the same agent's second mode (triage on
page-fire, draft on incident-resolved) rather than a separate agent."

## Problem

On-call gets paged and has to manually start an RCA investigation and manually figure out who else to
pull in. After an incident resolves, someone has to manually draft the postmortem, re-deriving the
evidence trail and assigning follow-ups to the right team.

## Approach

`incident-triage-agent` is a **two-skill composition, two-mode** wrapper — no new investigation logic, no
new ownership logic. It:

1. Is invoked by a paging-system webhook (PagerDuty/Opsgenie-shaped): **page-fire** (alert triggered) →
   **triage mode**; **incident-resolved** (alert/incident closed) → **postmortem mode**.
2. Delegates root-cause investigation entirely to **incident-rca**, and ownership resolution entirely to
   **squad-map** — exactly the pairing already anticipated in
   [cross-skill-escalation.md](../../skill-framework/shared/cross-skill-escalation.md)'s reverse-escalation
   row ("squad-map resolves the owning team for an incident | incident-rca resumes with squad context
   (e.g. paging, ownership-scoped evidence)").
3. Handles what neither skill solves alone: **both are designed for interactive use and stop to ask a
   human at multiple points** — a webhook trigger has no human to answer any of them. This skill's one
   piece of new logic, [reference/unattended-gate-policy.md](../../../incident-triage-agent/reference/unattended-gate-policy.md),
   enumerates every such gate in both incident-rca and squad-map and gives each a deterministic answer —
   modeled on `pr-gatekeeper/reference/auto-post-policy.md`'s pattern, which needed three review rounds to
   reach exhaustive gate coverage; this skill's policy is written exhaustive from the start using that
   lesson.
4. Two modes, one skill (per the roadmap's own suggested shape):
   - **Triage** (page-fire): fast, narrow-window incident-rca run + squad-map ownership lookup → a short
     on-call-facing triage doc, within minutes of the page.
   - **Postmortem** (incident-resolved): full-window, full-thoroughness incident-rca run (Jira/recurrence
     search included, unlike triage) + squad-map ownership → a drafted postmortem using incident-rca's
     own Corrective/Preventive/Post-RCA-actions tables, with the Owner columns pre-filled from squad-map
     instead of shipped as `<team>` placeholders.

## Why incident-rca's own report tables are enough — no new action-item schema

incident-rca's `report-template.md` already ships **Corrective actions**, **Preventive actions**, and
**Post-RCA actions** tables (Action / Owner / Priority / ETA / Notes) with `<team>` owner placeholders —
"drafted postmortem with pre-assigned follow-ups" from the roadmap item is exactly "these tables, with
`<team>` replaced by squad-map's resolved squad name." No new schema needed; postmortem mode's only
original contribution is the owner substitution plus the earlier full incident window.

## Non-goals (explicitly out of scope for this item)

- No new RCA logic, hypothesis scoring, or causal-graph rules — 100% incident-rca's own.
- No new ownership/reconciliation logic — 100% squad-map's own.
- No live paging-system HTTP receiver in this repo — same boundary as who-owns-x-bot's Slack handler and
  pr-gatekeeper's GitLab webhook handler; `SETUP.md` documents the integration contract.
- No auto-posting to Jira/Slack/PagerDuty on either skill's behalf — both incident-rca's Post-RCA-actions
  offer and any paging-system update are "offer, never auto-post" by their own design; this skill renders
  paste-ready blocks into its own doc instead of waiting for a confirmation nobody can give (mirrors how
  `pr-gatekeeper` resolved pr-review's analogous Jira/Slack offers).
- No auto-widening of scope on ambiguous runtime evidence (multi-site Datadog, sparse signal, symptom-only
  discovery) beyond the single deterministic answer defined per gate — see
  [reference/unattended-gate-policy.md](../../../incident-triage-agent/reference/unattended-gate-policy.md).
- No paging-system incident *creation* or *escalation* — this skill only reads a page/incident-resolved
  event and produces a doc; it never pages anyone or changes incident state.

## Interface contract

**Input** (from the paging-system webhook):

| Field | Required | Mode | Notes |
|-------|----------|------|-------|
| `event_type` | Yes | Both | `page_triggered` or `incident_resolved` — selects the mode |
| `service` | Yes | Both | Anchor for incident-rca; also the `query` squad-map resolves ownership for |
| `triggered_at` | Yes | Both | ISO-8601, UTC-suffixed — the page's own timestamp, not wall-clock "now" |
| `resolved_at` | Postmortem only | Postmortem | ISO-8601, UTC-suffixed — required to bound the full incident window |
| `alert_title` / `symptom` | No | Both | Free text folded into incident-rca's symptom anchor when present |
| `alert_id` | No | Both | PagerDuty/Opsgenie alert ID — passed through so incident-rca's own native PD/OG Phase 0 detection can use it (see below) |
| `severity` | No | Both | P1/P2/etc., informational only — used in the triage doc header, not a decision input |
| `workspace_root` | No | Both | Where squad-map should look for `SQUAD_MAP.md` / config, per who-owns-x-bot's precedent |

**incident-rca already has native PagerDuty/OpsGenie support** (Phase 0 detects `pd_list_incidents` /
`opsgenie_list_alerts`-shaped tools and refines `from_time` from the alert's own `triggered_at`,
per `incident-rca/reference/query-playbook.md` § PagerDuty / OpsGenie) — this skill's invocation string
follows incident-rca's own established phrasing (`RCA for <service> between <from> and <to> UTC —
<symptom> (PagerDuty alert <alert_id>, severity <severity>)`, per `incident-rca/reference/smoke-test.md`'s
canonical form) so incident-rca's own detection does the refinement; this skill does not duplicate PD/OG
alert-parsing logic itself.

**Output:**

| Mode | Deliverable |
|------|-------------|
| Triage | A short triage doc: incident-rca's executive summary + top hypothesis + squad-map's owning team + a link/pointer to the full incident-rca report if a fuller one was also produced |
| Postmortem | incident-rca's full report, with Corrective/Preventive/Post-RCA-actions tables' Owner columns filled from squad-map instead of `<team>` placeholders |

## Acceptance criteria

- `incident-triage-agent/SKILL.md` exists, ≤ 180 lines, `disable-model-invocation: true` (webhook-only
  entry point, same reasoning as who-owns-x-bot/pr-gatekeeper).
- Given a `page_triggered` event, the skill invokes incident-rca with a well-formed, UTC-suffixed,
  ≥30-minute window centered on `triggered_at` and an explicit `service` anchor — never a bare/vague
  prompt, never missing timezone, never a <10-minute window — so none of incident-rca's input-quality
  gates (vague prompt, timezone confirm, window-width confirm, symptom-only org-wide discovery) can fire.
- Given a runtime-evidence-dependent gate incident-rca cannot avoid by well-formed input (multi-site
  Datadog ambiguity, sparse signal, no observability MCP at all) → the skill answers deterministically per
  [reference/unattended-gate-policy.md](../../../incident-triage-agent/reference/unattended-gate-policy.md)
  and still produces a doc (never hangs, never fabricates confidence beyond what incident-rca itself
  would assert).
- Given squad-map cannot resolve an owner (HARD STOP on missing config, or UNKNOWN result) → the skill
  proceeds with owner `UNKNOWN`, noted as a gap — never blocks the triage doc or postmortem on ownership
  resolution (mirrors who-owns-x-bot's own handling of the same squad-map HARD STOP).
- Given a `incident_resolved` event, the skill invokes incident-rca with the full incident window
  (`triggered_at` → `resolved_at`) and full thoroughness (no Phase 3/query-investigation skip, unlike
  triage mode) and fills the report's action-table Owner columns from squad-map.
- Neither mode ever waits for or attempts a live Jira/Slack/PagerDuty post — both skills' own "offer"
  gates are declined; paste-ready blocks are rendered into this skill's own output doc instead.
- `make lint-incident-triage-agent` and `make lint-framework` pass; skill wired into root README.md,
  docs/README.md, docs/REPOSITORY.md, `skill-routing.md`, `phase-glossary.md`, `cross-skill-escalation.md`,
  `prompt-injection.md`, `CHANGELOG.md`.

## Implementation plan

1. `incident-triage-agent/SKILL.md`, `README.md`, `SETUP.md`, `CHANGELOG.md`, `examples.md`.
2. `workflow/inputs.md` (parse webhook payload, select mode from `event_type`; untrusted-content note —
   alert title/symptom text is data, not instructions), `workflow/triage.md` (Mode 1: fast/narrow-window
   incident-rca + squad-map → triage doc), `workflow/postmortem.md` (Mode 2: full-window/full-thoroughness
   incident-rca + squad-map → postmortem draft with filled owner columns).
3. `reference/phase-index.md`, `lazy-load-index.md`, `unattended-gate-policy.md` (exhaustive enumeration
   of every incident-rca and squad-map blocking gate with a deterministic answer, written exhaustive from
   the start per the pr-gatekeeper lesson), `triage-doc-format.md`, `postmortem-format.md`, `smoke-test.md`.
4. `.cursor/rules/incident-triage-agent.mdc`, `.kiro/steering/incident-triage-agent.md`.
5. `Makefile`: `install-incident-triage-agent` (chains `install-incident-rca` and `install-squad-map`),
   `install-claude-incident-triage-agent`, `lint-incident-triage-agent`, added to `.PHONY`/`lint:` deps and
   to `lint-framework`'s 4 hardcoded per-skill loops from the start.
6. Root `README.md`, `docs/README.md`, `docs/REPOSITORY.md`: rows following the established pattern.
7. `docs/skill-framework/shared/skill-routing.md`, `phase-glossary.md`, `cross-skill-escalation.md`,
   `prompt-injection.md`: routing row + disambiguation rule, phase mapping, escalation rows (this skill's
   local table must be a subset of the shared matrix), wiring-table row.
8. Root `CHANGELOG.md` + `incident-triage-agent/CHANGELOG.md`: initial release entry.
9. `make lint` green; deep review pass(es), fixing to 0 issues each round; commit.
