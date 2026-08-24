# Smoke test conventions (shared)

**Normative.** Each skill extends these conventions with a dedicated `reference/smoke-test.md` (or anchored section in k8s `workflow/render.md` until Phase 3 extracts it).

**Reference implementations:** every skill in this repo has a `reference/smoke-test.md` (or, for k8s, an
anchored section in `workflow/render.md`) — see § 3 for the per-skill invocation strings and § 6 for the
matching `make lint-<skill>` targets.

## 1. When to run

| Event | Run smoke? |
|-------|------------|
| Fresh install (`make install-*`) | Yes |
| Any edit to `SKILL.md`, `workflow/`, `reference/` | Yes |
| Pre-release / before merge to master | Yes |
| User invocation in production | No (use real target) |

Re-run after **any** skill edit — not only after install.

## 2. Required structure

Each skill's smoke doc MUST include:

1. **Fixture** — small real target (MR <10 files; known service + 1h window; deployment with ≥7d metrics)
2. **Invocation string** — exact user phrase to type in chat
3. **Numbered output checklist** — minimum 5 elements agents must emit
4. **Expected first output** — what Phase 0 / MCP profile line looks like when healthy
5. **Script self-test** — if `scripts/` exist: `py_compile` + pytest or shellcheck
6. **Failure diagnosis** — MCP disconnected vs wrong target vs regression (§5 below)
7. **Pressure-test link** — pointer to `reference/pressure-tests.md`

## 3. Standalone `reference/smoke-test.md` format

Every compliant skill maintains a file at `reference/smoke-test.md` with this skeleton:

```markdown
# Smoke test — expected minimal output

Run after install and after any skill edit.

## Invocation

> <exact user phrase for fixture target>

## A correct minimal output contains

1. **Phase 0 / MCP profile** — which integrations are ✅/❌
2. **Scope announcement** — what is being analyzed and boundaries
3. **Core findings** — table or explicit "none"
4. **Summary / report** — executive or human report section
5. **Structured footer** — YAML/JSON metadata where applicable
6. **Confirmation or next step** — post gate, handoff offer, or re-run hint

## Script self-test

<commands or make target>

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
```

### Per-skill invocation strings

| Skill | Invocation string | Expected first output |
|-------|-------------------|------------------------|
| pr-review | `/pr-review` on open PR/MR <10 files in test project | Phase 0: posting mode (`full`/`summary-only`/…) + provider and host |
| pr-gatekeeper | Webhook: `project`, `merge_request_iid`, `head_sha`, `auto_post_authorized: true` | pr-review's own Phase 0 posting-mode announcement — no pr-gatekeeper-specific preamble |
| incident-rca | `RCA for <service> between <from> and <to> UTC — <symptom>` | MCP profile: `Datadog ✅ \| KubeSense … \| GitLab …` |
| incident-triage-agent | Webhook: `event_type: page_triggered`, `service`, `triggered_at`, `alert_title`, `severity` | 30-minute window announced, UTC-suffixed, symmetric around `triggered_at` |
| k8s-overprovisioning-datadog | Assess single deployment with ≥7d history from Kubernetes MCP or Datadog, <5 containers | DISCOVER_SOURCES profile first; scope: deployment + env + window |
| domain-comprehension | `Map bounded contexts in <domain> workspace` | Session 0 MCP profile + census scope |
| squad-map | `Map squads for repos in <workspace>` | Phase 0: `GitLab ✅ \| Datadog …` |
| who-owns-x-bot | `query: <repo-name>`, `workspace_root: <workspace>` | One Slack-formatted reply — no intermediate chatter, no file written |
| new-hire-guide | `new_hire: {name: <name>, squad: <squad>}`, `workspace_root: <workspace>` | squad-map's own Phase 0/1 output, then domain-comprehension's own Session 0 output, unscoped |
| release-readiness-checker | `release_manifest: [{repo, service, since}, ...]` | MR-range resolution announced per repo, before any pr-review invocation starts |
| migration-program-manager | `program_manifest: [{workspace_root}, ...]`, `staleness_threshold_days` | Per-workspace read announced, before the aggregator writes any output file |
| cost-optimization-sprint-planner | `sweep_scope: {env, deployments}`, `cost_rate: {provider, dollars_per_core_month, dollars_per_gib_month}` | Resolved sweep config announced, before the first k8s-overprovisioning-datadog invocation starts |
| mysql-to-postgres-sql | `Scan tests/fixtures/mysql-dialect/hits for MySQL-only SQL` | Scan command + hit file:line list or OK |
| loop-task-implementer | `Use loop-task-implementer to implement <task> and open a PR.` | Discovers repo policy, selects one eligible task, dispatches a fresh Builder |
| backlog-runner | `tracker_query`, `max_tasks_per_run`, `repo_context` | Queue pull announced (tickets found, capped, skipped), then dependency order, before the first loop-task-implementer invocation |
| weekly-squad-digest | `rollup_manifest: {migration_rollup_path, cost_rollup_path}` | Resolved rollup paths announced (supplied vs. found on disk), before the digest is rendered |
| test-writer | A test-writing request with the level unspecified | Classified level announced (or the ask-once level gate), before dispatch |
| unit-test-creator | `target: {mode: diff/backfill, ...}`, `repo_root: <path>` | Detected framework + confidence announced, before any target is selected |
| integration-test-creator | `target: {mode: diff/backfill, ...}`, `repo_root: <path>` | Detected base framework + real-dependency orchestration mechanism announced |
| contract-test-creator | `target: {mode: diff/backfill, role: consumer/provider, ...}`, `repo_root: <path>` | Detected Pact tooling + role announced, before any interaction is selected |
| e2e-test-creator | `target: {mode: diff/backfill, journeys: [...] }`, `repo_root: <path>` | Detected browser tooling announced, before any journey is selected |
| api-test-creator | `target: {mode: diff/backfill, ...}`, `repo_root: <path>` | Detected Postman/Newman tooling + collection announced, before any endpoint is selected |
| architecture-review | `Architecture review for <feature>` + proposal/design text | Inputs parsed, before Analyze starts |
| system-design | `Design the implementation for <feature>` + architecture decision/PRD text | Inputs parsed, before Analyze starts |
| api-design-review | `Review the API design for <feature>` + API spec/contract text | Inputs parsed, before Analyze starts |
| database-review | `Review this schema/migration` + schema/DDL text | Inputs parsed, before Analyze starts |
| security-review | `Security review of <target>` + code/config/design content | Inputs parsed, before Analyze starts |
| performance-review | `Performance review of <target>` + code/query content | Inputs parsed, before Analyze starts |
| capacity-planner | `Forecast capacity for <service>` + historical demand data | Inputs parsed, before Analyze starts |
| observability-review | `Observability review for <service>` + metrics/logs/dashboard/alert config | Inputs parsed, before Analyze starts |
| deployment-risk-review | `Deployment risk review for <change>` + release/change description | Inputs parsed, before Analyze starts |
| dependency-upgrade-review | `Review upgrading <dependency> from <current> to <target>` | Inputs parsed, before Analyze starts |
| tech-debt-assessor | `Rank this tech debt backlog` + debt-item list | Inputs parsed, before Analyze starts |
| change-impact-analyzer | `What services/contracts are affected by PR #123?` | Exact target/diff and capability profile announced before Analyze |

## 4. Output checklist template

```markdown
A correct minimal output should contain:

1. **Phase 0 / MCP profile** — which integrations are ✅/❌
2. **Scope announcement** — what is being analyzed and boundaries
3. **Core findings** — table or explicit "none" (not empty header)
4. **Summary / report** — executive or human report section
5. **Structured footer** — YAML/JSON metadata where applicable
6. **Confirmation or next step** — post gate, handoff offer, or re-run hint
```

## 5. Failure diagnosis

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Phase 0 shows all MCP ❌ | MCP server disconnected / auth | Re-auth; check Cursor MCP settings |
| Smoke passes but pressure test fails | Edge case regression | Check `pressure-tests.md` row |
| pytest fails in pr-review | Script change broke diff parser | `make lint-pr-review-scripts` |
| k8s INV failure in smoke | Schema or template drift | `make lint-k8s-skill` |
| incident-rca empty hypothesis rank | Both `error_signals` and `infra_signals` empty | Expected blocked path; verify gap message |
| pr-review stops at Phase 1 | MR closed/merged or merge conflicts | Use open MR fixture |
| k8s Human Report shows formula arithmetic | Render regression | Check `workflow/report.md` smoke rules |

## 6. Makefile integration

| Skill | Lint target |
|-------|-------------|
| pr-review | `make lint-pr-review` (includes pytest) |
| pr-gatekeeper | `make lint-pr-gatekeeper` |
| incident-rca | `make lint-incident-rca` |
| incident-triage-agent | `make lint-incident-triage-agent` |
| k8s-overprovisioning-datadog | `make lint-k8s-skill` |
| domain-comprehension | `make lint-domain-comprehension` (includes pytest) |
| squad-map | `make lint-squad-map` (includes pytest) |
| who-owns-x-bot | `make lint-who-owns-x-bot` |
| new-hire-guide | `make lint-new-hire-guide` |
| release-readiness-checker | `make lint-release-readiness-checker` |
| migration-program-manager | `make lint-migration-program-manager` (includes aggregator pytest) |
| cost-optimization-sprint-planner | `make lint-cost-optimization-sprint-planner` |
| mysql-to-postgres-sql | `make lint-mysql-to-postgres-sql` |
| loop-task-implementer | `make lint-loop-task-implementer` |
| backlog-runner | `make lint-backlog-runner` |
| weekly-squad-digest | `make lint-weekly-squad-digest` |
| test-writer | `make lint-test-writer` |
| unit-test-creator | `make lint-unit-test-creator` (includes pytest + shellcheck) |
| integration-test-creator | `make lint-integration-test-creator` (includes pytest + shellcheck) |
| contract-test-creator | `make lint-contract-test-creator` (includes pytest + shellcheck) |
| e2e-test-creator | `make lint-e2e-test-creator` (includes pytest + shellcheck) |
| api-test-creator | `make lint-api-test-creator` (includes pytest + shellcheck) |
| prd-architect | `make lint-prd-architect` |
| architecture-review | `make lint-architecture-review` |
| system-design | `make lint-system-design` |
| api-design-review | `make lint-api-design-review` |
| database-review | `make lint-database-review` |
| security-review | `make lint-security-review` |
| performance-review | `make lint-performance-review` |
| capacity-planner | `make lint-capacity-planner` |
| observability-review | `make lint-observability-review` |
| deployment-risk-review | `make lint-deployment-risk-review` |
| dependency-upgrade-review | `make lint-dependency-upgrade-review` |
| tech-debt-assessor | `make lint-tech-debt-assessor` |
| change-impact-analyzer | `make lint-change-impact-analyzer` |
| Framework | `make lint-framework` |
| All | `make lint` |

## 7. Maintainer pressure tests

Smoke = happy path. `pressure-tests.md` = edge cases and **wrong behavior** rows (≥2 per skill). Every smoke doc links to pressure tests.
