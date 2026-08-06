# Team-facing agents roadmap

**Date:** 2026-08-05
**Status:** Implemented — all 11 items shipped, each with its own design spec
(`docs/superpowers/specs/`) and a deep adversarial review loop before completion. See each skill's own
`CHANGELOG.md` for its build history.
**Scope:** Agents that *consume* the 7 skills in this repo (pr-review, incident-rca,
k8s-overprovisioning-datadog, domain-comprehension, squad-map, mysql-to-postgres-sql,
loop-task-implementer) for real team workflows. Distinct from repo-maintenance tooling — nothing here
changes skill internals; each item composes existing skills into a team-facing agent, bot, or
scheduled job.

Each item below is a candidate roadmap entry, not a committed plan. Before implementing any item,
write a design spec (`docs/superpowers/specs/`) and implementation plan (`docs/superpowers/plans/`)
per this repo's usual pattern — this doc is the brainstorm those should draw from.

## Priority tiers

- **P0** — highest value-to-effort ratio; thin wrapper around one existing skill, minimal new logic.
- **P1** — composes 2+ skills; real value, moderate build.
- **P2** — composes 3+ skills or needs new scheduling/aggregation infrastructure; highest effort.

## Roadmap items

### P0 — thin wrappers, ship first

1. **"Who owns X" Slack bot** — squad-map only, wrapped as a Slack slash command. No new logic;
   squad-map already produces exactly this answer. Smallest possible agent on this list, likely the
   right first thing to build to validate the wrapper pattern before investing in composed agents.

2. **PR Gatekeeper** — pr-review auto-run on every push (webhook-triggered), posting inline as it
   already supports. The "hand off small findings to loop-task-implementer for auto-fix" extension is
   P1-complexity — ship the plain auto-review wrapper first, add the auto-fix loop as a follow-up.

### P1 — two-skill composition

3. **Incident Triage Agent** — page fires → incident-rca (root cause) + squad-map (owning team) →
   triage doc for on-call. Needs a paging-system webhook (PagerDuty/Opsgenie) as the trigger; both
   underlying skills already support this call pattern individually.

4. **Postmortem Drafter** — incident-rca's evidence trail + squad-map ownership → drafted postmortem
   with pre-assigned follow-ups. Natural extension of #3; could ship as the same agent's second mode
   (triage on page-fire, draft on incident-resolved) rather than a separate agent.

5. **New-Hire Guide** — domain-comprehension + squad-map → personalized onboarding tour for a new
   engineer's assigned repos/services. Needs an org-chart or team-assignment input (who's joining,
   which squad) that doesn't exist in either skill today — that's the new part.

6. **Architecture Decision Assistant** — domain-comprehension only, but used differently from its
   normal full-map mode: check a proposed feature/service against existing bounded contexts and flag
   conflicts. Needs a new "delta check" invocation mode on domain-comprehension itself (compare a
   proposal against an existing manifest.yaml) more than new orchestration — closer to a
  domain-comprehension feature request than a new agent.

7. **Backlog Runner** — loop-task-implementer pointed at a ticket queue (Jira/GitHub Issues), works
   overnight, opens PRs by morning. Mostly already what loop-task-implementer does per-task; the new
   part is queue management (pull N tickets, respect dependencies across tickets, stop conditions for
   an unattended overnight run) — needs its own budget/circuit-breaker profile tighter than an
   interactive session's.

### P2 — multi-skill, needs new aggregation infrastructure

8. **Migration Program Manager** — mysql-to-postgres-sql across many repos/squads, aggregating
   `MIGRATION_STATUS.yaml` org-wide, escalating stalled services, tracking migration MRs per team.
   Needs a new cross-repo status aggregation layer (mysql-to-postgres-sql today reports per-service,
   not org-wide) — the largest new-build item on this list.

9. **Release Readiness Checker** — pr-review (MRs since last release) + k8s-overprovisioning-datadog
   (target services not riskily overprovisioned) + incident-rca (no open incidents on the release
   path). Needs a "since last release" MR-range resolver and a release-manifest input (which services
   this release touches) that don't exist yet.

10. **Cost Optimization Sprint Planner** — k8s-overprovisioning-datadog org-wide sweep, ranked by
    waste, grouped by squad-map ownership, turned into a prioritized backlog with $ estimates.
    Effectively a scheduled, aggregated version of k8s-overprovisioning-datadog's existing per-service
    report — the new part is the org-wide sweep + squad grouping + ranking, not new analysis logic.

11. **Weekly Squad Digest** — scheduled per-squad Slack post combining k8s-overprovisioning-datadog
    (overprovisioned services), mysql-to-postgres-sql (pending migrations), and squad-map (routing to
    the right channel). Shares the aggregation infrastructure #8 and #10 would need — worth building
    after those two land rather than before, so the aggregation layer is designed once, not three
    times.

## Suggested build order

Given the P2 items share aggregation-layer needs, and the P0/P1 items validate the wrapper pattern
cheaply:

1. #1 (who-owns-X bot) — validates the thin-wrapper pattern
2. #2 (PR Gatekeeper) — validates the trigger-on-event pattern
3. #3 + #4 (Incident Triage + Postmortem, one agent two modes) — validates two-skill composition and
   the paging-webhook trigger
4. Design the shared cross-repo aggregation layer once, informed by what #8, #10, #11 all need, before
   building any of them individually
5. #7 (Backlog Runner) can proceed independently of the aggregation-layer work — no shared dependency

#5, #6, #9 are lower urgency — revisit after the above land and real usage surfaces which of them
teams actually ask for.

## Out of scope for this roadmap

- Any change to the 7 existing skills' own internals (that's regular skill maintenance, tracked in
  each skill's own `CHANGELOG.md` section).
- Repo-maintenance agents (skill-framework-auditor, docs-freshness-bot, etc.) — separate brainstorm,
  not team-facing.
