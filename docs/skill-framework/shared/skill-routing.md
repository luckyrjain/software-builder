# Skill Routing (shared)

**Normative.** Single source of truth for routing user requests to the correct skill. Each skill's
"When NOT to use" table MUST be a subset of this routing table — do not maintain independent routing
logic per skill.

When adding a new skill, add it here first; then each existing skill only needs a link to this file.

## Routing table

| User intent / keywords | Route to | NOT these |
|------------------------|----------|-----------|
| Overprovisioned, right-size, rightsizing, CPU/memory requests, HPA, replicas, throttling, OOM (sizing context), Kafka consumer lag (scaling), cost/waste, namespace waste ranking | **k8s-overprovisioning-datadog** | incident-rca, pr-review |
| RCA, root cause, postmortem, incident, outage, 5xx spike, error spike, deploy regression (time-window), consumer lag (incident), SLO breach, P1/P2, INC-, on-call (interactive, conversational) | **incident-rca** | k8s, pr-review |
| PagerDuty/Opsgenie page-fire or incident-resolved webhook, no follow-up turn possible | **incident-triage-agent** | incident-rca, squad-map (that's what it delegates to internally — do not call either directly for an unattended paging event, their own confirmation gates are designed to wait for a human chat turn) |
| Review MR, review merge request, review !IID, /pr-review, re-review, post-merge audit, list open MRs, review as SRE/security/architect (interactive, conversational) | **pr-review** | incident-rca, k8s |
| GitLab push-event webhook, automated review on every push, no follow-up turn possible | **pr-gatekeeper** | pr-review (that's what it delegates to internally — do not call pr-review directly for an unattended webhook run, its own posting confirmation is designed to wait for a human chat turn) |
| Domain comprehension, bounded context, data ownership, critical path, architecture smells, subsystem onboarding **with no person named**, multi-repo ground truth, five questions | **domain-comprehension** | squad-map (ownership only), incident-rca, new-hire-guide (onboarding **a named person**, not a subsystem) |
| Squad map, ownership, who owns, CODEOWNERS, GitLab group, Datadog team, team reconciliation (interactive, conversational) | **squad-map** | domain-comprehension (full map) |
| `/who-owns` Slack slash command, single-shot automated ownership lookup with a structured `query`, no follow-up turn possible | **who-owns-x-bot** | squad-map (that's what it delegates to internally — do not call squad-map directly for a single-shot Slack reply, its output contract is a markdown file + chat summary, not one message) |
| New engineer onboarding, new-hire tour, "joining the squad", first-week orientation, **a person is named** (interactive, conversational) | **new-hire-guide** | squad-map (ownership only, no tour), domain-comprehension (subsystem/domain onboarding with **no person named** — "subsystem onboarding" is domain-comprehension's own trigger phrase too; the person-named test is what disambiguates, not the word "onboarding") |
| Release readiness, "is this release ready to ship?", release go/no-go, pre-release check with a `release_manifest` (interactive, conversational) | **release-readiness-checker** | pr-review (one specific MR only), k8s-overprovisioning-datadog (one service only), incident-rca (full root-cause investigation, not a Phase-1-only signal check) |
| MySQL scrub, jdbc:postgresql, TIMESTAMPDIFF, DATE_FORMAT, native SQL rewrite, mysql2→pg, SQLAlchemy PG cutover, collection P0/P1 cooling SQL | **mysql-to-postgres-sql** | domain-comprehension (full map), squad-map (ownership only) |
| Org-wide migration status, migration program, "which services/squads are stuck migrating", stalled migration escalation, migration MR rollup across many repos with a `program_manifest` | **migration-program-manager** | mysql-to-postgres-sql (one workspace's own migration status), squad-map (ownership lookup only, no migration status) |
| Org-wide cost/waste ranking, cost optimization sprint, "where's the money", rightsizing sprint planning, cost savings backlog across many deployments with a `sweep_scope` | **cost-optimization-sprint-planner** | k8s-overprovisioning-datadog (one deployment's own rightsizing question), squad-map (ownership lookup only, no cost angle) |
| Implement task/issue autonomously, independent review + remediation loop, adjudicate findings, work through a task queue (interactive, human-driven) | **loop-task-implementer** | pr-review (reviewing someone else's existing MR only) |
| Scheduled trigger pulling N tickets from a tracker query, overnight/unattended, no human turn available | **backlog-runner** | loop-task-implementer (that's what it delegates to internally — do not call loop-task-implementer directly for an unattended scheduled sweep; use it for a single-task or human-driven multi-task request) |
| GitHub pull request, local uncommitted diff, review unstaged | **review-bugbot** (external) | pr-review |
| Datadog MCP missing / 403, configure Datadog | **ddsetup** / **ddconfig** | all others |
| Live rollback, kubectl apply, deploy, restart pods | **Out of scope** — human operator | all skills |
| Security-only deep review (no MR) | **pr-review** with security persona | — |

## Disambiguation rules

1. **Time-window + error/outage** → incident-rca (even if service is overprovisioned)
2. **Sizing / resource optimization** (no active incident) → k8s-overprovisioning-datadog
3. **GitLab MR target** → pr-review (even if the MR changes resources)
4. **"Who owns X?"** without domain map intent → squad-map
5. **"Map the domain / bounded contexts"** → domain-comprehension (which delegates ownership to squad-map at Session 0b)
6. **OOM in sizing context** ("is this overprovisioned?") → k8s; **OOM in incident context** ("what caused the outage?") → incident-rca
7. **Kafka lag in scaling context** → k8s; **Kafka lag in incident context** → incident-rca
8. **Native SQL / JDBC migration to PostgreSQL** → mysql-to-postgres-sql; **domain map / bounded contexts** → domain-comprehension
9. **Migration MR review** → pr-review (even if diff is SQL rewrites)
10. **Ownership request from an automated, single-shot caller** (Slack slash command, no follow-up turn) →
    who-owns-x-bot; **ownership request from an interactive human turn** → squad-map directly
11. **Review request from a push webhook, no human turn available** → pr-gatekeeper; **review request from
    an interactive human turn** → pr-review directly
12. **Page-fire or incident-resolved event from a paging system, no human turn available** →
    incident-triage-agent; **RCA or ownership request from an interactive human turn** → incident-rca /
    squad-map directly
13. **Scheduled overnight ticket-queue sweep, no human turn available** → backlog-runner; **single-task or
    human-driven multi-task request** → loop-task-implementer directly
14. **Onboarding request naming a person** ("onboard `<name>`, joining `<squad>`") → new-hire-guide;
    **onboarding request naming a subsystem/domain, no person named** ("help me onboard to the payments
    subsystem") → domain-comprehension directly, even though both skills use the word "onboarding";
    **plain "who owns X?"** (no new-hire input) → squad-map directly
15. **Release-wide go/no-go request with a `release_manifest`** → release-readiness-checker; **one
    specific MR** → pr-review directly; **one specific service's rightsizing** → k8s-overprovisioning-datadog
    directly; **full RCA on a known/suspected incident** → incident-rca directly
16. **Org-wide migration status across many workspaces with a `program_manifest`** →
    migration-program-manager; **one workspace's own migration status** → mysql-to-postgres-sql directly;
    **plain "who owns X?" with no migration angle** → squad-map directly
17. **Org-wide cost/waste ranking across many deployments with a `sweep_scope`** →
    cost-optimization-sprint-planner; **one deployment's own rightsizing question** →
    k8s-overprovisioning-datadog directly; **plain "who owns X?" with no cost angle** → squad-map directly

## Ambiguous requests — ask

If the user's intent matches multiple skills equally (e.g. "checkout-api has OOM and high latency"),
ask which angle they want:
- "Investigate the incident?" → incident-rca
- "Assess resource sizing?" → k8s-overprovisioning-datadog

Do not default to one skill when the intent is genuinely ambiguous.

## Cross-skill handoffs

After a skill completes, it may recommend invoking another skill. See
[cross-skill-escalation.md](cross-skill-escalation.md) for the full handoff matrix.

## How skills reference this table

From a skill's `SKILL.md`:

```markdown
Routing: [skill-routing.md](../docs/skill-framework/shared/skill-routing.md)
```

Each skill's "When NOT to use" section should link here and list only its 3–5 most common mis-routes
as a quick reference — not a complete routing table.
