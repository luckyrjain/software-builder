# Skill Routing (shared)

**Normative.** Single source of truth for routing user requests to the correct skill. Each skill's
"When NOT to use" table MUST be a subset of this routing table — do not maintain independent routing
logic per skill.

When adding a new skill, add it here first; then each existing skill only needs a link to this file.

## Routing table

| User intent / keywords | Route to | NOT these |
|------------------------|----------|-----------|
| Overprovisioned, right-size, rightsizing, CPU/memory requests, HPA, replicas, throttling, OOM (sizing context), Kafka consumer lag (scaling), cost/waste, namespace waste ranking | **k8s-overprovisioning-datadog** | incident-rca, pr-review |
| RCA, root cause, postmortem, incident, outage, 5xx spike, error spike, deploy regression (time-window), consumer lag (incident), SLO breach, P1/P2, INC-, on-call | **incident-rca** | k8s, pr-review |
| Review MR, review merge request, review !IID, /pr-review, re-review, post-merge audit, list open MRs, review as SRE/security/architect | **pr-review** | incident-rca, k8s |
| Domain comprehension, bounded context, data ownership, critical path, architecture smells, subsystem onboarding, multi-repo ground truth, five questions | **domain-comprehension** | squad-map (ownership only), incident-rca |
| Squad map, ownership, who owns, CODEOWNERS, GitLab group, Datadog team, team reconciliation | **squad-map** | domain-comprehension (full map) |
| MySQL scrub, jdbc:postgresql, TIMESTAMPDIFF, DATE_FORMAT, native SQL rewrite, mysql2→pg, SQLAlchemy PG cutover, collection P0/P1 cooling SQL | **mysql-to-postgres-sql** | domain-comprehension (full map), squad-map (ownership only) |
| Implement task/issue autonomously, independent review + remediation loop, adjudicate findings, work through a task queue | **loop-task-implementer** | pr-review (reviewing someone else's existing MR only) |
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
