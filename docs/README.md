# Documentation index

Human-readable guide to everything in the **software-builder** repository. Agent instructions live in each skill's
`SKILL.md`; this index explains what each piece is for and where to look.

## Start here

| Document | What it is |
|----------|------------|
| [../CONTEXT.md](../CONTEXT.md) | Domain glossary — platform vocabulary (skills, hosts, composition, evidence) |
| [../CONTEXT-MAP.md](../CONTEXT-MAP.md) | Platform vs target-system context map |
| [../domain-comprehension/CONTEXT.md](../domain-comprehension/CONTEXT.md) | Target-system vocabulary (bounded contexts, as-built PRD, squads) |
| [../README.md](../README.md) | Install, invoke, and quick usage for all skills |
| [REPOSITORY.md](REPOSITORY.md) | Repo layout, `Makefile`, `scripts/`, lint targets, git hooks |
| [skill-framework/README.md](skill-framework/README.md) | Shared normative conventions every skill follows (confidence bands, escalation, routing, phase glossary, …) |
| [history/README.md](history/README.md) | Historical specs and plans (`docs/superpowers/`) vs. normative framework docs |
| [adr/README.md](adr/README.md) | Platform architecture decision records |
| [../scripts/README.md](../scripts/README.md) | What `scripts/install.sh` does |
| [../CHANGELOG.md](../CHANGELOG.md) | Per-skill change history (replaces stale inline "Recent changes" in SKILL files) |

## Skills (what each one does)

Each skill is a self-contained directory copied to `~/.cursor/skills/<name>/` on install. The agent reads
`SKILL.md` at runtime; humans should start with the skill `README.md`.

| Skill | Human overview | Agent entry | Setup |
|-------|----------------|-------------|-------|
| **pr-review** | [pr-review/README.md](../pr-review/README.md) | [pr-review/SKILL.md](../pr-review/SKILL.md) | [pr-review/SETUP.md](../pr-review/SETUP.md) |
| **pr-gatekeeper** | [pr-gatekeeper/README.md](../pr-gatekeeper/README.md) | [pr-gatekeeper/SKILL.md](../pr-gatekeeper/SKILL.md) | [pr-gatekeeper/SETUP.md](../pr-gatekeeper/SETUP.md) |
| **incident-rca** | [incident-rca/README.md](../incident-rca/README.md) | [incident-rca/SKILL.md](../incident-rca/SKILL.md) | [incident-rca/SETUP.md](../incident-rca/SETUP.md) |
| **incident-triage-agent** | [incident-triage-agent/README.md](../incident-triage-agent/README.md) | [incident-triage-agent/SKILL.md](../incident-triage-agent/SKILL.md) | [incident-triage-agent/SETUP.md](../incident-triage-agent/SETUP.md) |
| **k8s-overprovisioning-datadog** | [k8s-overprovisioning-datadog/README.md](../k8s-overprovisioning-datadog/README.md) | [k8s-overprovisioning-datadog/SKILL.md](../k8s-overprovisioning-datadog/SKILL.md) | [k8s-overprovisioning-datadog/SETUP.md](../k8s-overprovisioning-datadog/SETUP.md) |
| **domain-comprehension** | [domain-comprehension/README.md](../domain-comprehension/README.md) | [domain-comprehension/SKILL.md](../domain-comprehension/SKILL.md) | [domain-comprehension/SETUP.md](../domain-comprehension/SETUP.md) |
| **squad-map** | [squad-map/README.md](../squad-map/README.md) | [squad-map/SKILL.md](../squad-map/SKILL.md) | [squad-map/SETUP.md](../squad-map/SETUP.md) |
| **who-owns-x-bot** | [who-owns-x-bot/README.md](../who-owns-x-bot/README.md) | [who-owns-x-bot/SKILL.md](../who-owns-x-bot/SKILL.md) | [who-owns-x-bot/SETUP.md](../who-owns-x-bot/SETUP.md) |
| **new-hire-guide** | [new-hire-guide/README.md](../new-hire-guide/README.md) | [new-hire-guide/SKILL.md](../new-hire-guide/SKILL.md) | [new-hire-guide/SETUP.md](../new-hire-guide/SETUP.md) |
| **release-readiness-checker** | [release-readiness-checker/README.md](../release-readiness-checker/README.md) | [release-readiness-checker/SKILL.md](../release-readiness-checker/SKILL.md) | [release-readiness-checker/SETUP.md](../release-readiness-checker/SETUP.md) |
| **migration-program-manager** | [migration-program-manager/README.md](../migration-program-manager/README.md) | [migration-program-manager/SKILL.md](../migration-program-manager/SKILL.md) | [migration-program-manager/SETUP.md](../migration-program-manager/SETUP.md) |
| **cost-optimization-sprint-planner** | [cost-optimization-sprint-planner/README.md](../cost-optimization-sprint-planner/README.md) | [cost-optimization-sprint-planner/SKILL.md](../cost-optimization-sprint-planner/SKILL.md) | [cost-optimization-sprint-planner/SETUP.md](../cost-optimization-sprint-planner/SETUP.md) |
| **mysql-to-postgres-sql** | [mysql-to-postgres-sql/README.md](../mysql-to-postgres-sql/README.md) | [mysql-to-postgres-sql/SKILL.md](../mysql-to-postgres-sql/SKILL.md) | [mysql-to-postgres-sql/SETUP.md](../mysql-to-postgres-sql/SETUP.md) |
| **loop-task-implementer** | [loop-task-implementer/README.md](../loop-task-implementer/README.md) | [loop-task-implementer/SKILL.md](../loop-task-implementer/SKILL.md) | [loop-task-implementer/SETUP.md](../loop-task-implementer/SETUP.md) |
| **backlog-runner** | [backlog-runner/README.md](../backlog-runner/README.md) | [backlog-runner/SKILL.md](../backlog-runner/SKILL.md) | [backlog-runner/SETUP.md](../backlog-runner/SETUP.md) |
| **weekly-squad-digest** | [weekly-squad-digest/README.md](../weekly-squad-digest/README.md) | [weekly-squad-digest/SKILL.md](../weekly-squad-digest/SKILL.md) | [weekly-squad-digest/SETUP.md](../weekly-squad-digest/SETUP.md) |
| **test-writer** | [test-writer/README.md](../test-writer/README.md) | [test-writer/SKILL.md](../test-writer/SKILL.md) | [test-writer/SETUP.md](../test-writer/SETUP.md) |
| **unit-test-creator** | [unit-test-creator/README.md](../unit-test-creator/README.md) | [unit-test-creator/SKILL.md](../unit-test-creator/SKILL.md) | [unit-test-creator/SETUP.md](../unit-test-creator/SETUP.md) |
| **integration-test-creator** | [integration-test-creator/README.md](../integration-test-creator/README.md) | [integration-test-creator/SKILL.md](../integration-test-creator/SKILL.md) | [integration-test-creator/SETUP.md](../integration-test-creator/SETUP.md) |
| **contract-test-creator** | [contract-test-creator/README.md](../contract-test-creator/README.md) | [contract-test-creator/SKILL.md](../contract-test-creator/SKILL.md) | [contract-test-creator/SETUP.md](../contract-test-creator/SETUP.md) |
| **e2e-test-creator** | [e2e-test-creator/README.md](../e2e-test-creator/README.md) | [e2e-test-creator/SKILL.md](../e2e-test-creator/SKILL.md) | [e2e-test-creator/SETUP.md](../e2e-test-creator/SETUP.md) |
| **api-test-creator** | [api-test-creator/README.md](../api-test-creator/README.md) | [api-test-creator/SKILL.md](../api-test-creator/SKILL.md) | [api-test-creator/SETUP.md](../api-test-creator/SETUP.md) |

A one-line "invoke / does" summary of every skill is in root [README.md § Skills](../README.md#skills) —
not repeated here to avoid two independently-maintained copies drifting apart.

## Cross-skill routing

Skills reference each other when a finding belongs in another workflow:

| From | Trigger | Next skill |
|------|---------|------------|
| pr-review | Critical security finding tied to a deployed incident | incident-rca |
| pr-review | Large perf regression in K8s manifests | k8s-overprovisioning-datadog |
| k8s-overprovisioning | OOM / crashloop in analysis window | incident-rca |
| k8s-overprovisioning | Utilization spike after a deploy | pr-review on the causative MR |
| incident-rca | "Is deployment overprovisioned?" | k8s-overprovisioning-datadog |
| incident-rca | "Review the MR" | pr-review |
| domain-comprehension | Incident / outage in a time window | incident-rca |
| domain-comprehension | "Review this MR" | pr-review |
| incident-rca / pr-review | "How does this domain work?" / onboarding | domain-comprehension |
| domain-comprehension | Squad / repo ownership only | squad-map |
| squad-map | Full domain map / bounded contexts | domain-comprehension |
| incident-rca | Unclear service owner during RCA | squad-map |
| incident-triage-agent | Caller wants an interactive, on-demand RCA or ownership lookup | incident-rca / squad-map |
| who-owns-x-bot | Caller wants the full mapping table, not one answer | squad-map |
| who-owns-x-bot | Caller wants bounded contexts / domain map | domain-comprehension |
| new-hire-guide | Caller wants a one-off ownership lookup, not a tour | squad-map |
| new-hire-guide | Caller wants the full org-wide domain map, not scoped to one person | domain-comprehension |
| release-readiness-checker | Caller wants one MR reviewed, not a release-wide sweep | pr-review |
| release-readiness-checker | Caller wants one service's rightsizing question, not a release sweep | k8s-overprovisioning-datadog |
| release-readiness-checker | A flagged service needs the full incident investigation | incident-rca |
| migration-program-manager | Caller wants one workspace's own migration status, not the org-wide rollup | mysql-to-postgres-sql |
| migration-program-manager | A workspace has no SQUAD_MAP.md — services join as UNKNOWN | squad-map |
| cost-optimization-sprint-planner | Caller wants one deployment's own rightsizing question, not a sweep | k8s-overprovisioning-datadog |
| cost-optimization-sprint-planner | A deployment has no SQUAD_MAP.md/service-alias match — joins as UNKNOWN | squad-map |
| domain-comprehension | Produced `MYSQL_TO_PG_SQL_REWRITES.md` | mysql-to-postgres-sql |
| mysql-to-postgres-sql | Migration MR needs review | pr-review |
| mysql-to-postgres-sql | Cutover regression / wrong query results | incident-rca |
| loop-task-implementer | Task's MR needs review beyond its own lenses | pr-review |
| pr-gatekeeper | Caller wants an interactive, on-demand review | pr-review |
| loop-task-implementer | Task implementation causes/needs incident investigation | incident-rca |
| loop-task-implementer | Task needs unfamiliar-codebase context first | domain-comprehension |
| loop-task-implementer | Task touches MySQL-dialect SQL during a PG migration | mysql-to-postgres-sql |
| backlog-runner | Caller wants a single, interactive, on-demand task | loop-task-implementer |
| weekly-squad-digest | Caller wants a fresh single-source rollup, not the combined digest | migration-program-manager / cost-optimization-sprint-planner |
| unit-test-creator / integration-test-creator / contract-test-creator / e2e-test-creator / api-test-creator | A generated test surfaces a probable production bug | loop-task-implementer (fix) / pr-review (flag on the MR) |
| pr-review | Missing/weak test coverage on the reviewed MR | test-writer |
| loop-task-implementer | Task's changes need generated tests | test-writer |
| test-writer | Request classified into a level | unit-test-creator / integration-test-creator / contract-test-creator / e2e-test-creator / api-test-creator (exactly one) |
| unit-test-creator | Target needs a real adjacent dependency, not a mock | integration-test-creator |
| integration-test-creator | Caller wants the full UI journey, not just the seam | e2e-test-creator |
| integration-test-creator | Caller wants a consumer/provider agreement, not a live integration test | contract-test-creator |
| integration-test-creator / contract-test-creator | Caller wants a standalone black-box HTTP suite | api-test-creator |
| api-test-creator | Caller wants a consumer/provider interaction agreement, not a standalone suite | contract-test-creator |

Full symmetric matrix (forward + reverse escalations):
[docs/skill-framework/shared/cross-skill-escalation.md](skill-framework/shared/cross-skill-escalation.md).

## Design specs (internal)

| File | What it is |
|------|------------|
| [superpowers/specs/2026-06-29-pr-review-governance-design.md](superpowers/specs/2026-06-29-pr-review-governance-design.md) | pr-review v1.4 governance: finding pipeline, phase contracts, lazy-load rules |
| [superpowers/specs/2026-06-29-pr-review-architecture-lens-design.md](superpowers/specs/2026-06-29-pr-review-architecture-lens-design.md) | Architecture lens (§16) triggers and heuristics for MR reviews |
| [superpowers/specs/2026-07-02-skills-roadmap-design.md](superpowers/specs/2026-07-02-skills-roadmap-design.md) | Repo hygiene + incident-rca causal-graph determinism roadmap |
| [superpowers/specs/2026-07-02-platform-evolution-strategy-design.md](superpowers/specs/2026-07-02-platform-evolution-strategy-design.md) | 12–24 month platform evolution strategy: maturity assessment, eval harness, distribution, roadmap |
| [superpowers/plans/2026-08-05-team-facing-agents-roadmap.md](superpowers/plans/2026-08-05-team-facing-agents-roadmap.md) | Team-facing agents brainstorm: 11 candidate bots/jobs composing the 7 skills for real team workflows |
| [superpowers/specs/2026-08-05-who-owns-x-bot-design.md](superpowers/specs/2026-08-05-who-owns-x-bot-design.md) | who-owns-x-bot design — item #1 of the team-facing agents roadmap |
| [superpowers/specs/2026-08-05-pr-gatekeeper-design.md](superpowers/specs/2026-08-05-pr-gatekeeper-design.md) | pr-gatekeeper design — item #2 of the team-facing agents roadmap |
| [superpowers/specs/2026-08-05-incident-triage-agent-design.md](superpowers/specs/2026-08-05-incident-triage-agent-design.md) | incident-triage-agent design — items #3+#4 of the team-facing agents roadmap |
| [superpowers/specs/2026-08-05-org-rollup-aggregation-layer-design.md](superpowers/specs/2026-08-05-org-rollup-aggregation-layer-design.md) | Shared cross-repo aggregation layer design — implemented by items #8, #10, and #11 |
| [superpowers/specs/2026-08-05-backlog-runner-design.md](superpowers/specs/2026-08-05-backlog-runner-design.md) | backlog-runner design — item #7 of the team-facing agents roadmap |
| [superpowers/specs/2026-08-05-domain-comprehension-proposal-check-mode-design.md](superpowers/specs/2026-08-05-domain-comprehension-proposal-check-mode-design.md) | domain-comprehension `PROPOSAL_CHECK` mode design — item #6 of the team-facing agents roadmap (a mode addition, not a new skill) |
| [superpowers/specs/2026-08-05-new-hire-guide-design.md](superpowers/specs/2026-08-05-new-hire-guide-design.md) | new-hire-guide design — item #5 of the team-facing agents roadmap |
| [superpowers/specs/2026-08-05-release-readiness-checker-design.md](superpowers/specs/2026-08-05-release-readiness-checker-design.md) | release-readiness-checker design — item #9 of the team-facing agents roadmap |
| [superpowers/specs/2026-08-05-migration-program-manager-design.md](superpowers/specs/2026-08-05-migration-program-manager-design.md) | migration-program-manager design — item #8 of the team-facing agents roadmap |
| [superpowers/specs/2026-08-05-cost-optimization-sprint-planner-design.md](superpowers/specs/2026-08-05-cost-optimization-sprint-planner-design.md) | cost-optimization-sprint-planner design — item #10 of the team-facing agents roadmap |
| [superpowers/specs/2026-08-05-weekly-squad-digest-design.md](superpowers/specs/2026-08-05-weekly-squad-digest-design.md) | weekly-squad-digest design — item #11 of the team-facing agents roadmap (the last item) |

These are planning artifacts; the live behavior is defined in each skill's own `SKILL.md` and `reference/`.

## pr-review file map

| Path | What it does |
|------|--------------|
| `workflow/inputs.md` | Resolve MR from URL, `!IID`, or current branch; list open MRs |
| `workflow/phase-0.md` | Detect GitLab MCP posting mode (`full`, `summary-only`, `general-only`, `chat-only`) |
| `workflow/phase-1.md` | Fetch MR metadata, paginated diff, CI, Jira AC, review boundary |
| `workflow/phase-2.md` | Run checklist dimensions, finding pipeline, stop-search cap |
| `workflow/phase-2-3-gate.md` | Block noise posts (nits-only, zero findings) |
| `workflow/posting.md` | Confirm with user, post inline threads + summary note |
| `workflow/phase-5.md` | Executive summary, optional Jira write-back |
| `reference/finding-pipeline.md` | Detect → evidence → don't-guess → severity → emit order |
| `reference/severity-rubric.md` | L×I matrix, merge verdict, stop-search thresholds |
| `reference/comment-templates.md` | GitLab summary and re-review note templates |
| `reference/incremental-rerun.md` | Re-review dedupe, regression check, Phase 5 output checklist |
| `scripts/diff-to-positions.py` | Map diff hunks to GitLab inline comment positions |
| `tests/test_diff_to_positions.py` | Pytest suite for the position helper |
| `examples/review-rules.yaml` | Starter template for per-repo review overrides |

## pr-gatekeeper file map

| Path | What it does |
|------|--------------|
| `workflow/inputs.md` | Webhook event filtering, `head_sha` dedupe short-circuit |
| `workflow/gatekeep.md` | Invoke pr-review, apply auto-post-policy, route notification |
| `reference/auto-post-policy.md` | The two-message protocol reconciling unattended runs with pr-review's Phase 3 gate |
| `reference/smoke-test.md` | Post-install validation steps |

## incident-rca file map

| Path | What it does |
|------|--------------|
| `reference/query-playbook.md` | Per-source Datadog/KubeSense/GitLab/Jenkins/Jira query recipes |
| `reference/mcp-capabilities.md` | Connected-server detection, degraded modes |
| `reference/manual-scoring.md` | Hypothesis weights when the optional correlator CLI is absent |
| `reference/evidence.example.json` | Canonical evidence bundle shape (`schema_version: 4`; see [evidence-schema.md](../incident-rca/reference/evidence-schema.md)) |
| `report-template.md` | Output sections and quality checklist |
| `reference/smoke-test.md` | Post-install validation steps |

## incident-triage-agent file map

| Path | What it does |
|------|--------------|
| `workflow/inputs.md` | Parse paging webhook payload, select Triage/Postmortem mode |
| `workflow/triage.md` | Fast 30-min-window incident-rca + squad-map → triage doc |
| `workflow/postmortem.md` | Full-window incident-rca + squad-map → postmortem draft |
| `reference/unattended-gate-policy.md` | Exhaustive incident-rca + squad-map blocking-gate answers |
| `reference/triage-doc-format.md`, `reference/postmortem-format.md` | Output shape for each mode |

## squad-map file map

| Path | What it does |
|------|--------------|
| `workflow/inputs.md` | Workspace root, repo list, config resolution |
| `workflow/phase-0.md` | MCP capability check + profile line |
| `workflow/phase-1.md` | GitLab + Datadog mapping, CODEOWNERS fallback |
| `reference/squad-mapping.md` | Reconciliation rules, GitLab/Datadog mapping |
| `reference/config-schema.md` | `squad-map-config.yaml` / `domain-config.yaml` ownership block |
| `templates/SQUAD_MAP.md` | Deliverable template |
| `reference/smoke-test.md` | Post-install validation steps |

## who-owns-x-bot file map

| Path | What it does |
|------|--------------|
| `workflow/inputs.md` | Parse `query` + optional `workspace_root`; HARD STOP on empty query |
| `workflow/lookup.md` | Delegate to squad-map, classify Resolved/Ambiguous/Unknown |
| `reference/slack-format.md` | Normative three-shape Slack reply spec |
| `reference/smoke-test.md` | Post-install validation steps |

## new-hire-guide file map

| Path | What it does |
|------|--------------|
| `workflow/inputs.md` | Parse `new_hire` (name, squad) + `workspace_root` + `delivery_mode`; HARD STOP on missing required fields |
| `workflow/run-tour.md` | Resolve squad → repos via squad-map, invoke domain-comprehension **unscoped**, curate `ONBOARDING_TOUR.md` |
| `reference/tour-format.md` | Normative `ONBOARDING_TOUR.md` structure |
| `reference/smoke-test.md` | Post-install validation steps |

## release-readiness-checker file map

| Path | What it does |
|------|--------------|
| `workflow/inputs.md` | Parse `release_manifest` + `incident_lookback_hours` + `target_branch`; HARD STOP on empty manifest |
| `workflow/run-check.md` | Resolve MR ranges (paginated), invoke pr-review / k8s / incident-rca per manifest entry per gate-policy.md, aggregate |
| `reference/gate-policy.md` | Normative gate answers for all three wrapped skills: pr-review (reuses pr-gatekeeper's policy), k8s (ambiguous-service ask), incident-rca (Phase 1 checkpoint, "stop here" every signal density) |
| `reference/report-format.md` | Normative `RELEASE_READINESS_REPORT.md` structure + verdict derivation |
| `reference/smoke-test.md` | Post-install validation steps |

## migration-program-manager file map

| Path | What it does |
|------|--------------|
| `workflow/inputs.md` | Parse `program_manifest` + `staleness_threshold_days` + `state_path`; HARD STOP on missing required fields |
| `workflow/run-rollup.md` | Invoke the aggregator script, rank/group by squad, build the report + rollup JSON |
| `scripts/aggregate_migration_status.py` | Parse `MIGRATION_STATUS.yaml` × N + `SQUAD_MAP.md`, join, compute staleness against persisted state |
| `reference/report-format.md` | Normative `MIGRATION_PROGRAM_REPORT.md` + `migration_program_rollup.json` structure |
| `reference/smoke-test.md` | Post-install validation steps |

## cost-optimization-sprint-planner file map

| Path | What it does |
|------|--------------|
| `workflow/inputs.md` | Parse `sweep_scope` + `cost_rate` + `max_deployments_per_run`/`deadline`/`session_token_budget`; HARD STOP on missing required fields |
| `workflow/run-sweep.md` | Optional namespace pre-filter, loop k8s-overprovisioning-datadog per deployment, join, rank, render |
| `reference/gate-policy.md` | Every live k8s-overprovisioning-datadog gate and its scripted, reused answer; cost-rate resolved once, sweep-wide |
| `reference/sweep-policy.md` | The sweep loop's own session-level state, candidate-list construction, failure isolation, stop conditions |
| `reference/report-format.md` | Normative `COST_OPTIMIZATION_SPRINT_REPORT.md` + `cost_optimization_sprint_rollup.json` structure |
| `reference/smoke-test.md` | Post-install validation steps |

## weekly-squad-digest file map

| Path | What it does |
|------|--------------|
| `workflow/inputs.md` | Parse `rollup_manifest` + `staleness_warning_days`; HARD STOP if neither rollup path is set |
| `workflow/run-digest.md` | Read both rollups, group by squad then `metric_type`, compute staleness, render |
| `reference/report-format.md` | Normative `WEEKLY_SQUAD_DIGEST.md` structure |
| `reference/smoke-test.md` | Post-install validation steps |

## mysql-to-postgres-sql file map

| Path | What it does |
|------|--------------|
| `workflow/migrate-service.md` | Per-service inventory → scan → rewrite → config → verify → merge gate |
| `reference/function-translations.md` | MySQL → PostgreSQL function mapping + cooling-period pattern |
| `reference/collection-domain-files.md` | Redirect stub — old link target, now points to `domain-packs/collection.md` |
| `reference/domain-packs/README.md` | Domain-pack index — when to load one, how to author one |
| `reference/domain-packs/collection.md` | Worked-example domain pack: `collection` workspace P0/P1 file list |
| `reference/domain-packs/TEMPLATE.md` | Blank domain-pack skeleton for a new workspace/org |
| `reference/org-migration-gaps.md` | Coverage map vs ARCH Confluence wiki |
| `reference/timestamp-handling.md` | `ON UPDATE CURRENT_TIMESTAMP` + 14 custom column tables |
| `reference/data-type-mapping.md` | Type mapping, ENUM, boolean, UNSIGNED |
| `reference/case-sensitivity.md` | Email/PAN/IFSC conventions on PG |
| `reference/nodejs-migration.md` | Node.js: mysql2→pg, Sequelize, TypeORM, Knex, Prisma |
| `reference/python-migration.md` | Python: SQLAlchemy `pool_recycle`, Django, engine setup |
| `reference/spring-datasource-example.yaml` | ARCH wiki §6 Spring/Hikari YAML |
| `reference/migration-prompts.md` | Pointer to ARCH Confluence migration prompts |
| `reference/shadow-migration.md` | Dual-run, feature flags, partial fleet, rollback |
| `reference/lazy-load-index.md` | On-demand reference loading |
| `reference/collection-checklist-refresh.md` | Regenerate collection hit list from scan |
| `reference/migration-edge-cases.md` | Translation caveats, scan limits, OAuth, isolation, sql_mode |
| `scripts/scan-report.sh` | Report-only scan (always exit 0) |
| `scripts/scan-mysql-dialect.sh` | ripgrep gate — `.java`, `.php`, `.sql`, `.py`, `.js`, `.ts` |
| `reference/smoke-test.md` | Post-install validation steps |
| `reference/skill-contract.md` | Non-negotiable agent contract (load with SKILL.md) |
| `reference/calibration-snippets.md` | P0/JPQL/gate few-shots for rewrite step |
| `reference/pressure-tests.md` | Maintainer regression scenarios |
| `examples.md` | Invocation table + golden scenarios |
| `templates/SERVICE_PG_MIGRATION.md` | Per-service migration deliverable |
| `tests/fixtures/mysql-dialect/` | Scan gate fixture (hits fail / clean pass) |

## domain-comprehension file map

| Path | What it does |
|------|--------------|
| `workflow/inputs.md` | Delivery mode (`FULL` / `RESUME` / `DELTA` / `COMPLIANCE_RETROFIT`), parameter intake |
| `workflow/session-0.md` … `phase-5.md` | Session 0 → P0…P5 comprehension phases, one file per phase |
| `reference/phase-outputs.md` | Mandatory artifacts per phase |
| `reference/phase-completion-gate.md` | Coverage report + completion gate after every phase |
| `reference/manifest-schema.md` | `manifest.yaml` machine-readable state schema |
| `reference/evidence-precedence.md` | Runtime → code → config → tests evidence ordering |
| `templates/manifest.yaml`, `templates/domain-config.yaml` | Starter templates |
| `scripts/validate_manifest_yaml.py` | Manifest validator (`--check-content`) |
| `tests/test_validate_manifest.py` | Pytest suite for the validator |

## k8s-overprovisioning-datadog file map

| Path | What it does |
|------|--------------|
| `workflow/orchestrator.md` | Pipeline routing, intent shortcuts, decision tree |
| `workflow/discover-sources.md` | Kubernetes MCP-first capability discovery and `source_profile` routing before workload queries |
| `workflow/stop-reasons.md` | P0 safety gates (auth failure, manifest drift, insufficient metrics) |
| `workflow/build-graph.md` … `render.md` | BUILD_GRAPH → VALIDATE_INVARIANTS → RENDER |
| `reference/decision-graph-schema.md` | Primary typed artifact (`schema_version: 3`) |
| `reference/invariants.md` | INV-01–INV-14 self-validation |
| `render/markdown.md`, `render/json.md` | Renderers — Human Report + Technical Appendix (markdown) or JSON export |
| `templates/human-report.md` | Human Report layout (prose-first; no registry IDs) |
| `workflow/report.md` | Presentation rules — label translation, summary-only mode, smoke tests |
| `queries.md` | Datadog query strings (do not invent inline) |
| `thresholds.md` | Verdict bands, HPA table, cyclic detection, confidence rubric |
| `report-template.md` | DORA section contract — Human Report (primary) + Technical Appendix |

## test-writer file map

A thin router — no scripts, no tests, no detection/generation logic. See each dispatch target's own file
map below for where the real work happens.

| Path | What it does |
|------|--------------|
| `workflow/inputs.md` | Parse `request` + `repo_root` + optional `level_hint`; HARD STOP on missing required fields |
| `workflow/classify.md` | Resolve to exactly one level; ask once if genuinely ambiguous, never guess |
| `workflow/delegate.md` | Dispatch to the matching skill with inputs unchanged; relay its report verbatim |
| `reference/skill-contract.md` | Non-negotiable agent contract (load with SKILL.md) |
| `reference/level-classification.md` | Keyword heuristics per level, mirroring `skill-routing.md` |
| `reference/pressure-tests.md` | Maintainer regression scenarios |
| `examples.md` | Invocation table + golden scenarios |

## unit-test-creator file map

| Path | What it does |
|------|--------------|
| `workflow/inputs.md` | Parse `target` (`diff`/`backfill`) + `repo_root` + `run_tests`; HARD STOP on missing required fields |
| `workflow/detect-conventions.md` | Run the detection script; ask-once on ambiguous framework, ask-before-writing on none detected |
| `workflow/select-targets.md` | Diff-mode changed-code selection / backfill scope expansion, exclusions, `max_files_per_run` cap |
| `workflow/generate-tests.md` | Write real, convention-matched tests with every external mocked; untestable-without-fixture gate |
| `workflow/verify-and-iterate.md` | Run, fix test bugs, never patch production code to force green |
| `workflow/report.md` | `UNIT_TEST_REPORT.md` rendering rules |
| `scripts/detect-test-framework.sh`, `scripts/test-framework-markers.sh` | Marker-file framework detection across 11 ecosystems |
| `reference/skill-contract.md` | Non-negotiable agent contract; links shared `test-creation-principles.md` |
| `reference/gate-policy.md` | Every live gate and its required, non-guessing answer |
| `reference/test-quality-deltas.md` | Unit-specific delta on the shared quality checklist: mock every external dependency |
| `reference/framework-detection.md` | Marker-file table + confidence rules the detection script implements |
| `reference/report-format.md` | Normative `UNIT_TEST_REPORT.md` structure |
| `reference/pressure-tests.md` | Maintainer regression scenarios |
| `examples.md` | Invocation table + golden scenarios |
| `tests/fixtures/test-framework-detect/` | Marker-file fixtures per ecosystem + ambiguous/none cases |
| `tests/test_detect_test_framework.py` | Pytest suite for the detection script |

## integration-test-creator file map

| Path | What it does |
|------|--------------|
| `workflow/inputs.md` | Parse `target` + `repo_root` + `run_tests`; HARD STOP on missing required fields |
| `workflow/detect-conventions.md` | Detect base runner + real-dependency orchestration mechanism; ask-once/ask-before-writing gates |
| `workflow/select-targets.md` | Diff/backfill target resolution, exclusions, `max_files_per_run` cap |
| `workflow/generate-tests.md` | Write tests against the real dependency — never mock the seam under test |
| `workflow/verify-and-iterate.md` | Run against the real dependency, fix test bugs, never patch production code |
| `workflow/report.md` | `INTEGRATION_TEST_REPORT.md` rendering rules, including `NEEDS_INTEGRATION_ENV` |
| `scripts/detect-integration-setup.sh`, `scripts/integration-markers.sh` | testcontainers/docker-compose/embedded-DB + integration-tag detection |
| `reference/skill-contract.md` | Non-negotiable agent contract; links shared `test-creation-principles.md` |
| `reference/gate-policy.md` | Every live gate, including `NEEDS_INTEGRATION_ENV` when no orchestration mechanism exists |
| `reference/test-quality-deltas.md` | Integration-specific delta: never mock the dependency under test |
| `reference/framework-detection.md` | Base-runner + orchestration-mechanism marker tables |
| `reference/report-format.md` | Normative `INTEGRATION_TEST_REPORT.md` structure |
| `reference/pressure-tests.md` | Maintainer regression scenarios |
| `examples.md` | Invocation table + golden scenarios |
| `tests/fixtures/integration-detect/` | testcontainers/docker-compose/tag-only/none fixtures |
| `tests/test_detect_integration_setup.py` | Pytest suite for the detection script |

## contract-test-creator file map

| Path | What it does |
|------|--------------|
| `workflow/inputs.md` | Parse `target` (with required `role: consumer\|provider`) + `repo_root`; HARD STOP if `role` absent |
| `workflow/detect-conventions.md` | Detect Pact tooling per ecosystem + broker vs. local-only usage |
| `workflow/select-targets.md` | Diff/backfill target resolution scoped to the given role |
| `workflow/generate-tests.md` | Consumer vs. provider generation logic; interaction shape must trace to real observed usage |
| `workflow/verify-and-iterate.md` | Run/verify against pact file(s) or broker; never loosen a contract to pass |
| `workflow/report.md` | `CONTRACT_TEST_REPORT.md` rendering rules, including `NEEDS_OBSERVED_INTERACTION` |
| `scripts/detect-pact-tooling.sh`, `scripts/pact-markers.sh` | Pact library + broker detection per ecosystem |
| `reference/skill-contract.md` | Non-negotiable agent contract; links shared `test-creation-principles.md` |
| `reference/gate-policy.md` | Every live gate, including required `role` and `NEEDS_OBSERVED_INTERACTION` |
| `reference/test-quality-deltas.md` | Contract-specific delta: interaction shape must trace to real usage |
| `reference/framework-detection.md` | Pact-tooling marker table per ecosystem + broker detection |
| `reference/report-format.md` | Normative `CONTRACT_TEST_REPORT.md` structure |
| `reference/pressure-tests.md` | Maintainer regression scenarios |
| `examples.md` | Invocation table + golden scenarios |
| `tests/fixtures/pact-detect/` | Consumer/provider/broker/none fixtures |
| `tests/test_detect_pact_tooling.py` | Pytest suite for the detection script |

## e2e-test-creator file map

| Path | What it does |
|------|--------------|
| `workflow/inputs.md` | Parse `target` (`journeys` required for backfill mode) + `repo_root`; HARD STOP if empty |
| `workflow/detect-conventions.md` | Detect Playwright/Cypress/Selenium tooling + layout convention |
| `workflow/select-targets.md` | Diff-mode journey inference from changed routes/pages / backfill explicit journeys |
| `workflow/generate-tests.md` | Journey → steps → user-visible assertions only; no hard sleeps |
| `workflow/verify-and-iterate.md` | Run against a reachable app instance, fix test bugs, never patch production code |
| `workflow/report.md` | `E2E_TEST_REPORT.md` rendering rules, including `NEEDS_BROWSER_ENV` |
| `scripts/detect-e2e-tooling.sh`, `scripts/e2e-markers.sh` | Playwright/Cypress/Selenium + layout detection |
| `reference/skill-contract.md` | Non-negotiable agent contract; links shared `test-creation-principles.md` |
| `reference/gate-policy.md` | Every live gate, including `NEEDS_BROWSER_ENV` when no app instance is reachable |
| `reference/test-quality-deltas.md` | E2E-specific delta: user-visible assertions only, no hard sleeps |
| `reference/framework-detection.md` | Browser-tooling marker table + layout conventions |
| `reference/report-format.md` | Normative `E2E_TEST_REPORT.md` structure |
| `reference/pressure-tests.md` | Maintainer regression scenarios |
| `examples.md` | Invocation table + golden scenarios |
| `tests/fixtures/e2e-detect/` | Playwright/Cypress/ambiguous/none fixtures |
| `tests/test_detect_e2e_tooling.py` | Pytest suite for the detection script |

## api-test-creator file map

| Path | What it does |
|------|--------------|
| `workflow/inputs.md` | Parse `target` (endpoint list or file/dir scope) + `repo_root` + `run_tests`; HARD STOP on missing required fields |
| `workflow/detect-conventions.md` | Detect Postman/Newman tooling + canonical collection file; ask-which-collection / ask-before-creating gates |
| `workflow/select-targets.md` | Diff-mode changed-endpoint selection / backfill endpoint-descriptor or file/dir expansion, including the domain-comprehension `API_CATALOG.md` step |
| `workflow/generate-tests.md` | Write request/assertion pairs (status, schema, headers); request chaining via Postman variables; `NEEDS_OBSERVED_ENDPOINT` gate |
| `workflow/verify-and-iterate.md` | Run via Newman against a reachable API instance, fix test bugs, never patch production code; `NEEDS_API_ENV` gate |
| `workflow/report.md` | `API_TEST_REPORT.md` rendering rules, including `NEEDS_OBSERVED_ENDPOINT` and `NEEDS_API_ENV` |
| `scripts/detect-postman-tooling.sh`, `scripts/postman-markers.sh` | Postman/Newman + canonical-collection detection |
| `reference/skill-contract.md` | Non-negotiable agent contract; links shared `test-creation-principles.md` |
| `reference/gate-policy.md` | Every live gate, including ambiguous-collection, `NEEDS_OBSERVED_ENDPOINT`, and `NEEDS_API_ENV` |
| `reference/test-quality-deltas.md` | API-specific delta: assert status AND schema, chain via variables not hard-coded IDs |
| `reference/framework-detection.md` | Postman/Newman marker table + canonical-collection ambiguity rule |
| `reference/report-format.md` | Normative `API_TEST_REPORT.md` structure |
| `reference/pressure-tests.md` | Maintainer regression scenarios |
| `examples.md` | Invocation table + golden scenarios |
| `tests/fixtures/postman-detect/` | Single-collection/newman-only/ambiguous/none fixtures |
| `tests/test_detect_postman_tooling.py` | Pytest suite for the detection script |

## Install and quality gates

See [REPOSITORY.md](REPOSITORY.md) for `make install`, `make lint`, GitHub Actions CI (`.github/workflows/lint.yml`), and pre-commit hooks.
