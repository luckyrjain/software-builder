# Cross-skill escalation (shared)

**Normative.** Symmetric escalation matrix for pr-review, pr-gatekeeper, incident-rca, incident-triage-agent, k8s-overprovisioning-datadog, domain-comprehension, squad-map, who-owns-x-bot, new-hire-guide, release-readiness-checker, mysql-to-postgres-sql, loop-task-implementer, backlog-runner, migration-program-manager, cost-optimization-sprint-planner, weekly-squad-digest, prd-architect, test-writer, unit-test-creator, integration-test-creator, contract-test-creator, e2e-test-creator, and api-test-creator.

**Consumers:** `SKILL.md` in each skill (link here; keep ≤10 skill-specific rows max).

**This table is optional escalations only — not mandatory subroutine calls.** One row below is not
optional: domain-comprehension's Session 0b *always* invokes squad-map as a required phase (produces
`SQUAD_MAP.md`, consumed by later phases), not a suggestion the agent may skip — see
[phase-index.md](../../../domain-comprehension/reference/phase-index.md). It's listed here anyway,
marked **(subroutine, not optional)**, because it's still a real cross-skill call other skills should
know about — don't treat it as a "you may want to" row the way every other row in this table is.

## 1. Symmetric matrix (forward escalations)

| Trigger | From → To | Handoff artifact | User prompt template |
|---------|-----------|------------------|----------------------|
| Critical security / bad deploy in prod | pr-review → incident-rca | Incident window + MR link + service | "RCA for `{service}` {window} — deploy regression from MR !{iid}" |
| K8s/infra perf regression in MR | pr-review → k8s | Deployment + env + resource diff | "Assess rightsizing for `{deployment}` in `{env}` — MR !{iid} reduced resources" |
| Resource-down MR merged + outage | pr-review → k8s + incident-rca | MR + post-merge window | "RCA `{service}` {window}; then k8s assessment for `{deployment}`" |
| Deploy regression confirmed | incident-rca → pr-review | Causative MR URL/IID + window | "Review MR !{iid} for deploy regression tied to `{service}` outage {window}" |
| Infra capacity (OOM/throttle/crashloop) | incident-rca → k8s | [report-template.md#k8s-skill-handoff](../../../incident-rca/report-template.md#k8s-skill-handoff-infra-capacity-confirmed) block | "Assess rightsizing for `{service}` in `{env}` — OOMKilled during {window}" |
| Kafka consumer lag | incident-rca → k8s | Service + consumer group + lag metrics | "Assess `{deployment}` replicas vs partitions — consumer lag spike {window}" |
| OOM / crashloop on assessed deployment | k8s → incident-rca | Time window + OBS evidence | "RCA for `{service}` {window} — OOMKilled pods on `{deployment}`" |
| Manifest drift + active incident | k8s → incident-rca | Drift summary + deploy timeline | "RCA `{service}` {window} — manifest drift detected during assessment" |
| Spike + recent deploy | k8s → pr-review | Suspect MR from deploy event | "Review MR !{iid} — deploy preceded utilization spike on `{deployment}`" |
| Squad ownership only (no domain map) | domain-comprehension → squad-map | In-scope repo census + `domain-config.yaml` ownership | "Map squads for repos in `{workspace}` — org prefix `{org}`, segment `{n}`" |
| **Session 0b (subroutine, not optional)** — every domain-comprehension run | domain-comprehension → squad-map | Workspace root + repo census | Not user-facing — Session 0b invokes squad-map directly per [session-0b.md](../../../domain-comprehension/workflow/session-0b.md) |
| Full domain map after squad map | squad-map → domain-comprehension | `SQUAD_MAP.md` + workspace root | "Map bounded contexts and data ownership for `{domain}` — full domain comprehension" |
| Incident + unclear service owner | incident-rca → squad-map | Service name + window | "Who owns `{service}`? — need squad for RCA follow-up" |
| Caller wants the full mapping table, not one Slack answer | who-owns-x-bot → squad-map | `workspace_root` | "Map squads for repos in `{workspace}` — org prefix `{org}`, segment `{n}`" |
| Caller wants bounded contexts / domain map, not just ownership | who-owns-x-bot → domain-comprehension | `query` (repo/service name) | "Map bounded contexts and data ownership for `{domain}` — full domain comprehension" |
| `query` names a service mid-incident (surfaced as a suffix line appended to the single reply — a single-shot Slack reply cannot itself switch skills; exact trigger keywords and template: [who-owns-x-bot/reference/slack-format.md § Escalation suffix](../../../who-owns-x-bot/reference/slack-format.md#escalation-suffix-mid-incident-query)) | who-owns-x-bot → incident-rca | Service name from `query` | "RCA for `{service}` — is there an active incident?" |
| Caller wants a one-off ownership lookup, not a tour | new-hire-guide → squad-map | `workspace_root` | "Who owns `{repo}`?" |
| Caller wants the full org-wide domain map, not scoped to one person | new-hire-guide → domain-comprehension | `workspace_root` | "Map bounded contexts and data ownership for `{domain}` — full domain comprehension" |
| Caller wants one MR reviewed, not a release-wide sweep | release-readiness-checker → pr-review | MR !IID + project | "Review MR !{iid} for `{project}`" |
| Caller wants one service's rightsizing question, not a release sweep | release-readiness-checker → k8s-overprovisioning-datadog | Service + env | "Assess rightsizing for `{deployment}` in `{env}`" |
| A flagged service needs the full incident investigation | release-readiness-checker → incident-rca | Service + window (same used for the Phase 1 check) | "RCA for `{service}` `{window}`" |
| Caller wants an interactive, on-demand review instead of the webhook-triggered auto-run | pr-gatekeeper → pr-review | MR !IID + project | "Review MR !{iid} for `{project}`" |
| Caller wants an interactive, on-demand RCA instead of the paging-webhook-triggered triage/postmortem | incident-triage-agent → incident-rca | Service + window | "RCA for `{service}` `{window}`" |
| Caller wants an interactive, on-demand ownership lookup instead of the paging-webhook-triggered flow | incident-triage-agent → squad-map | Service name | "Who owns `{service}`?" |
| Caller wants a single, interactive, on-demand task instead of the scheduled overnight queue sweep | backlog-runner → loop-task-implementer | Task/ticket ID | "Implement `{task_id}`" |
| Security finding in domain analysis (P3b) | domain-comprehension → pr-review | Repo + file path + finding type | "Review MR !{iid} for credential exposure in `{service}`" |
| Architecture smell needs RCA context | domain-comprehension → incident-rca | Service + smell + time window | "RCA for `{service}` {window} — recurring {smell} identified in domain analysis" |
| Domain map reveals overprovisioned service | domain-comprehension → k8s | Service + env from runtime validation | "Assess rightsizing for `{service}` in `{env}` — domain analysis found low utilization" |
| Domain analysis produced `MYSQL_TO_PG_SQL_REWRITES.md` | domain-comprehension → mysql-to-postgres-sql | Comprehension artifact + repo list | "Implement PG rewrites for `{service}` per domain-comprehension artifact" |
| `RISK_MAP.md` § Change risk flags a critical/high-fan-out path with weak `Test signal` | domain-comprehension → unit-test-creator / integration-test-creator (per whether the flagged path is isolated or crosses a real dependency) | `RISK_MAP.md` row (repo/context, risk, fan-out) | "Backfill tests for `{repo/context}` — domain-comprehension's RISK_MAP.md flags weak test signal on a critical path" |
| `BUSINESS_FLOWS.md` documents a journey with no e2e coverage | domain-comprehension → e2e-test-creator | `BUSINESS_FLOWS.md` journey name + entry route | "Write an e2e test for the `{journey}` journey per domain-comprehension's BUSINESS_FLOWS.md" |
| `API_CATALOG.md` documents an endpoint with `exercise: none` | domain-comprehension → api-test-creator | `API_CATALOG.md` row (method, path, implementation) | "Write an API test for `{method} {path}` per domain-comprehension's API_CATALOG.md" |
| Migration MR needs review | mysql-to-postgres-sql → pr-review | Service path + MR !IID | "Review MR !{iid} for MySQL→PostgreSQL migration in `{service}`" |
| Cutover wrong results / outage | mysql-to-postgres-sql → incident-rca | Service + window + shadow diff | "RCA for `{service}` {window} — PG cutover query regression" |
| RCA recommends monitor/alert fix | incident-rca → kubesense-alerts | Monitor query + threshold from RCA | "Create or update alert for `{query}` — RCA `{service}` {window}" |
| RCA needs dashboard for verification | incident-rca → kubesense-dashboards | Metric panels from RCA evidence | "Dashboard for `{service}` post-incident / soak verification" |
| Builder needs an MR reviewed beyond its own lenses | loop-task-implementer → pr-review | MR !IID + task ID | "Review MR !{iid} for task `{task_id}`" |
| Task implementation causes or needs incident investigation | loop-task-implementer → incident-rca | Service + window + task ref | "RCA for `{service}` {window} — regression from task `{task_id}`" |
| Task requires understanding an unfamiliar domain/codebase first | loop-task-implementer → domain-comprehension | Repo/workspace + task ref | "Map domain for `{workspace}` before implementing task `{task_id}`" |
| Task touches MySQL-dialect SQL during a PG migration | loop-task-implementer → mysql-to-postgres-sql | Service + repo | "Scan/rewrite MySQL dialect in `{service}` for task `{task_id}`" |
| Caller wants one workspace's own migration status, not an org-wide rollup | migration-program-manager → mysql-to-postgres-sql | `workspace_root` | "What's the migration status for `{workspace}`?" |
| A workspace in the rollup has no `SQUAD_MAP.md` (services join as `squad: UNKNOWN`) | migration-program-manager → squad-map | `workspace_root` | "Map squads for repos in `{workspace}` — org prefix `{org}`, segment `{n}`" |
| Caller wants one deployment's own rightsizing question, not a sweep | cost-optimization-sprint-planner → k8s-overprovisioning-datadog | Deployment + env | "Assess rightsizing for `{deployment}` in `{env}`" |
| A deployment in the rollup has no `SQUAD_MAP.md`/`ownership.datadog.service_aliases` match | cost-optimization-sprint-planner → squad-map | `workspace_root` | "Map squads for repos in `{workspace}` — org prefix `{org}`, segment `{n}`" |
| Caller wants a fresh single-source migration rollup, not the combined digest | weekly-squad-digest → migration-program-manager | `program_manifest` | "Migration status across all repos" |
| Caller wants a fresh single-source cost/waste sweep, not the combined digest | weekly-squad-digest → cost-optimization-sprint-planner | `sweep_scope` | "Where's the money?" |
| Generated/verified test surfaces a probable production bug (any of the five `*-test-creator` skills) | unit/integration/contract/e2e/api-test-creator → loop-task-implementer | Failing assertion + expected/actual + test file:line | "Fix `{function}` so `{test_file}` passes — {skill} found: {finding}" |
| Generated/verified test surfaces a probable production bug on an MR under review | unit/integration/contract/e2e/api-test-creator → pr-review | Failing assertion + test file:line + MR !IID | "Flag `{finding}` on MR !{iid} — the generated test fails against current behavior" |
| Caller wants the *existing* test suite reviewed for quality, not new tests written | pr-review → test-writer | MR !IID + flagged files with missing/weak coverage | "Write tests for MR !{iid} — missing coverage on `{files}`" |
| Task implementation needs generated tests for a subsystem it just touched | loop-task-implementer → test-writer | Repo/task ref + changed files | "Write tests for task `{task_id}`'s changes in `{repo}`" |
| test-writer classified the request's level (its own dispatch, not a suggestion) | test-writer → unit/integration/contract/e2e/api-test-creator | `target`, `repo_root`, and every other input, passed through unchanged | Not user-facing — an internal dispatch per [skill-routing.md](skill-routing.md); test-writer relays the dispatched skill's own report verbatim |
| Caller wants a real adjacent dependency tested, not a mocked unit | unit-test-creator → integration-test-creator | Target + repo_root | "Write an integration test for `{target}` against a real `{dependency}`" |
| Caller wants the full user journey through the UI, not just the API/service seam | integration-test-creator → e2e-test-creator | Journey description | "Write an e2e test for `{journey}`" |
| Caller wants a consumer/provider interaction agreement, not a live integration test | integration-test-creator → contract-test-creator | Consumer/provider services + interaction | "Write a Pact contract test for `{consumer}` calling `{provider}`" |
| Caller wants a standalone black-box HTTP suite, not an in-process/testcontainers-backed test | integration-test-creator → api-test-creator | Endpoint + repo_root | "Write an API test for `{method} {path}`" |
| Caller wants a black-box request/response suite, not a consumer/provider interaction agreement | contract-test-creator → api-test-creator | Endpoint + repo_root | "Write an API test for `{method} {path}`" |
| Caller wants a consumer/provider interaction agreement, not a standalone black-box suite | api-test-creator → contract-test-creator | Consumer/provider services + interaction | "Write a Pact contract test for `{consumer}` calling `{provider}`" |
| PRD Ready; caller wants implementation | prd-architect → loop-task-implementer | Final PRD + Build Readiness verdict | "Implement `{feature}` per the PRD — task `{prd_title}`" |
| PRD depends on unfamiliar existing system behavior | prd-architect → domain-comprehension | Feature area + workspace root | "Map domain for `{subsystem}` before finalizing PRD for `{feature}`" |
| PRD defines critical paths needing test coverage | prd-architect → test-writer | PRD acceptance criteria + target scope | "Write tests for `{feature}` per PRD section `{section}`" |
| PRD security finding needs review of existing code on an MR | prd-architect → pr-review | MR !IID + finding | "Review MR !{iid} for `{finding}` flagged during PRD review" |
| Task needs a PRD before implementation | loop-task-implementer → prd-architect | Task description + constraints | "Write an implementation-ready PRD for task `{task_id}`" |
| Domain map suggests a new product initiative | domain-comprehension → prd-architect | Bounded context + problem statement | "Write a PRD for `{initiative}` based on domain-comprehension findings" |
| PRD needs an architecture decision before implementation | prd-architect → architecture-review | Final PRD | "Architecture review for `{feature}` before implementation" |
| Architecture decision approved, needs implementation-level design | architecture-review → system-design | Architecture decision + PRD | "Design the implementation for `{feature}` per the approved architecture decision" |
| Architecture decision approved and ready to build | architecture-review → loop-task-implementer | Architecture decision | "Implement `{feature}` per the approved architecture decision" |
| A specific security/trust-boundary concern needs a deep audit | architecture-review → security-review | Architecture decision + trust-boundary concern | "Security review of `{concern}` — trust-boundary concern found during architecture review" |
| The PRD itself has gaps, not the architecture | architecture-review → prd-architect | PRD gap found during architecture review | "Revise the PRD for `{feature}` — architecture review found `{gap}`" |
| System design defines an API surface needing contract review | system-design → api-design-review | API surface from design spec | "Review the API design for `{feature}`" |
| System design defines a data model needing schema review | system-design → database-review | Data model from design spec | "Review the database schema for `{feature}`" |
| System design ready, needs an observability plan review | system-design → observability-review | Observability plan from design spec | "Review observability coverage for `{feature}`" |
| API design finding looks exploitable | api-design-review → security-review | Endpoint + authorization gap | "Security review of `{endpoint}` — authorization gap found in API design review" |
| Review request is actually a MySQL→Postgres dialect migration, not a general schema review | database-review → mysql-to-postgres-sql | Schema/query findings + service path | "Scan/rewrite MySQL dialect in `{service}` — flagged as a PG migration during schema review" |
| Reviewing one MR's migration, not a standalone schema review | database-review → pr-review | MR !IID + schema/migration findings | "Review MR !{iid} for the schema/migration change found during database review" |
| Database review finding suggests a broader performance problem | database-review → performance-review | Query/index finding | "Performance review of `{service}` — {finding} found in database review" |
| Security-sensitive finding on an MR under review | pr-review → security-review | MR !IID + finding | "Security review of `{finding}` flagged on MR !{iid}" |
| Vulnerable dependency is the root cause of a security finding | security-review → dependency-upgrade-review | Dependency + CVE | "Review upgrade path for `{dependency}` — CVE `{cve_id}` found during security review" |
| Upgrade CVE looks exploitable in this codebase's actual usage | dependency-upgrade-review → security-review | Dependency + CVE | "Security review of `{dependency}` usage — CVE `{cve_id}` may be exploitable" |
| Performance finding means the service needs re-forecasted capacity | performance-review → capacity-planner | Service + finding | "Forecast capacity for `{service}` — {finding} found during performance review" |
| Capacity forecast should be checked against live rightsizing data | capacity-planner → k8s-overprovisioning-datadog | Service + forecast | "Assess rightsizing for `{deployment}` in `{env}` against forecasted capacity" |
| Observability gap directly explains slow incident detection | observability-review → incident-rca | Service + gap | "RCA for `{service}` `{window}` — observability gap may have delayed detection" |
| Gaps found ahead of an upcoming release | observability-review → deployment-risk-review | Service + gap list + release date | "Assess deployment risk for `{service}` — observability gaps found ahead of release" |
| Caller wants the full multi-repo release go/no-go sweep, not one change | deployment-risk-review → release-readiness-checker | Release manifest | "Is this release ready to ship?" |
| Deploy already happened and something broke | deployment-risk-review → incident-triage-agent | Service + change | "Triage `{service}` — deploy-related incident after {change}" |
| A "Now" priority debt item is really a multi-service migration | tech-debt-assessor → migration-program-manager | Debt item + affected repos | "Plan migration for `{item}` across `{repos}`" |
| A "Now" priority debt item is really a resource/cost problem | tech-debt-assessor → cost-optimization-sprint-planner | Debt item + affected services | "Cost sweep for `{services}` — {item} flagged as a resource problem" |

Skill-specific rows in each `SKILL.md` MUST be a subset of this table plus local deltas only.

## 2. Reverse escalations

| After skill completes | Next action | User prompt template |
|-----------------------|-------------|----------------------|
| k8s recommends Ready cut applied | Re-run k8s in **7d** (PostChangeVerification) | "Re-run rightsizing assessment for `{deployment}` `{env}` — 7d post-change verification" |
| incident-rca ranks `deploy_regression` HIGH | pr-review on identified MR | "Review MR !{iid} for deploy regression tied to `{service}` outage {window}" |
| pr-review flags underprovisioned resources | k8s assessment before merge | "Assess rightsizing for `{deployment}` in `{env}` before merging MR !{iid}" |
| pr-review finds critical security in deployed code | incident-rca on incident window (if outage) | "RCA for `{service}` {window} — security finding PRR-{id} in MR !{iid}" |
| incident-rca finds `configuration_change` + code MR | pr-review on code MR if not yet reviewed | "Review MR !{iid} — config spike + code change in `{service}` window" |
| k8s assessment during active incident | incident-rca if not already run | "RCA for `{service}` {window} — correlate with k8s OBS findings" |
| domain-comprehension P3b flags security issue | pr-review on affected MR/repo | "Review MR !{iid} for `{finding_type}` in `{service}` — flagged during domain analysis" |
| domain-comprehension completes P5 | squad-map refresh if ownership changed | "Refresh squad map — domain comprehension found new services in `{workspace}`" |
| PG cutover regression confirmed in RCA | mysql-to-postgres-sql audit on failing query | "Audit native SQL in `{service}` for PG semantic mismatch — RCA found query regression" |
| pr-review approves a mysql-to-postgres-sql migration MR | mysql-to-postgres-sql marks that repo's rewrites complete in `MIGRATION_STATUS.yaml` | "Mark `{repo}` migration complete — MR !{iid} for MySQL→PostgreSQL rewrites merged" |
| mysql-to-postgres-sql completes rewrites from a domain-comprehension handoff artifact | domain-comprehension records the outcome (e.g. `PROGRESS.md`) | "Record MySQL→PG rewrite completion for `{service}` in domain comprehension progress" |
| pr-review approves a loop-task-implementer task MR | loop-task-implementer resumes and selects the next task | "Continue loop-task-implementer — MR !{iid} merged, select next task" |
| mysql-to-postgres-sql completes rewrites for a loop-task-implementer task's repo | loop-task-implementer resumes remediation/verification for that task | "Continue task `{task_id}` — PG rewrites applied to `{repo}`" |
| incident-rca confirms a regression tied to a task branch | loop-task-implementer dispatches Builder remediation | "Dispatch Builder remediation for task `{task_id}` — RCA confirmed regression {window}" |
| squad-map resolves the owning team for an incident | incident-rca resumes with squad context (e.g. paging, ownership-scoped evidence) | "Resume RCA for `{service}` {window} — owning squad is `{squad}`" |
| incident-rca links a recurring architecture smell to a service | domain-comprehension re-run or update on that bounded context | "Update domain analysis for `{service}` — RCA found recurring {smell} across {n} incidents" |
| k8s confirms a service is overprovisioned per domain-comprehension's referral | domain-comprehension records the outcome in its runtime-validation section | "Record k8s rightsizing outcome for `{service}` in domain comprehension runtime validation" |
| domain-comprehension identifies implementation work loop-task-implementer should carry out | loop-task-implementer picks up the resulting task(s) | "Implement `{task_id}` per domain-comprehension findings for `{workspace}`" |

## 3. Handoff block (required fields)

Paste into chat from `report-template.md` anchors or generate inline:

```markdown
**Handoff → <skill>**
- Service: `<name>`
- Env: `<env>`
- Window: `<from>` – `<to>` (UTC)
- Trigger: `<hypothesis or finding>`
- Evidence: <links, MR !IID, metric queries>
- Ask: "<one-line user prompt>"
```

Confidence at handoff: use categorical band from [confidence-bands.md](confidence-bands.md); receiving skill recomputes per its own rules.

### domain-comprehension → mysql-to-postgres-sql (artifact)

When `MYSQL_TO_PG_SQL_REWRITES.md` exists in the workspace deliverable directory:

```markdown
**Handoff → mysql-to-postgres-sql**
- Artifact: `<workspace>/<deliverable_dir>/MYSQL_TO_PG_SQL_REWRITES.md`
- Service: `<primary service from artifact header>`
- Repos: `<paths listed in artifact>`
- Risk tier focus: P0 / P1 (from artifact tables)
- Ask: "Implement PG rewrites for `{service}` per domain-comprehension MYSQL_TO_PG_SQL_REWRITES.md"
```

## 4. When NOT to escalate

| User request | Correct skill |
|--------------|---------------|
| Size K8s deployment / rightsizing | k8s-overprovisioning-datadog |
| Review GitLab MR (interactive, conversational) | pr-review |
| Automated, unattended review on every push (webhook-triggered) | pr-gatekeeper |
| Post-incident RCA / root cause (interactive, conversational) | incident-rca |
| PagerDuty/Opsgenie page-fire or incident-resolved webhook (unattended) | incident-triage-agent |
| Squad / repo ownership mapping (interactive, conversational) | squad-map |
| Single-shot automated ownership lookup (Slack `/who-owns` slash command) | who-owns-x-bot |
| New-hire onboarding tour scoped to one person's repos | new-hire-guide |
| Release go/no-go report across MRs/services since last release | release-readiness-checker |
| Domain / subsystem map, bounded contexts, data ownership | domain-comprehension |
| MySQL scrub / native SQL PG migration / jdbc:postgresql cutover | mysql-to-postgres-sql |
| Org-wide migration status rollup across many workspaces/squads | migration-program-manager |
| Org-wide cost/waste ranking sweep across many deployments/squads | cost-optimization-sprint-planner |
| Combined weekly squad digest across both migration and cost rollups | weekly-squad-digest |
| Autonomous multi-task implement → review → remediate → PR loop (interactive, human-driven) | loop-task-implementer |
| Scheduled overnight ticket-queue sweep (unattended) | backlog-runner |
| Write / generate / backfill automated tests, level unspecified | test-writer (dispatches to one of the five below) |
| Unit tests — isolated, mocked externals | unit-test-creator directly |
| Integration tests — real adjacent dependency | integration-test-creator directly |
| Consumer-driven contract / Pact tests | contract-test-creator directly |
| E2E / browser user-journey tests | e2e-test-creator directly |
| Black-box API tests — Postman/Newman, no browser | api-test-creator directly |
| Live rollback / kubectl apply | Out of scope — human operator |
| Security-only deep review | security-review |
| Cost/billing investigation across services | Canvas + appropriate skill; not auto-routed |

See each skill's **when NOT to use** table in `SKILL.md`.

## 5. Canvas hint

Use [canvas skill](~/.cursor/skills-cursor/canvas/SKILL.md) when the deliverable is multi-tabular, timeline-heavy, or benefits from interactive layout. Chat markdown suffices for single MR summary or short RCA.

| Skill | Canvas when | Chat suffices when |
|-------|-------------|---------------------|
| incident-rca | Multi-service timeline, hypothesis score comparison, correlation across 3+ services | Single-service RCA with ≤2 hypotheses |
| k8s | Cost/waste table, decision graph summary, namespace ranking across deployments | Single deployment Human Report |
| pr-review | Finding severity distribution, dimension scores heatmap, large MR finding map | Single MR executive summary |
| domain-comprehension | Multi-repo dependency graph, bounded context map, data ownership matrix | Single-repo orientation or quick five-questions summary |
| squad-map | Multi-repo ownership table, conflict matrix across squads | Single-repo ownership lookup |
| mysql-to-postgres-sql | Multi-service migration status table, scan hit matrix across repos | Single-service scan + rewrite summary |

Trigger phrases: "show in canvas", billing/timeline investigations, or when user has canvas open beside chat.
