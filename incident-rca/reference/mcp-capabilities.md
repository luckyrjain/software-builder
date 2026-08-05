# MCP Capability Matrix — Incident RCA

> **Re-verify in Phase 0** — tool names/availability change across MCP server upgrades; always confirm
> against the live tool list before relying on a tool below.

Discover connected tools in Phase 0 before investigating. Match **capabilities**, not exact names. All
Datadog calls require a `telemetry.intent` (one-line English, no secrets).

## Observability

### Datadog (`plugin-datadog-datadog`)

| Capability | Tool | RCA use |
|------------|------|---------|
| Log aggregation (counts, top-N, GROUP BY) | `analyze_datadog_logs` | Error counts by service/message |
| Raw log samples | `search_datadog_logs` | Sample error lines, stack traces (not for counting) |
| Change events | `get_change_stories` | Deploys, k8s manifest/scale, feature flags, crashloops in window |
| Metrics | `get_datadog_metric` | Error rate, p95 latency, K8s restarts |
| Metric discovery | `get_datadog_metric_context` / `search_datadog_metrics` | Resolve the real error/latency metric name |
| Traces | `search_datadog_spans` / `aggregate_spans` / `get_datadog_trace` | Latency spikes, error spans, **top DB/search workloads** |
| Span aggregation | `aggregate_spans` | Top resources / query patterns by count or p95 in window |
| DBM skills | `load_datadog_skill` (`datadog/dbm-*`) + `get_datadog_metric` | Top queries by `query_signature` when DBM enabled |
| Incidents | `search_datadog_incidents` / `get_datadog_incident` | Declared incidents in window |
| SLOs | `search_datadog_slos` | SLO status and error-budget breach during window (optional) |
| Dashboards | `search_datadog_dashboards` | Deep links for report |
| RUM (browser / UX) | `aggregate_rum_events` / `search_datadog_rum_events` | Client-side errors, slow views, faulty user flows — see below |

**Datadog RUM — when to use:** query RUM when symptoms may originate from **client-side or user
behavior** (browser errors, slow page loads, broken UI flows) or when server-side signals (logs, APM,
metrics) are clean but users still report impact. RUM **supplements** server telemetry — it does not
replace deploy correlation or infra metrics. If RUM tools are absent in Phase 0, note in **Gaps**.

**CWJ / JVM watchdog:** when JVM search nodes show stall patterns without query text, see
[query-playbook.md](query-playbook.md) §CloudWatch / JVM watchdog — heuristic list + user override.

**Setup:** Run **ddsetup** skill if tools missing. Load `datadog/logs`, `datadog/traces`,
`datadog/metrics`; load RUM/ddsql guidance when investigating frontend or UX-origin symptoms.

### KubeSense (`user-kubesense`)

**Official workflow:** install and read the **`kubesense-mcp`** skill ([dependencies.md](../dependencies.md)).
Nested **`kubesense-logs`**, **`kubesense-apm`**, **`kubesense-metrics`** for datasource-specific queries.
Do not guess field names — discovery-first per the official skill.

| Tool | RCA use |
|------|---------|
| `get-trace-or-log-fields` | **Required before first log/trace query** — discover field names |
| `analyze-logs` | Error count by workload/level; log coverage fallback when Datadog empty |
| `search-logs` | Raw log samples (max 10 rows) — include `body` in `fields` for message text |
| `incident-rca/scripts/kubesense_logs.py` | **Fallback** — SPL REST when MCP `body` fetch fails |
| `analyze-traces` | p95 latency by workload/service |
| `search-traces` | Failed trace samples; endpoint attribution |
| `analyze-metrics` | Pod restarts, CPU throttle |
| `get-available-metrics` | Discover metric names |

**Field mapping heuristics** (confirm via `get-trace-or-log-fields`):

| Generic / Datadog | KubeSense (varies by cluster) |
|-------------------|-------------------------------|
| `service:<name>` | `workload`, `server`, or `service` — **mpokket uses `workload` only** |
| `status:error` | `level = 'ERROR'` |
| log message / URI / query text | MCP `search-logs` with `body` field; filter with `body LIKE '%…%'` |

**Org profile — mpokket:** application logs are **not ingested to Datadog** (`logs_primary: kubesense`).
Read **`kubesense-logs`** skill; use 15–30 min windows for `search-logs`; retry once on fetch errors.
If MCP `body` fails → [kubesense-spl.md](kubesense-spl.md). Full recipes:
[query-playbook.md](query-playbook.md) §KubeSense → Org profile — mpokket.

**Log workflow (mpokket):** KubeSense `analyze-logs` + MCP `search-logs` with `body` — **do not** query
Datadog logs or record `log_coverage_gap` for Datadog 0 rows.

**Log coverage fallback (other orgs):** when Datadog returns 0 rows for a blast-radius service and
KubeSense is ✅, mandatory KubeSense MCP (official skill workflow) before Phase 2. SPL CLI only if MCP
`body` fails. Distinguish:
- `mcp_process_failure` — agent skipped KubeSense while connected
- `observability_backend_error` — KubeSense called but backend returned "unable to fetch logs" **after
  one retry** with a narrower window

Use when Datadog unavailable or for cross-validation.

### Grafana / Prometheus MCP servers (not supported in v1)

| Server | Required | v1 behavior |
|--------|----------|-------------|
| Grafana MCP | optional | ❌ Not supported in v1 — use Datadog dashboards/metrics only; do not call Grafana MCP |
| Prometheus MCP | optional | ❌ Not supported in v1 — use Datadog metrics; document gap in report |

When Datadog and KubeSense are both absent, use the **oss-obs** path below (manual PromQL/LogQL or user-pasted
query results) — not dedicated Grafana/Prometheus MCP tool calls.

### Grafana / Prometheus / Loki (OSS stack — degraded mode)

When **neither Datadog nor KubeSense** is connected but the user has Grafana, Prometheus, or Loki MCP
tools (or can run queries manually), use this **oss-obs** path instead of stopping:

| Capability | Typical tool / query | RCA use |
|------------|---------------------|---------|
| Error rate / request metrics | Prometheus `rate(http_requests_total{status=~"5.."}[5m])` | Symptom confirmation |
| Latency | Prometheus histogram `_bucket` p95 | Latency spike |
| Log top-N | Loki `sum by (message) (count_over_time({service="<svc>"} \| json \| status="error"[1h]))` | Error messages |
| Deploy markers | Prometheus `changes()` or Grafana annotations | Change correlation (weaker than Datadog) |
| Dashboards | Grafana dashboard UID + panel | Deep links in report |

**Degraded profile:** announce `oss-obs` — cap confidence at **MEDIUM** (single stack, no change-story
integration unless Jenkins/GitLab present). Label all Prom/Loki signals `source: prometheus` or
`source: loki` in evidence JSON.

If no OSS MCP exists, ask the user to paste PromQL/LogQL results or run queries in Grafana — do not
fabricate metrics.

## Change management

### GitLab (`user-gitlab`)

| Tool | RCA use |
|------|---------|
| `list_merge_requests` | MRs **merged** in window (`state: merged`, `updated_after`/`updated_before`) |
| `get_commit` | Author, message; match a deploy SHA to its commit/MR |
| `get_commit_diff` | Blast radius for suspect SHA |

> **No `list_deployments`** in this toolset — build the deploy timeline from Datadog
> `get_change_stories` (preferred) and Jenkins, with merged MRs as the GitLab fallback. Only use
> `list_deployments` / pipeline tools if your specific GitLab MCP exposes them (verify in Phase 0).

### Jenkins (`user-jenkins`)

| Tool | RCA use |
|------|---------|
| `findJobsWithScmUrl` | Map repo → prod job |
| `getBuild` | Build timestamp, result |
| `getBuildScm` | Commit SHA |
| `getBuildChangeSets` | Change summary |
| `searchBuildLog` | Deploy failure keywords |
| `getBuildLog` | Full log for failed deploy |

## Tickets

### Jira (`user-Atlassian-MCP-Server`)

| Tool | RCA use |
|------|---------|
| `getAccessibleAtlassianResources` | Obtain `cloudId` |
| `searchJiraIssuesUsingJql` | Tickets in window |
| `getJiraIssue` | Details, comments |
| `getTeamworkGraphContext` | Related people/projects (optional) |

**Read-only for RCA** — do not transition or comment unless user explicitly asks.

## Phase 0 detection checklist

```
1. List available MCP servers (match host when more than one GitLab/Atlassian instance).
2. Datadog OR KubeSense present?  → observability OK (need at least one)
3. Datadog get_change_stories OR Jenkins OR GitLab list_merge_requests present?  → deploy correlation OK
4. Jenkins getBuildScm present?  → SHA linking OK
5. Jira searchJiraIssuesUsingJql present?  → ticket context OK
6. incident-rca CLI on PATH (incident-rca --help)?  → correlator OK (else manual scoring)
7. Announce profile and missing sources.
```

Example announcement:

> **RCA MCP profile:** Datadog ✅ (queried) | KubeSense ✅ (attempted — no rows) | GitLab ✅ | Jenkins ✅ | Jira ✅ | CLI ✅

Profile suffixes: `(queried)` / `(attempted — no rows)` / `❌` — never *(not queried — Datadog sufficient)*.

## Degraded modes

| Mode | Available | Limitation |
|------|-----------|------------|
| **full** | All sources + CLI | Best confidence |
| **obs-only** | Datadog/KubeSense only | No deploy correlation |
| **oss-obs** | Prometheus/Loki/Grafana (+ optional GitLab/Jenkins) | No Datadog change stories; cap MEDIUM |
| **change-only** | GitLab/Jenkins only | No symptom confirmation |
| **manual** | MCP only, no CLI | Agent scores hypotheses manually |

## Datadog API rate limits

Multiple `analyze_datadog_logs` / metric calls across phases can hit rate limits (429 / quota errors).

| Response | Action |
|----------|--------|
| **429 / rate limit** | Wait **30s**, retry once with narrower query (shorter window, LIMIT 5) |
| **Second 429** | Skip remaining Datadog log aggregations; note in Gaps *"Datadog rate limited — partial log analysis"* |
| **Quota exhausted mid-phase** | Complete current phase with available data; offer partial report; do not retry in a tight loop |
| **Auth errors** | Run **ddsetup** / **ddconfig** — not a rate limit |

Prefer one broad `analyze_datadog_logs` GROUP BY over many narrow calls. Batch metric queries when the MCP supports it.
