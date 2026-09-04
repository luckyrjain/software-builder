# MCP Error Handling Conventions (shared)

**Normative.** Consistent patterns for handling MCP server failures across all skills.

**Consumers:** All skills' Phase 0 (MCP profile) and any phase that calls MCP tools.

## 1. MCP profile check (Phase 0)

Every skill's Phase 0 MUST probe available MCP servers and announce a profile line:

```
**<Skill> MCP profile:** Datadog ✅ | KubeSense ❌ | GitLab ✅ | Jenkins ❌
```

| Status | Meaning |
|--------|---------|
| ✅ (queried) | Tool responded successfully to a probe call |
| ✅ | Tool is configured; not yet probed (acceptable for lazy-probe skills) |
| ❌ | Tool missing, not configured, or probe failed |
| N/A | Tool not relevant to this skill |

## 2. Failure categories

| Category | Symptom | Retry? | Action |
|----------|---------|--------|--------|
| **auth_failure** | 401, 403, "unauthorized" | No | Record the failure against that source, use its setup/remediation path, and continue through another sufficient source when the consuming skill supports fallback |
| **not_configured** | Tool name not found in MCP registry | No | Announce ❌; fall back to degraded path or ask user to configure |
| **timeout** | No response within tool timeout | Yes (1×) | Retry once; on second failure, treat as `unavailable` |
| **rate_limited** | 429, "rate limit exceeded" | Yes (backoff) | Wait 30s, retry once; on failure, narrow query scope or defer |
| **server_error** | 500, 502, 503 | Yes (1×) | Retry once; on failure, treat as `unavailable` |
| **invalid_request** | 400, "bad request", schema validation | No | Fix the request parameters; do not retry same payload |
| **empty_response** | 200 but no data returned | No | Valid result — absence of data is informational, not a failure |
| **unavailable** | After retries exhausted | No | Mark tool ❌; announce degraded mode; continue with available sources |

## 3. Retry policy

```
MAX_RETRIES = 1 (total 2 attempts)
RETRY_DELAY = 5s (timeout), 30s (rate_limited)
```

- **Do not retry** auth failures or invalid requests — these are deterministic.
- **Do not retry** empty responses — they're valid.
- After `MAX_RETRIES`, mark the tool as unavailable for this session and announce degraded mode.

## 4. Degraded mode patterns

When an MCP server is unavailable, each skill follows a defined fallback. Each skill declares that
policy in its own registry fragment (`scripts/registry/skills.d/<skill-id>.yaml`, under
`degraded_behavior:`), which is the single place it is authored and the only place to edit it.

<!-- degraded-behavior-table:start -->
Every row below is projected from `scripts/registry/degraded_behavior.yaml` — itself
generated from each skill's `scripts/registry/skills.d/<skill-id>.yaml` fragment — and named
against the families in `scripts/registry/capability_families.yaml`. A provider-branded
capability is shown by provider, because that is how the failure presents to a user
(`Datadog ❌`, `GitHub ❌`, `GitLab ❌`, `Kubernetes MCP ❌`); the capability id beside it is what the eval scenario harness exercises.

`BLOCKED` means all viable sources for that capability are gone and the skill must stop rather
than guess. `FALLBACK` and `DEGRADED` continue on the remaining capabilities named in the last
column.

| Skill | Unavailable | Capability family | Behavior | Continues with |
|-------|-------------|-------------------|----------|----------------|
| `api-design-review` | `host.report.write` | — | BLOCKED | — |
| `api-test-creator` | `host.repository.read_write` | — | BLOCKED | — |
| `architecture-review` | `host.report.write` | — | BLOCKED | — |
| `backlog-runner` | `scheduler.cron.trigger` | — | BLOCKED | — |
| `capacity-planner` | `host.report.write` | — | BLOCKED | — |
| `change-impact-analyzer` | `host.repository.read` | — | DEGRADED | `host.report.write`, `host.scm.change.read` |
| `contract-test-creator` | `host.repository.read_write` | — | BLOCKED | — |
| `cost-optimization-sprint-planner` | `host.filesystem.read` | — | BLOCKED | — |
| `database-review` | `host.report.write` | — | BLOCKED | — |
| `dependency-upgrade-review` | `host.report.write` | — | BLOCKED | — |
| `deployment-risk-review` | `host.report.write` | — | BLOCKED | — |
| `domain-comprehension` | `host.repository.read` | — | BLOCKED | — |
| `e2e-test-creator` | `host.repository.read_write` | — | BLOCKED | — |
| `implementation-planner` | `host.repository.read` | — | BLOCKED | `host.report.write` |
| `incident-rca` | `telemetry.logs.query` | — | BLOCKED | — |
| `incident-triage-agent` | `pager.webhook.receive` | — | BLOCKED | — |
| `integration-test-creator` | `host.repository.read_write` | — | BLOCKED | — |
| `k8s-overprovisioning-datadog` | **Kubernetes MCP ❌** `kubernetes.metrics.history` | observability.metrics.query | FALLBACK | `datadog.query_metrics` |
| `loop-task-implementer` | `host.repository.read_write` | — | BLOCKED | — |
| `migration-program-manager` | `host.filesystem.read` | — | BLOCKED | — |
| `mysql-to-postgres-sql` | `host.repository.read_write` | — | BLOCKED | — |
| `new-hire-guide` | `host.repository.read` | — | BLOCKED | — |
| `observability-review` | `host.report.write` | — | BLOCKED | — |
| `performance-review` | `host.report.write` | — | BLOCKED | — |
| `pr-gatekeeper` | **GitLab ❌** `gitlab.get_merge_request` | scm.pull_request.read | BLOCKED | — |
| `pr-review` | **GitLab ❌** `gitlab.get_merge_request` | scm.pull_request.read | FALLBACK | `github.get_pull_request`, `github.get_pull_request_files` |
| `prd-architect` | `host.report.write` | — | BLOCKED | — |
| `production-readiness-review` | `host.dependency.advisories.read` | — | DEGRADED | `host.report.write`, `host.repository.read`, `host.scm.change.read`, `host.ci.status`, `host.scm.policy.read`, `host.build.provenance.read`, `host.service.metadata.read` |
| `release-readiness-checker` | `host.report.write` | — | BLOCKED | — |
| `resilience-review` | `host.repository.read` | — | DEGRADED | `host.report.write` |
| `security-review` | `host.report.write` | — | BLOCKED | — |
| `squad-map` | **GitLab ❌** `gitlab.list_projects` | scm.merge_request.list | BLOCKED | — |
| `system-design` | `host.report.write` | — | BLOCKED | — |
| `tech-debt-assessor` | `host.report.write` | — | BLOCKED | — |
| `test-writer` | `host.repository.read` | — | BLOCKED | — |
| `unit-test-creator` | `host.repository.read_write` | — | BLOCKED | — |
| `weekly-squad-digest` | `scheduler.cron.trigger` | — | BLOCKED | — |
| `who-owns-x-bot` | `slack.slash_command.receive` | — | BLOCKED | — |
<!-- degraded-behavior-table:end -->

## 5. Confidence impact

MCP failures affect confidence scoring:

| Condition | Confidence impact |
|-----------|-------------------|
| Primary observability source unavailable | Cap at **MEDIUM** |
| Secondary/optional source unavailable | Note in Gaps; no automatic cap |
| All sources unavailable for a signal | Cap at **LOW** or block the assessment |
| Retry succeeded (transient failure) | No impact — treat as normal |

## 6. Error reporting in output

When MCP failures affect the assessment, report them in a standard format:

```markdown
### MCP coverage gaps

| Server | Status | Impact |
|--------|--------|--------|
| Datadog | ❌ timeout after retry | Log analysis unavailable; trigger attribution capped at MEDIUM |
| KubeSense | ✅ | Primary log source |
| GitLab | ✅ | Deploy correlation available |
```

Place this in:
- **incident-rca**: Gaps / missing evidence section
- **k8s**: Pre-flight announcement or Gaps section
- **pr-review**: Phase 0 announcement
- **domain-comprehension**: `KNOWN_OMISSIONS.md`
- **squad-map**: `SQUAD_MAP.md` header

## 7. Anti-patterns

| Anti-pattern | Correct behavior |
|--------------|------------------|
| Silently skip a tool and claim complete coverage | Announce ❌ and note in Gaps |
| Retry auth failures repeatedly | Route to setup skill immediately |
| Treat empty response as failure | Empty = no data in window; not an error |
| Invent data when MCP fails | Use UNKNOWN; never fabricate metrics/fields |
| Block entire skill for optional MCP | Only block for required sources; degrade gracefully |
| Retry indefinitely | Max 2 attempts total; then degrade |

## 8. Implementation checklist (per skill)

- [ ] Phase 0 probes all relevant MCP servers
- [ ] Profile line announced with ✅/❌ per server
- [ ] Retry policy applied (1 retry for timeout/5xx)
- [ ] Degraded path documented and followed
- [ ] Confidence impact applied per §5
- [ ] MCP gaps reported in standard format per §6
- [ ] No silent failures — every ❌ is visible to the user
