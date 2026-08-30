# Skill Routing (shared)

**Normative.** Single source of truth for routing user requests to the correct skill. Each skill's
"When NOT to use" table MUST be a subset of this routing table — do not maintain independent routing
logic per skill.

When adding a new skill, add it here first; then each existing skill only needs a link to this file.

## Routing table

| User intent / keywords | Route to | NOT these |
|------------------------|----------|-----------|
| Overprovisioned, right-size, rightsizing, CPU/memory requests, HPA, replicas, throttling, OOM (sizing context), Kafka consumer lag (scaling), cost/waste, namespace waste ranking | **k8s-overprovisioning-datadog** | incident-rca, pr-review |
| RCA, root cause, postmortem, incident, outage, 5xx spike, error spike, deploy regression (time-window), consumer lag (incident), SLO breach, P1/P2, INC-, on-call (interactive, conversational) | **incident-rca** | k8s-overprovisioning-datadog, pr-review |
| PagerDuty/Opsgenie page-fire or incident-resolved webhook, no follow-up turn possible | **incident-triage-agent** | incident-rca, squad-map (that's what it delegates to internally — do not call either directly for an unattended paging event, their own confirmation gates are designed to wait for a human chat turn) |
| Review PR/MR, review pull request/merge request — generic correctness/regression review, /pr-review, re-review, post-merge audit, list open reviews, review as SRE/security/architect (interactive, conversational) | **pr-review** | change-impact-analyzer, incident-rca, k8s-overprovisioning-datadog |
| GitLab push-event webhook, automated review on every push, no follow-up turn possible | **pr-gatekeeper** | pr-review (that's what it delegates to internally — do not call pr-review directly for an unattended webhook run, its own posting confirmation is designed to wait for a human chat turn) |
| Domain comprehension, bounded context, data ownership, critical path, architecture smells, subsystem onboarding **with no person named**, multi-repo ground truth, five questions | **domain-comprehension** | squad-map (ownership only), incident-rca, new-hire-guide (onboarding **a named person**, not a subsystem) |
| Squad map, ownership, who owns, CODEOWNERS, GitLab group, Datadog team, team reconciliation (interactive, conversational) | **squad-map** | domain-comprehension (full map) |
| `/who-owns` Slack slash command, single-shot automated ownership lookup with a structured `query`, no follow-up turn possible | **who-owns-x-bot** | squad-map (that's what it delegates to internally — do not call squad-map directly for a single-shot Slack reply, its output contract is a markdown file + chat summary, not one message) |
| New engineer onboarding, new-hire tour, "joining the squad", first-week orientation, **a person is named** (interactive, conversational) | **new-hire-guide** | squad-map (ownership only, no tour), domain-comprehension (subsystem/domain onboarding with **no person named** — "subsystem onboarding" is domain-comprehension's own trigger phrase too; the person-named test is what disambiguates, not the word "onboarding") |
| Release readiness, "is this release ready to ship?", release go/no-go, pre-release check with a `release_manifest` (interactive, conversational) | **release-readiness-checker** | pr-review (one specific MR only), k8s-overprovisioning-datadog (one service only), incident-rca (full root-cause investigation, not a Phase-1-only signal check) |
| MySQL scrub, jdbc:postgresql, TIMESTAMPDIFF, DATE_FORMAT, native SQL rewrite, mysql2→pg, SQLAlchemy PG cutover, domain-pack P0/P1 cooling SQL | **mysql-to-postgres-sql** | domain-comprehension (full map), squad-map (ownership only) |
| Org-wide migration status, migration program, "which services/squads are stuck migrating", stalled migration escalation, migration MR rollup across many repos with a `program_manifest` | **migration-program-manager** | mysql-to-postgres-sql (one workspace's own migration status), squad-map (ownership lookup only, no migration status) |
| Org-wide cost/waste ranking, cost optimization sprint, "where's the money", rightsizing sprint planning, cost savings backlog across many deployments with a `sweep_scope` | **cost-optimization-sprint-planner** | k8s-overprovisioning-datadog (one deployment's own rightsizing question), squad-map (ownership lookup only, no cost angle) |
| Implement task/issue autonomously, independent review + remediation loop, adjudicate findings, work through a task queue (interactive, human-driven) | **loop-task-implementer** | pr-review (reviewing someone else's existing MR only) |
| Scheduled trigger pulling N tickets from a tracker query, overnight/unattended, no human turn available | **backlog-runner** | loop-task-implementer (that's what it delegates to internally — do not call loop-task-implementer directly for an unattended scheduled sweep; use it for a single-task or human-driven multi-task request) |
| Scheduled combined squad digest reading both migration and cost rollup files, no human turn available | **weekly-squad-digest** | migration-program-manager / cost-optimization-sprint-planner (a fresh single-source rollup, not the combined digest) |
| PRD, product requirements, feature spec, product spec, requirements document, turn idea into PRD, implementation-ready spec | **prd-architect** | loop-task-implementer (implement the feature), domain-comprehension (map existing codebase), pr-review (review MR) |
| Should we build this, is this worth building, challenge this idea, build vs buy, what alternatives exist (no authoritative PRD) | **prd-architect** Validation Mode | loop-task-implementer (implement before validating), domain-comprehension (architecture map only) |
| Review PRD, PRD gaps, PRD readiness, improve product spec, critique requirements doc (existing PRD supplied) | **prd-architect** Review Mode | pr-review (code/MR review), domain-comprehension (bounded-context map) |
| Write tests, generate tests, add test coverage, backfill tests, test this MR/PR/diff — level unspecified **or two or more complementary test levels explicitly requested** | **test-writer** (plans one or more complementary levels and dispatches the existing specialists independently) | pr-review (reviewing existing test quality, not writing new tests), loop-task-implementer (implementing the production feature itself) |
| Unit tests, function/class-level tests, mock all externals, TDD helper, fast isolated tests — when unit is the **only** requested level | **unit-test-creator** | integration-test-creator (needs a real adjacent dependency, not a mock) |
| Integration tests, test against a real DB/queue/service, testcontainers, docker-compose test env, seam between components — when integration is the **only** requested level | **integration-test-creator** | unit-test-creator (isolated, mocked), e2e-test-creator (full user journey through the UI) |
| Contract tests, consumer-driven contract, Pact, provider verification, "does the API still match what the consumer expects" — when contract is the **only** requested level | **contract-test-creator** | integration-test-creator (a real dependency, not an interface agreement), api-test-creator (a standalone black-box suite, not a consumer/provider agreement) |
| E2E tests, end-to-end, browser test, user journey, Playwright/Cypress/Selenium, click-through test — when e2e is the **only** requested level | **e2e-test-creator** | integration-test-creator (below the UI), unit-test-creator (function-level), api-test-creator (no browser involved) |
| API tests, Postman, Newman, black-box API test, request/response assertion, REST endpoint test — when api is the **only** requested level | **api-test-creator** | integration-test-creator (in-process/testcontainers-backed, not black-box HTTP), contract-test-creator (a consumer/provider agreement, not a standalone suite), e2e-test-creator (a browser journey, not an API-only one) |
| Local uncommitted diff, review unstaged | **Host local diff/code-review workflow** — no registered skill owns local-only diff review | pr-review |
| Required provider/capability unavailable or unauthorized | Follow **mcp-error-handling.md** and the skill's declared degraded mode; do not route to an unregistered setup skill | all registered skills |
| Live rollback, kubectl apply, deploy, restart pods | **Out of scope** — accountable operator or explicitly authorized host workflow | all skills |
| Security-only deep review (no MR) | **security-review** | pr-review (general code-quality review, which escalates here for security-sensitive findings) |
| Architecture review, ADR, architecture decision record, design review, "should we build it this way", scale limits, failure modes, proposed design + diagram | **architecture-review** | prd-architect (PRD authoring), system-design (implementation-level design), pr-review (already-merged code) |
| System design, technical design doc, component design, data model, state machine, rollout plan, implementation-oriented design, ready PRD turned into implementation design | **system-design** | architecture-review (whether the architecture is sound), api-design-review (an existing API's contract), prd-architect (the PRD itself) |
| API design review, API contract review, breaking change (API), API versioning, pagination design | **api-design-review** | pr-review (full MR review), database-review (schema), system-design (whole-system design) |
| Database review, schema review, migration review, index review, query plan, locking, partitioning | **database-review** | mysql-to-postgres-sql (dialect rewrite), pr-review (general MR review), capacity-planner (forecasting) |
| Security review, authN, authZ, injection, SSRF, tenant isolation, secrets, cryptography review | **security-review** | pr-review (general code-quality review, which escalates here for security-sensitive findings), dependency-upgrade-review (CVE sweep) |
| Performance review, N+1, slow query, cache design, concurrency review, connection pool sizing | **performance-review** | capacity-planner (turning demand into capacity numbers), database-review (schema/index design directly) |
| Capacity planning, capacity forecast, scaling requirements, replica count, headroom | **capacity-planner** | k8s-overprovisioning-datadog (current rightsizing against live metrics), performance-review (code review) |
| Observability review, SLO review, alert coverage, tracing coverage, correlation ID, dashboard review | **observability-review** | incident-rca (investigating a live incident), deployment-risk-review (risk for a specific release) |
| Deployment risk, release risk, blast radius, rollback plan, go/no-go on deployment risk alone (single-dimension, not an aggregated ship/no-ship verdict) | **deployment-risk-review** | release-readiness-checker (multi-repo release sweep), incident-triage-agent (an incident that already happened), production-readiness-review (go/no-go for one change spanning ALL evidence, not deployment risk alone) |
| Dependency upgrade, version bump review, CVE review, breaking change (library), transitive dependency | **dependency-upgrade-review** | security-review (a dedicated deep security audit), mysql-to-postgres-sql (the MySQL-to-Postgres migration itself) |
| Tech debt, debt prioritization, debt backlog, engineering drag, refactor prioritization | **tech-debt-assessor** | migration-program-manager (planning a specific migration program), cost-optimization-sprint-planner (cost/rightsizing sweep) |
| Change impact, affected services/contracts/data/tests, callers/consumers touched by a proposed design or exact PR/MR | **change-impact-analyzer** | pr-review (generic correctness/regression review), deployment-risk-review (blast radius/rollback risk after deployment) |
| Resilience review, failure-mode review, timeout budgets, retries, circuit breakers, load shedding, backpressure, queues, idempotency, partial failure, recovery or reconciliation | **resilience-review** | incident-rca (live incident diagnosis), capacity-planner (demand/headroom forecasting), pr-review (generic correctness/regression review) |
| Implementation plan, implementation planning, task decomposition, dependency-aware implementation DAG, execution waves, plan traceability | **implementation-planner** | loop-task-implementer (executes the plan), system-design (creates the design), pr-review (reviews the resulting code) |
| Is this PR/MR production ready, ready to release, ready to deploy, go/no-go for one/this change (aggregated across CI/review/policy/specialists), production readiness review for one exact PR/MR/release candidate | **production-readiness-review** | pr-review (generic correctness review only), release-readiness-checker (release-wide go/no-go across multiple services), deployment-risk-review/change-impact-analyzer (single-dimension analysis, not the aggregated readiness rollup) |

## Disambiguation rules

1. **Time-window + error/outage** → incident-rca (even if service is overprovisioned)
2. **Sizing / resource optimization** (no active incident) → k8s-overprovisioning-datadog
3. **GitLab MR target** → pr-review for generic correctness; affected-surface questions take precedence and route to change-impact-analyzer
4. **"Who owns X?"** without domain map intent → squad-map
5. **"Map the domain / bounded contexts"** → domain-comprehension (which delegates ownership to squad-map at Session 0b)
6. **OOM in sizing context** ("is this overprovisioned?") → k8s-overprovisioning-datadog; **OOM in incident context** ("what caused the outage?") → incident-rca
7. **Kafka lag in scaling context** → k8s-overprovisioning-datadog; **Kafka lag in incident context** → incident-rca
8. **Native SQL / JDBC migration to PostgreSQL** → mysql-to-postgres-sql; **domain map / bounded contexts** → domain-comprehension
9. **Migration MR review** → pr-review (even if diff is SQL rewrites)
10. **Ownership request from an automated, single-shot caller** (Slack slash command, no follow-up turn) → who-owns-x-bot; **ownership request from an interactive human turn** → squad-map directly
11. **Review request from a push webhook, no human turn available** → pr-gatekeeper; **review request from an interactive human turn** → pr-review directly
12. **Page-fire or incident-resolved event from a paging system, no human turn available** → incident-triage-agent; **RCA or ownership request from an interactive human turn** → incident-rca / squad-map directly
13. **Scheduled overnight ticket-queue sweep, no human turn available** → backlog-runner; **single-task or human-driven multi-task request** → loop-task-implementer directly
14. **Onboarding request naming a person** ("onboard `<name>`, joining `<squad>`") → new-hire-guide; **onboarding request naming a subsystem/domain, no person named** ("help me onboard to the payments subsystem") → domain-comprehension directly, even though both skills use the word "onboarding"; **plain "who owns X?"** (no new-hire input) → squad-map directly
15. **Release-wide go/no-go request with a `release_manifest`** → release-readiness-checker; **one specific MR generic review** → pr-review directly, while **one specific MR affected-surface analysis** → change-impact-analyzer; **one specific service's rightsizing** → k8s-overprovisioning-datadog directly; **full RCA on a known/suspected incident** → incident-rca directly
16. **Org-wide migration status across many workspaces with a `program_manifest`** → migration-program-manager; **one workspace's own migration status** → mysql-to-postgres-sql directly; **plain "who owns X?" with no migration angle** → squad-map directly
17. **Org-wide cost/waste ranking across many deployments with a `sweep_scope`** → cost-optimization-sprint-planner; **one deployment's own rightsizing question** → k8s-overprovisioning-datadog directly; **plain "who owns X?" with no cost angle** → squad-map directly
18. **Scheduled combined squad digest, no human turn available** → weekly-squad-digest; **a fresh single-source rollup, interactive** → migration-program-manager / cost-optimization-sprint-planner directly
19. **Test creation routing:** one explicitly named level (unit, integration, contract, e2e, or api) → that matching `*-test-creator` directly; **two or more explicitly named complementary levels** → test-writer to build and execute the multi-level plan; level unspecified → test-writer; several levels that are only competing interpretations of one behavior → test-writer asks once rather than dispatching all candidates; **review existing test quality** → pr-review; **implement production behavior** → loop-task-implementer.
20. **Product spec / PRD / requirements doc** → prd-architect; **"should we build X?" without an authoritative PRD** → prd-architect Validation Mode; **existing PRD + gaps/readiness** → prd-architect Review Mode; **"implement the PRD"** → loop-task-implementer directly; **"map the domain / bounded contexts"** → domain-comprehension directly
21. **PRD → implementation design → architecture validation** is the canonical lifecycle: a ready PRD and request to design the implementation routes to **system-design**, then the resulting design routes to **architecture-review**; **PRD/proposal + "is this the right architecture?"** may still route directly to architecture-review; an existing API/schema's own contract → api-design-review / database-review directly, not architecture-review or system-design; a specific security/authZ/crypto concern → security-review directly, not architecture-review's general security-posture section
22. **One exact PR/MR/release-candidate "production ready?" or "ready to release?" request** → production-readiness-review, even though the phrase "ready to release" overlaps release-readiness-checker's own trigger; **release-wide go/no-go across multiple services with a `release_manifest`** → release-readiness-checker directly; **a generic correctness/regression review with no readiness framing** → pr-review directly; **one specific analysis dimension only** (blast radius, affected surface) → deployment-risk-review / change-impact-analyzer directly

## Ambiguous requests — ask

If the user's intent matches multiple skills equally (e.g. "checkout-api has OOM and high latency"), ask which angle they want:
- "Investigate the incident?" → incident-rca
- "Assess resource sizing?" → k8s-overprovisioning-datadog

For test creation, multiple explicit levels are not automatically ambiguous: route complementary named surfaces through test-writer. If several levels are merely alternative interpretations of the same target, test-writer asks which surface is intended instead of dispatching all of them.

Do not default to one skill when the intent is genuinely ambiguous.

## Cross-skill handoffs

After a skill completes, it may recommend invoking another skill. See [cross-skill-escalation.md](cross-skill-escalation.md) for the full handoff matrix. Handoffs use the portable envelope and recursion rules in [runtime-contract.md](runtime-contract.md).

## Universal inherited contracts

Every registered skill inherits these shared contracts through this routing document:

- Runtime/input/evidence/freshness/stopping/result/handoff/state semantics: [runtime-contract.md](runtime-contract.md)
- Host/provider capability boundary and packaging behavior: [host-adapter-contract.md](host-adapter-contract.md)
- Positive/negative/ambiguous/adversarial/degraded evaluation requirements: [eval-contract.md](eval-contract.md)

These files are normative. Skill-local text should document only domain-specific deltas instead of copying the shared rules.

## How skills reference this table

From a skill's `SKILL.md`:

```markdown
Routing: [skill-routing.md](../docs/skill-framework/shared/skill-routing.md)
```

Each skill's "When NOT to use" section should link here and list only its 3–5 most common mis-routes as a quick reference — not a complete routing table.
