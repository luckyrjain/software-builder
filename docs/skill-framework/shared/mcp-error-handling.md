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

When an MCP server is unavailable, each skill follows a defined fallback.

`scripts/registry/degraded_behavior.yaml` is the machine-checked source of that policy: it covers all
38 skills, names abstract capability ids rather than MCP-server brands, and is what the eval scenario
harness actually exercises. **The table below is an illustrative subset**, kept in provider terms
because that is how the failure presents to a user. It is written by hand and is not generated from
the YAML — when the two differ, the YAML is authoritative.

| Skill | MCP unavailable | Degraded behavior |
|-------|-----------------|-------------------|
| **incident-rca** | Datadog ❌ | `oss-obs` path; user-supplied PromQL; cap confidence MEDIUM |
| **incident-rca** | KubeSense ❌ | Datadog-only (if available); skip log body analysis; note in Gaps |
| **incident-rca** | Both ❌ | Blocked — require at least one observability source |
| **k8s** | Datadog ❌ | Continue with Kubernetes MCP when it supplies sufficient historical evidence; otherwise defer history-dependent sizing or emit `insufficient_metrics` |
| **k8s** | Kubernetes MCP ❌ | Continue with Datadog telemetry; record the live-state verification gap |
| **k8s** | All viable sources unauthorized | Blocked (`STOP_REASON: auth_failure`); report attempted sources and configure one usable source |
| **k8s** | Git MCP ❌ | Skip manifest drift check; ask user to paste resource values |
| **pr-review** | GitLab ❌ | Blocked — cannot fetch MR diffs without GitLab MCP |
| **pr-review** | Jira ❌ | Skip AC check; note "no linked ticket" |
| **domain-comprehension** | GitLab ❌ | Squad mapping degraded (CODEOWNERS fallback via squad-map) |
| **domain-comprehension** | Datadog ❌ | Skip P2b runtime validation; note in KNOWN_OMISSIONS |
| **squad-map** | GitLab ❌ | Datadog team only; GitLab squad = UNKNOWN |
| **squad-map** | Datadog ❌ | GitLab squad only; Datadog team = UNKNOWN |
| **squad-map** | Both ❌ | CODEOWNERS fallback; confidence capped at LOW |

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
