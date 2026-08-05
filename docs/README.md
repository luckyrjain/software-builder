# Documentation index

Human-readable guide to everything in the **ai-skills** repository. Agent instructions live in each skill's
`SKILL.md`; this index explains what each piece is for and where to look.

## Start here

| Document | What it is |
|----------|------------|
| [../README.md](../README.md) | Install, invoke, and quick usage for all skills |
| [REPOSITORY.md](REPOSITORY.md) | Repo layout, `Makefile`, `scripts/`, lint targets, git hooks |
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
| **mysql-to-postgres-sql** | [mysql-to-postgres-sql/README.md](../mysql-to-postgres-sql/README.md) | [mysql-to-postgres-sql/SKILL.md](../mysql-to-postgres-sql/SKILL.md) | [mysql-to-postgres-sql/SETUP.md](../mysql-to-postgres-sql/SETUP.md) |
| **loop-task-implementer** | [loop-task-implementer/README.md](../loop-task-implementer/README.md) | [loop-task-implementer/SKILL.md](../loop-task-implementer/SKILL.md) | [loop-task-implementer/SETUP.md](../loop-task-implementer/SETUP.md) |

### One-line summary

| Skill | Invoke | Does |
|-------|--------|------|
| **pr-review** | `/pr-review` or "review this MR/PR …" | Reviews GitLab merge requests: loads diff + Jira context, emits severity-tagged findings, optionally posts inline threads and a summary note via GitLab MCP |
| **pr-gatekeeper** | Push webhook, not ambient chat | Auto-runs pr-review on every push to an open MR; posts when pr-review's own confirmation rules allow it unattended, otherwise routes to notification |
| **incident-rca** | Natural language ("RCA for …") | Multi-source post-incident investigation (Datadog, KubeSense, GitLab, Jenkins, Jira) → manager-ready RCA report with hypotheses and evidence |
| **incident-triage-agent** | Paging webhook, not ambient chat | Page-fire triage doc + incident-resolved postmortem draft, composing incident-rca (root cause) + squad-map (owner) |
| **k8s-overprovisioning-datadog** | Natural language ("is X overprovisioned?") | Datadog-driven K8s deployment optimization assessment: CPU/memory/replica verdicts, waste estimate, cost, rollback guidance |
| **domain-comprehension** | Natural language ("map the domain …") | Evidence-backed domain comprehension across repos: bounded contexts, data ownership, dependency graphs, business flows, exec summary with confidence |
| **squad-map** | Natural language ("map squads …", "who owns …") | Repo-to-squad mapping via GitLab group hierarchy + Datadog team tags → `SQUAD_MAP.md` with confidence and conflict flags |
| **who-owns-x-bot** | Structured `query`, not ambient chat (`/who-owns <name>` Slack slash command) | Single-shot "who owns X" Slack reply — thin wrapper delegating the lookup entirely to squad-map |
| **mysql-to-postgres-sql** | Natural language ("MySQL scrub …", "jdbc:postgresql …") | MySQL-dialect scan gate + PostgreSQL rewrite for a `jdbc:mysql`→`jdbc:postgresql` migration |
| **loop-task-implementer** | Natural language ("implement issue 42 …") | Autonomous multi-task loop: isolated Builder → two-lens independent Reviewer → adjudicated remediation → PR; platform-neutral, no MCP dependency |

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
| domain-comprehension | Produced `MYSQL_TO_PG_SQL_REWRITES.md` | mysql-to-postgres-sql |
| mysql-to-postgres-sql | Migration MR needs review | pr-review |
| mysql-to-postgres-sql | Cutover regression / wrong query results | incident-rca |
| loop-task-implementer | Task's MR needs review beyond its own lenses | pr-review |
| pr-gatekeeper | Caller wants an interactive, on-demand review | pr-review |
| loop-task-implementer | Task implementation causes/needs incident investigation | incident-rca |
| loop-task-implementer | Task needs unfamiliar-codebase context first | domain-comprehension |
| loop-task-implementer | Task touches MySQL-dialect SQL during a PG migration | mysql-to-postgres-sql |

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

These are planning artifacts; the live behavior is defined in `pr-review/SKILL.md` and `pr-review/reference/`.

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

## mysql-to-postgres-sql file map

| Path | What it does |
|------|--------------|
| `workflow/migrate-service.md` | Per-service inventory → scan → rewrite → config → verify → merge gate |
| `reference/function-translations.md` | MySQL → PostgreSQL function mapping + cooling-period pattern |
| `reference/collection-domain-files.md` | collection domain P0/P1/P2 file-level rewrite checklist |
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
| `workflow/stop-reasons.md` | P0 safety gates (auth failure, manifest drift, insufficient metrics) |
| `workflow/build-graph.md` … `render.md` | BUILD_GRAPH → VALIDATE_INVARIANTS → RENDER |
| `reference/decision-graph-schema.md` | Primary typed artifact (`schema_version: 3`) |
| `reference/invariants.md` | INV-01–INV-12 self-validation |
| `render/markdown.md`, `render/json.md` | Renderers — Human Report + Technical Appendix (markdown) or JSON export |
| `templates/human-report.md` | Human Report layout (prose-first; no registry IDs) |
| `workflow/report.md` | Presentation rules — label translation, summary-only mode, smoke tests |
| `queries.md` | Datadog query strings (do not invent inline) |
| `thresholds.md` | Verdict bands, HPA table, cyclic detection, confidence rubric |
| `report-template.md` | DORA section contract — Human Report (primary) + Technical Appendix |

## Install and quality gates

See [REPOSITORY.md](REPOSITORY.md) for `make install`, `make lint`, GitLab CI (`.gitlab-ci.yml`), and pre-commit hooks.
