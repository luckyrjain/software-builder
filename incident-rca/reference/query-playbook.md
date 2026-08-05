# Query Playbook — Incident RCA

Recipes for each MCP source with evidence JSON mapping.

**Variables:** `<from>`, `<to>` (ISO 8601 UTC), `<service>`, `<symptom>`, `<env>` (default `production`).

**Telemetry (required on every Datadog MCP call):** `search_datadog_logs`, `analyze_datadog_logs`,
`get_change_stories`, `get_datadog_metric`, `get_datadog_metric_context`, `search_datadog_incidents`,
etc. all require a `telemetry` object with a one-line English `intent`. Never include secrets, tokens,
or raw tag values. Each Datadog recipe below carries the block — keep it on real calls:

```json
"telemetry": {"intent": "<why this query for the RCA, no secrets>"}
```

---

## Datadog

Use **logs, APM traces, metrics, SLOs, change stories, and incidents** as primary server-side sources.
Add **RUM** when symptoms may come from **faulty user behavior**, client-side errors, or UX degradation
that server telemetry alone does not explain ([mcp-capabilities.md](mcp-capabilities.md)).

### Error rate spike

**Resolve the real metric first — do not guess.** Error/latency metric names vary by framework
(`trace.servlet.request.errors`, `trace.http.request.errors`, custom). Discover the actual name with
`get_datadog_metric_context` (or `search_datadog_metrics`) before querying:

```text
search_datadog_metrics: "<service> request errors"   # discover candidate metric names
get_datadog_metric_context on the chosen metric        # confirm tags (service vs base_service, env)
```

Then query the resolved metric, comparing the incident window to the prior 24h baseline:

```text
Metric: <resolved_error_metric>{service:<service>,env:<env>}   # e.g. trace.servlet.request.errors
telemetry: {"intent": "compare error rate in the incident window vs 24h baseline"}
```

**Map to JSON:**
```json
{
  "source": "datadog",
  "service": "<service>",
  "signal_type": "error_rate",
  "detected_at": "<first_spike_utc>",
  "magnitude": "<rate> (baseline <baseline>)",
  "sample_messages": [],
  "link": "https://app.datadoghq.com/apm/traces?query=service%3A<service>",
  "raw_summary": "Error rate elevated from <baseline> to <peak>"
}
```

### Latency spike

```text
Metric: <resolved_latency_metric>{service:<service>,env:<env>}   # e.g. trace.servlet.request.duration.p95
```

`signal_type`: `"latency_p95"` (resolve the metric name via `get_datadog_metric_context` first).

### SLO breach

When Datadog SLOs are configured for the service (optional Phase 1 check):

```text
search_datadog_slos: query="service:<service>"
telemetry: {"intent": "check SLO status during the incident window"}
```

If SLOs exist, check breach status and error budget consumed during `[from, to]`.

**Map to JSON:**

```json
{
  "source": "datadog",
  "service": "<service>",
  "signal_type": "slo_breach",
  "detected_at": "<breach_start_utc>",
  "magnitude": "<error_budget_consumed_pct>",
  "sample_messages": ["SLO <name> breached for <duration>"],
  "link": "<datadog_slo_url>",
  "raw_summary": "SLO <name> breached; error budget <consumed>"
}
```

### Top error messages (counts) — `analyze_datadog_logs`

Use SQL `GROUP BY` for any count / top-N — **not** `search_datadog_logs`:

```json
{
  "sql_query": "SELECT message, count(*) AS n FROM logs GROUP BY message ORDER BY n DESC LIMIT 10",
  "filter": "service:<service> status:error env:<env>",
  "from": "<from>", "to": "<to>",
  "telemetry": {"intent": "rank the top error messages for an RCA"}
}
```

Map the top rows → `error_signals[].sample_messages` and `magnitude` (counts).

### Raw log samples — `search_datadog_logs`

For sample lines / stack traces only (its description says do NOT use it for counting):

```json
{
  "query": "service:<service> status:error env:<env>",
  "from": "<from>", "to": "<to>",
  "telemetry": {"intent": "pull a few raw error log samples for the RCA evidence"}
}
```

### Org-wide error discovery (symptom-only) — `analyze_datadog_logs`

When no service is given, find the top affected services, then take the **top 3**:

```json
{
  "sql_query": "SELECT service, count(*) AS n FROM logs GROUP BY service ORDER BY n DESC LIMIT 10",
  "filter": "status:error env:<env>",
  "from": "<from>", "to": "<to>",
  "telemetry": {"intent": "find the services with the most errors in the incident window"}
}
```

### Change events — `get_change_stories`

Deploys, k8s manifest/scale, feature flags, and crashloops for the service in the window (Phase 2
preferred source):

```json
{
  "service_name": "<service>",
  "start_ts": "<from_minus_30min>",
  "end_ts": "<to>",
  "env": "<env>",
  "story_types": ["deployment", "kubernetes", "scale", "feature_flag", "crashloopbackoff"],
  "telemetry": {"intent": "list deploy/k8s/scale change events to correlate with the incident"}
}
```

Map each story → `deploy_events[]` (`deployed_at`, `change_summary`, `services`, `link`) or
`infra_signals[]` (for `kubernetes`/`scale`/`crashloopbackoff`). Absence of a story does **not** prove
nothing changed — note the limitation.

### Declared incidents — `search_datadog_incidents`

Seed the window/service from any Datadog incident already declared:

```json
{
  "query": "<service> OR <symptom>",
  "telemetry": {"intent": "find declared Datadog incidents overlapping the window"}
}
```

Use the incident's timestamps to refine the window and `get_datadog_incident` for details.

### RUM — client-side / user-behavior symptoms

**When to query:** user-reported UI issues, browser/frontend errors, slow page loads, checkout or form
failures visible only in the browser, or server-side APM/logs look healthy while impact persists.
Symptoms may reflect **faulty user behavior** (repeated submits, rage clicks, stale client state) or
client bugs — RUM helps distinguish these from backend outages.

**Counts / top-N / time series → `aggregate_rum_events`** (not `search_datadog_rum_events`):

```json
{
  "query": "@type:error env:production @application.name:\"<app>\"",
  "computes": [{"aggregation": "COUNT", "field": "*", "output": "error_count"}],
  "group_by": [{"field": "@view.url_path", "limit": 10}],
  "from": "<from>",
  "to": "<to>",
  "telemetry": {"intent": "RUM error counts by page during incident window"}
}
```

**Raw samples / attribute discovery → `search_datadog_rum_events`** (limit small — not for aggregation):

```json
{
  "query": "@type:error @view.url_path:*/checkout/*",
  "from": "<from>",
  "to": "<to>",
  "limit": 5,
  "telemetry": {"intent": "sample RUM client errors on checkout during incident"}
}
```

Common filters: `@type:error`, `@type:view @view.loading_time:>5000000000` (>5s, nanoseconds),
`@type:operation @operation.status:failure`, `@user.id:<id>` when a specific reporter is known.

Map to evidence JSON as `error_signals[]` with `source: "datadog_rum"` and deep link to RUM explorer.
Note in the report when the **immediate trigger** may be client-side or user-driven rather than a
backend deploy or infra failure.

### Infra signals

| Signal | Metric / query | `signal_type` |
|--------|----------------|---------------|
| OOM | `kubernetes.containers.state.terminated{reason:oom*` | `oom` |
| Pod restart | `kubernetes.containers.restarts` | `pod_restart` |
| HPA max | `kubernetes.hpa.current_replicas` vs max | `hpa_max` |
| CPU throttle | `container.cpu.throttled` | `cpu_throttle` |
| Kafka lag | `avg:kafka.consumer_lag{service:<service>,env:<env>}` / `max:kafka.consumer_lag{...}` | `kafka_lag_spike` |
| Kafka lag (KubeSense) | `analyze-metrics: kafka consumer lag for <service> in window` | `kafka_lag_spike` |

---

## KubeSense

**Read `kubesense-mcp` + `kubesense-logs` skills** ([dependencies.md](../dependencies.md)) before querying.
Run `get-trace-or-log-fields` with `datasource: logs` (and `datasource: traces` when querying traces)
**before** the first filter query. Map discovered fields to filters — common heuristics:

| Datadog / intent | KubeSense field (confirm via discovery) |
|------------------|----------------------------------------|
| `service:<name>` | `workload = '<name>'` **or** `server = '<name>'` **or** `service = '<name>'` |
| log message / body | MCP `search-logs` with `body` in `fields`; `body LIKE '%…%'` filters |
| `status:error` | `level = 'ERROR'` (uppercase on some clusters) |
| env tag | `env` or `environment` or `namespace` |

Do not guess field names — discovery output is authoritative for this cluster.

**Default profile selection:** when discovery lists `workload` and org confirms logs are KubeSense-only,
apply the **mpokket** org profile below. Discovery may omit `body` even when MCP returns it — still
request `body` in `search-logs` per the official skill.

### Org profile — mpokket

Use when `get-trace-or-log-fields` shows `workload` and **no** `service` / `message` fields — or when
the user confirms **logs are not stored in Datadog** (KubeSense is the **primary and only** log source).

| Log source | mpokket |
|------------|---------|
| **Application / access logs** | **KubeSense only** — do not ingest to Datadog |
| **Datadog Logs** | **Not used** — `analyze_datadog_logs` / `search_datadog_logs` for `sample_messages` or query text will return **0 rows by design** |
| **Datadog APM + metrics** | **Used** — traces, metrics, change stories, RUM |
| **Log bodies / query strings** | **MCP `search-logs` with `body`** per **`kubesense-logs`** skill; SPL CLI fallback |

Set `kubesense_schema_profile: "mpokket"` and `logs_primary: "kubesense"` in evidence JSON.

**Do not** record `log_coverage_gap` for Datadog returning 0 log rows on mpokket — that is **expected**,
not missing telemetry. Record instead:

```json
{
  "signal_type": "logs_source_profile",
  "source": "org_profile",
  "finding": "mpokket — KubeSense primary; Datadog logs not ingested"
}
```

| Intent | Field / filter | Notes |
|--------|----------------|-------|
| Service identity | `workload` | e.g. `workload = 'autodebit-service'` — **not** `service` |
| Error level | `level = 'ERROR'` | Uppercase |
| Namespace / cluster | `namespace`, `cluster` | Scope blast radius |
| Pod / container | `pod_name`, `container`, `node_name` | Infra correlation |
| Log format / size | `format`, `body_length` | Metadata; request `body` in `search-logs` fields for text |
| **Absent in discovery** | `service`, `message` | May still request `body` in `search-logs` — confirm via MCP |

**Log text via MCP:** read **`kubesense-logs`** skill. `search-logs` with `body` in `fields` (15–30 min
windows). Filter with `body LIKE '%keyword%'` when hunting query strings. SPL CLI only when MCP body
fetch fails — see [kubesense-spl.md](kubesense-spl.md).

**Workflow for log text (mandatory on mpokket when RCA needs query strings, URIs, client channel, or
`sample_messages`):**

1. Read **`kubesense-mcp` + `kubesense-logs`** skills ([dependencies.md](../dependencies.md)).
2. `analyze-logs` — error **counts** by `workload` / `namespace` / `level` (≤1h windows).
3. **`search-logs` with `body`** — full message text via MCP (15–30 min windows; retry once).
4. **`scripts/kubesense_logs.py --evidence`** — only if step 3 fails ([kubesense-spl.md](kubesense-spl.md)).
5. Datadog APM — endpoint / resource attribution when logs confirm the path.

Do **not** treat empty Datadog log queries as a investigation blocker — go straight to steps 1–2.

Record `kubesense_schema_profile: "mpokket"` and `logs_primary: "kubesense"` in evidence.

**Time windows:** keep `analyze-logs` windows **≤1 hour** per call. Heavy `groupBy` queries on wider
windows can timeout (~2.5 min). Split the incident window into 1h slices and merge top workloads.

**Transient fetch errors:** if KubeSense returns "unable to fetch logs", **retry once** with a narrower
window (e.g. last 30–60 min of the slice). Only after retry fails → `observability_backend_error`.

### Error count by workload

**Tool:** `analyze-logs` — use `workload` when discovery shows it (mpokket default).

```json
{
  "from_time": "<from>",
  "to_time": "<to_max_1h_later>",
  "queryType": "range",
  "filters": "level = 'ERROR'",
  "groupBy": [{"field": "workload", "type": "string"}],
  "aggregation": {"function": "row_count"},
  "sorting": {"sortBy": {"field": "row_count", "type": "float"}, "sortOrder": "DESC"}
}
```

**Org-wide discovery:** omit workload filter; take top 3 workloads by error count. For long windows,
repeat in 1h slices.

**Scoped error count:**

```text
level = 'ERROR' AND workload = 'user-metadata-service'
```

### Error breakdown by workload (no message text)

When `message` / `body` are absent, **do not** GROUP BY message. Instead:

```json
{
  "filters": "level = 'ERROR' AND workload = '<workload>'",
  "groupBy": [
    {"field": "workload", "type": "string"},
    {"field": "namespace", "type": "string"},
    {"field": "pod_name", "type": "string"}
  ],
  "aggregation": {"function": "row_count"}
}
```

Map magnitude → `error_signals[].magnitude` (counts). Leave `sample_messages` empty or use synthetic
summaries only when backed by counts, e.g. `"ERROR count 1,240 on workload user-metadata-service"`.
Do **not** fabricate error text.

### Trace latency

**Tool:** `analyze-traces` — map service filter to discovered trace field (`workload`, `service`, or
`server` per discovery).

```json
{
  "filters": "workload = '<workload>'",
  "groupBy": [{"field": "workload", "type": "string"}],
  "aggregation": {
    "function": "p95",
    "fields": [{"field": "duration", "type": "float"}]
  }
}
```

### Sample error logs

**Tool:** `search-logs` — per **`kubesense-logs`** skill: include `body` in `fields` for message text.
Use 15–30 min windows. Prefer `analyze-logs` counts for evidence strength.

**SPL fallback (when MCP body fails):** see [kubesense-spl.md](kubesense-spl.md).

```bash
python3 scripts/kubesense_logs.py <workload> \
  --cluster <cluster> --namespace <namespace> \
  --from <from_time> --to <to_time> --limit 10 --evidence
```

API: `POST /api/logs/spl/execute`. Auth: `X-API-Key` / `KUBESENSE_API_KEY`.

---

## Log coverage — KubeSense-primary (mpokket)

**When `logs_primary: kubesense` or mpokket profile applies:** skip Datadog log queries for
`sample_messages` and query text — they are **N/A**, not empty. Run KubeSense directly.

For each blast-radius service **S** (primary + ES callers + dependency tree):

| Step | Action |
|------|--------|
| 0 | Read **`kubesense-mcp` + `kubesense-logs`** skills |
| 1 | `get-trace-or-log-fields` (`datasource: logs`) — map `workload`, `cluster`, `namespace` |
| 2 | `analyze-logs` — error counts on `workload = '<S>'` — **≤1h slices** |
| 3 | **`search-logs` with `body`** — when text needed (query strings, URIs, client channel, errors) |
| 4 | **`kubesense_logs.py --evidence`** — only when step 3 fails |
| 5 | On expensive-query / wildcard incidents — MCP `body LIKE` on **onset slice**; SPL if MCP fails |

| Engine in blast radius | KubeSense attempt |
|------------------------|-------------------|
| OpenSearch / Elasticsearch top callers | **Mandatory** |
| Any service where trigger needs log text | **Mandatory MCP body**; SPL before `kubesense_metadata_only` gap |

**Gate:** do not enter Phase 2 on ES saturation until KubeSense counts **and** MCP body attempted (SPL
if MCP fails) when query text / `sample_messages` are required.

Append `evidence_links[]`:

- `{ "signal_type": "logs_source_profile", "finding": "KubeSense primary — Datadog logs N/A" }`
- `{ "signal_type": "mcp_process_failure", ... }` — only when KubeSense or SPL **skipped** while ✅
- `{ "signal_type": "observability_backend_error", ... }` — KubeSense/SPL backend error after retry

**Do not** use `log_coverage_gap` with `source: datadog` on mpokket — mislabels expected N/A as a gap.

### Log coverage fallback (other orgs — Datadog + KubeSense)

When the org **does** ingest Datadog logs and `analyze_datadog_logs` returns **0 rows** for service S:

| Engine in blast radius | KubeSense attempt |
|------------------------|-------------------|
| OpenSearch / Elasticsearch | **Mandatory** when KubeSense ✅ |
| ES/OpenSearch top-3 upstream callers (first 10m) | **Mandatory** when Datadog empty for caller |
| Redis / Kafka | **Recommended** when Datadog empty for caller |

**Workflow:**

1. Read **`kubesense-logs`** skill — discovery-first MCP workflow.
2. `get-trace-or-log-fields` → map fields (default to **workload** when `service` absent).
3. `analyze-logs` on S — **≤1h windows**; retry once on fetch error with narrower slice.
4. `search-logs` with `body` when message text needed; SPL CLI if MCP body fails.
5. If still 0 rows: record `(attempted — no rows)` in MCP profile update.
6. Append `evidence_links[]`:
   - `{ "signal_type": "log_coverage_gap", "service": "<S>", "source": "datadog", "finding": "0 log rows in window" }`
   - `{ "signal_type": "mcp_process_failure", ... }` — only when KubeSense was **skipped** while ✅
   - `{ "signal_type": "observability_backend_error", ... }` — when KubeSense **was called** but returned "unable to fetch logs" or equivalent (backend/MCP error — **not** a process skip)

**Gate:** do not enter Phase 2 until mandatory KubeSense attempts complete when triggered.

**Parallel caller log pivot:** when a top `@base_service` caller is identified:

- **mpokket / KubeSense-primary:** KubeSense MCP `body` (+ SPL fallback) in parallel with Datadog APM —
  **do not** wait for Datadog logs.
- **Other orgs:** Datadog logs + KubeSense when Datadog empty — see [query-investigation.md](query-investigation.md).

---

## GitLab

> **No `list_deployments`** in this toolset. The deploy timeline comes from Datadog `get_change_stories`
> (preferred) and Jenkins; GitLab is the **fallback** for matching a deploy to a merged MR. Only use
> `list_deployments` if your specific GitLab MCP actually exposes it (verify in Phase 0).

### Merged MRs in window

**Tool:** `list_merge_requests`

```json
{
  "project_id": "<group/project>",
  "state": "merged",
  "updated_after": "<from_minus_30min>",
  "updated_before": "<to>",
  "order_by": "updated_at",
  "sort": "desc",
  "per_page": 50
}
```

**Map to JSON:**
```json
{
  "source": "gitlab",
  "deployed_at": "<mr.merged_at or deploy timestamp>",
  "project": "<group/project>",
  "environment": "<env>",
  "sha": "<mr.merge_commit_sha or sha from change story/Jenkins>",
  "change_summary": "<MR title>",
  "mr_url": "<mr.web_url>",
  "mr_iid": 482,
  "services": ["<apm_service_name>"],
  "link": "<mr.web_url>"
}
```

### Match a deploy SHA → MR / commit

Given a SHA from `get_change_stories` or Jenkins `getBuildScm`, confirm it with `get_commit` and find
the owning MR among the merged MRs above. Match in order:
1. `merge_commit_sha == sha`
2. `squash_commit_sha == sha`
3. `sha` is the MR's head/source commit

### Blast radius (code change)

**Tool:** `get_commit_diff` for the suspect SHA → summarize in `change_summary`. Confirm the diff
touches the failing path before calling the deploy the cause.

### Blast radius (dependency / multi-service)

When ≥2 application services show errors, map downstream impact for the report **Blast radius** section:

1. **Primary service** — the service under investigation or the saturated dependency (engine).
2. **APM service map** — `search_datadog_spans` or service dependency tags (`peer.service`, `@http.url`).
3. **Error log GROUP BY service** — `analyze_datadog_logs` in window; list co-spiking services.
4. **Upstream mandate** — when OpenSearch/ES, Redis, or Kafka is in blast radius: `aggregate_spans`
   GROUP BY `@base_service` in the **first 10 min**; record top-3 callers (see [query-investigation.md](query-investigation.md)).
5. **Tickets** — Jira/PD titles naming multiple services.

Render as tree or table:

```text
<root dependency — e.g. opensearch-cluster>
├── <top-caller-1>  ← upstream (first 10m)
├── <top-caller-2>
├── <top-caller-3>
├── onboarding-api  ← downstream impact
├── crm-api
└── metadata-api
```

For `dependency_failure`, combine with [Multi-hop cascade analysis](#multi-hop-cascade-analysis-dependency_failure) — tree shows **who failed**; cascade shows **why**.

---

## Infra capacity snapshot

When `infra_capacity` is primary or strong alternate, query or cite these series for the incident window
(compare to prior day or baseline when useful). Mark **N/A** if unavailable:

| Metric | Typical source | Notes |
|--------|----------------|-------|
| CPU % / CPU per core | host or container metrics | Saturation driver |
| Request rate / throughput | APM or engine metrics | Collapse vs spike |
| Latency p95/p99 | APM or engine | User-visible degradation |
| Queue depth / consumer lag | engine or broker metrics | Backpressure signal |
| Thread pool active / rejected | JVM or OpenSearch thread pools | Mechanism evidence |
| Shard count / node count | cluster stats | Capacity context |
| Heap % / GC pause time | JVM metrics | Rule out GC-driven failures |
| Disk IOPS / iowait | host metrics | Storage-bound saturation |

Prefer a **Key metrics snapshot** table (minute or 5-min buckets) in Phase 5 — see
[root-cause-depth.md](root-cause-depth.md) and [report-template.md](../report-template.md).

### Trigger workload analysis (search / DB)

When saturation involves a query engine, run the full pipeline in
[query-investigation.md](query-investigation.md) — do not skip to **Unknown** without attempting APM
spans, log aggregation, and DBM (when available). Summary recipes below; detail in that doc.

**OpenSearch/Elasticsearch — Phase 1 required pass (`aggregate_spans`):**

```text
aggregate_spans:
  query: "service:elasticsearch env:production"
  group_by: ["resource_name", "@base_service"]
  computes: COUNT, P95(@duration)
```

If empty, retry `@db.system:elasticsearch` with `group_by: ["resource_name", "service"]`. Populate
**Query execution profile** in the report before Phase 2. Phase 3 continues with logs and slowlog gaps.

**APM top workloads — other engines or supplemental ES attribution:**

```text
aggregate_spans:
  query: "env:production @db.system:elasticsearch"
  group_by: ["resource_name", "service"]
  computes: COUNT, P95(@duration)
```

**Slow span samples — `search_datadog_spans`:**

```text
search_datadog_spans:
  query: "@duration:>5000000000 @db.system:elasticsearch"
  sort: -@duration
  limit: 5
```

**Logs — `analyze_datadog_logs`:** GROUP BY messages containing `slowlog`, `rejected_execution`,
`took_millis`, or query text.

**DBM:** `load_datadog_skill` (`datadog/dbm-postgresql`, `datadog/dbm-mysql`, …) + per-skill query
metrics for top `query_signature` in window.

**Dashboard:** [Database Slow Query](https://app.datadoghq.com/dashboard/uwk-w92-5ys/database-slow-query)
(`search_datadog_dashboards` title `database-slow-query`; fast-path ID `uwk-w92-5ys` when title
confirms) — top slow queries and client attribution during DB saturation RCA.

Record results in report **Query execution profile** (OpenSearch/ES Phase 1) and **Executed queries
investigated** and `query_signals[]`.

When saturation + flat/<2× throughput, run **expensive-query onset signature** (Phase 1 mandatory) —
see [query-investigation.md](query-investigation.md) §Phase 1 — Expensive-query onset signature and
[thresholds.md](thresholds.md).

### Expensive-query onset — metric recipes (OpenSearch / AWS ES)

Run at **`from_time` − 5m → `from_time` + 10m** in **1-minute** buckets:

```text
get_datadog_metric:
  queries:
    - avg:aws.es.cpuutilization.maximum{domainname:<domain>}
    - sum:aws.es.elasticsearch_requests{domainname:<domain>}.as_count()
    - sum:aws.es.threadpool_search_rejected{domainname:<domain>}.as_count()
```

Caller baseline (top `@base_service` from APM):

```text
get_datadog_metric:
  queries:
    - sum:trace.servlet.request.hits{service:<caller>,env:production}.as_count()
  from: <from_time - 5m>
  to: <from_time + 10m>
```

Repeat with `from` shifted **−24h** for baseline comparison.

**Interpretation:** CPU ≥2× while `elasticsearch_requests` flat or **declining** → expensive-query
signature; deny `traffic_spike` primary.

---

## Client channel vs JVM watchdog — CWJ disambiguation

**Do not confuse:**

| Meaning | Examples | Use |
|---------|----------|-----|
| **Client channel / product code** | `CWJ` as app client sending API requests; channel tags in access logs | Map to `query_signals[].client_service` or `evidence_links[].finding` |
| **JVM / stall watchdog** | `watchdog`, long GC, JVM stall metrics in engine logs | Heuristics below |

When the user says "query came from CWJ", treat it as **client attribution** — hunt in application
logs/SPL for that channel on the API endpoint (e.g. `master-data/company`), not JVM watchdog metrics.

---

## CloudWatch / JVM watchdog heuristics

When JVM-based search/DB engines show saturation without clear query text, check watchdog / long-GC /
thread-pool stall patterns in logs and metrics. **Heuristic indicators** (adapt to your stack):

| Pattern | Log / metric hint |
|---------|-------------------|
| Watchdog stall | `watchdog`, `jvm`, `stall`, `not responding` |
| Long GC pause | `GC pause`, `Full GC`, pause >5s in logs |
| Thread pool exhaustion | `rejected_execution`, `queue capacity`, `pool size` |
| Heap pressure without OOM | `heap usage`, `old gen`, sustained >85% |

**User override:** if the user names a specific CWJ metric, log field, or dashboard, prefer that source
over the heuristic list and record the override in `query_references[]`.

Query Datadog logs/metrics first; pivot to KubeSense per §Log coverage fallback when Datadog empty.

---

## Jenkins

### Find prod job

**Tool:** `findJobsWithScmUrl`

```json
{ "scmUrl": "git@gitlab.example.com:group/project.git" }
```

### Build in window

**Tool:** `getBuild` — iterate recent build numbers; filter by `timestamp` in window.

**Tool:** `getBuildScm` → `sha` for `deploy_events[].sha`

**Tool:** `getBuildChangeSets` → files/authors for `change_summary`

**Tool:** `searchBuildLog` — keywords: `error`, `failed`, `rollback`

**Map to JSON:** same as GitLab deploy event with `"source": "jenkins"`.

---

## Jira

### Obtain cloud ID

**Tool:** `getAccessibleAtlassianResources` → use first `cloudId`.

### Incidents in window

**Tool:** `searchJiraIssuesUsingJql`

```text
project IN (INC, OPS) AND created >= "<from_date>" AND created <= "<to_date>"
AND (summary ~ "<symptom>" OR description ~ "<symptom>" OR labels = "<service>")
ORDER BY created DESC
```

**Map to JSON:**
```json
{
  "key": "INC-4521",
  "summary": "...",
  "status": "Investigating",
  "priority": "P1",
  "created_at": "2026-06-28T14:50:00Z",
  "link": "https://<site>.atlassian.net/browse/INC-4521",
  "comment_snippets": ["..."]
}
```

### Anchor from ticket

**Tool:** `getJiraIssue` when user provides `INC-4521`:
- Parse description/comments for timestamps
- Override `window.from_time` / `window.to_time` if ticket specifies

---

## Known issues cross-check (optional)

Only if the user points to a `KNOWN_ISSUES.md` (use a **repo-relative** path they provide — do not
assume an absolute path or that the file exists). If a symptom matches, record:

```json
{
  "issue_id": "KI-03",
  "title": "...",
  "severity": "HIGH",
  "matched_symptoms": ["stuck disbursement", "retry loop"],
  "link": "KNOWN_ISSUES.md#ki-03"
}
```

---

## PagerDuty / OpsGenie

### PagerDuty — list incidents in window

**Tool:** `pd_list_incidents` (or `pagerduty_list_incidents` — name depends on MCP server)

```json
{
  "statuses": ["triggered", "acknowledged", "resolved"],
  "since": "<from_time>",
  "until": "<to_time>",
  "service_ids": ["<pd_service_id>"]
}
```

To find `pd_service_id`: use `pd_list_services` filtered by service name if available, or ask the user.

**Map to `pd_alerts[]`:**
```json
{
  "source": "pagerduty",
  "alert_id": "<incident.id>",
  "title": "<incident.title>",
  "severity": "<incident.urgency or priority.name>",
  "triggered_at": "<incident.created_at>",
  "acknowledged_at": "<incident.acknowledged_at or null>",
  "resolved_at": "<incident.resolved_at or null>",
  "link": "<incident.html_url>"
}
```

Use `triggered_at` as a more accurate `from_time` anchor than Jira `created_at` when it precedes
the current window start.

### OpsGenie — list alerts in window

**Tool:** `opsgenie_list_alerts` (or `og_list_incidents`)

```json
{
  "query": "tag:<service> OR alias:<service>",
  "createdAt": ">= <from_time>",
  "limit": 20,
  "sort": "createdAt",
  "order": "asc"
}
```

**Map to `pd_alerts[]`** (same schema, `"source": "opsgenie"`):
- `triggered_at` = `alert.createdAt`
- `acknowledged_at` = `alert.acknowledgedAt`
- `resolved_at` = `alert.closedAt`
- `severity` = `alert.priority` (P1–P5 scale)

### Window refinement from PD/OpsGenie

If the earliest `triggered_at` from `pd_alerts[]` is before `from_time`:
- Set `from_time = min(pd_alerts[].triggered_at)` (more accurate onset)
- Re-apply Phase 0b backstroke: `analysis_from_time = from_time − 15m`
- Note in Phase 5 report: *"Window refined from PagerDuty/OpsGenie alert timeline."*

---

## Multi-hop cascade analysis (`dependency_failure`)

When errors suggest A→B→C failure (timeouts, connection refused, circuit open, upstream 5xx in messages),
trace the chain beyond reading a single error line:

### Step 1 — Identify the failing leaf

- Top error messages mentioning downstream service names, hostnames, or gRPC/HTTP status from callee.
- `analyze_datadog_logs` GROUP BY `service` + message filter `timeout|connection refused|503|upstream`.

### Step 2 — Walk upstream (one hop at a time)

For each named dependency in messages:

1. Query **that service's** error rate and logs in the same window.
2. If dependency B is healthy but A fails → look at A→B integration (config, auth, wrong URL).
3. If B is also failing → repeat for B's dependencies (C, D…).

### Step 3 — Trace correlation (when APM available)

- `search_datadog_spans` / `aggregate_spans`: filter `status:error`, GROUP BY `service` and
  `@http.url` / peer service tag.
- Find the **root span** where latency/error originates vs propagated errors.

### Step 4 — Change correlation per hop

- `get_change_stories` for **each service** in the chain — a deploy on C can cascade to A callers.
- Record chain in evidence: `dependency_chain: ["service-a", "service-b", "service-c"]` with per-hop status.

### Step 5 — Hypothesis scoring

- **Root at leaf** (C unhealthy, B and A propagate) → primary `dependency_failure` on C; A/B are symptoms.
- **Root at middle** (B misconfigured, A fails, C healthy) → B is primary.
- **No hop confirmed** → keep `dependency_failure` at MEDIUM/LOW; list untested hops in Gaps.

---

## Hypothesis scoring

When the `incident-rca` CLI is present it ranks hypotheses for you. When it is absent, score by hand
with [manual-scoring.md](manual-scoring.md) (full weights + formula + worked example) and label the
report's Gaps section accordingly. Summary of signals:

| Hypothesis | Scoring signals |
|------------|-----------------|
| `deploy_regression` | Deploy/change 0–60 min before error spike; same service; diff touches failing path |
| `infra_capacity` | OOM/restarts/HPA-max/crashloop without deploy |
| `query_governance` | Expensive/wildcard query under saturation; top caller in first 10m; slowlog; no client deploy (alias: `expensive_query` in narrative) |
| `dependency_failure` | downstream/cascade in messages |
| `known_issue_match` | `known_issue_matches` populated |
| `external_third_party` | bank/kafka/timeout keywords; no deploy |
| `inconclusive` | empty or non-overlapping evidence |
| `feature_flag_regression` | Feature flag event 0–30 min before spike + error overlap | `get_change_stories` (`feature_flag` type) |
| `kafka_lag_spike` | Consumer lag > 10× normal + no deploy | `kafka.consumer_lag` / KubeSense `analyze-metrics` |

**`query_governance` detail:** see [manual-scoring.md](manual-scoring.md). Cross-hypothesis: subtract 2
from `infra_capacity` when `query_governance` raw score ≥5.

Confidence (guardrails): **HIGH** = ≥2 **independent signal types** agree + alternates stated;
**MEDIUM** = one strong signal **or** only one source responded (hard cap); **LOW** = circumstantial.

---

## CLI handoff (only if installed)

Write the complete bundle → run:

```bash
incident-rca run -i evidence.json --result-output rca_result.json --report-output rca_report.md
```

See [evidence.example.json](evidence.example.json) and
[evidence.example.opensearch-query-governance.json](evidence.example.opensearch-query-governance.json)
for examples. If `incident-rca --help` fails,
use [manual-scoring.md](manual-scoring.md) instead.
