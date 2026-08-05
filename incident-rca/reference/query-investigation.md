# Query investigation — find executed workloads

Load in **Phase 1** (OpenSearch/Elasticsearch — required) and **Phase 3** (other query engines and
follow-up). Do not leave **Immediate trigger** as **Unknown** until you have run the applicable steps
(or each step is unavailable — record what was tried).

---

## Phase 1 — OpenSearch / Elasticsearch APM pass (required)

When the **affected resource** is OpenSearch or Elasticsearch (symptom mentions search failure,
thread-pool rejections, index errors, or `infra_signals` on an ES/OpenSearch cluster), run this in
**Phase 1 immediately after** collecting error/infra signals — **before the Phase 1 checkpoint**.

This yields **index + caller + HTTP status** from client spans even when slow logs are absent.

**Tool:** `aggregate_spans` (not `search_datadog_spans` for top-N):

```text
aggregate_spans:
  query: "service:elasticsearch env:<env>"
  group_by: ["resource_name", "@base_service"]
  computes:
    - COUNT (*)
    - P95(duration)
  from/to: incident window
  telemetry: {"intent": "top ES client spans by resource and caller during incident"}
```

If `service:elasticsearch` returns empty, retry:

```text
aggregate_spans:
  query: "@db.system:elasticsearch env:<env>"
  group_by: ["resource_name", "service"]
```

**Error breakdown** — second pass or filter for failures:

```text
aggregate_spans:
  query: "service:elasticsearch status:error env:<env>"
  group_by: ["resource_name", "@base_service", "http.status_code"]
```

**Slow samples** — `search_datadog_spans` with `sort: -@duration`, `limit: 5` on the top
`resource_name` from aggregation.

Map rows → `query_signals[]` and populate report **Query execution profile** (index from
`resource_name`, caller from `@base_service` or `service`, status from span tags).

### Upstream mandate — top callers (first 10 min)

When OpenSearch, Elasticsearch, Redis, or Kafka is in **blast radius**, run a **first-10-minute**
caller attribution pass immediately after the Phase 1 APM pass (or engine-equivalent span aggregation):

```text
aggregate_spans:
  query: "service:elasticsearch env:<env>"   # or @db.system:redis / kafka client service
  group_by: ["@base_service"]
  computes: COUNT, P95(duration)
  from: window.from_time
  to: min(window.from_time + 10m, window.to_time)
  telemetry: {"intent": "top upstream callers in first 10 min of incident"}
```

Record the **top 3** `@base_service` values by span count. Populate **Blast radius** upstream table
and `query_signals[].client_service` for the leading caller. This satisfies the upstream mandate
before Phase 2 — do not wait for Phase 3.

### Parallel caller log pivot (Datadog + KubeSense)

When a top caller is identified and Datadog logs for that caller return **0 rows** in the incident
window, pivot **in parallel** (same turn when possible):

1. **Datadog** — `analyze_datadog_logs` GROUP BY message on `service:<caller> status:error`
2. **KubeSense** — when KubeSense ✅ in profile: `get-trace-or-log-fields` first, then:
   - Map caller → `workload = '<caller>'` when discovery shows `workload` and no `service` (acme)
   - Else map `service` → `server` / `service` per discovery
   - `analyze-logs`: `level = 'ERROR' AND workload = '<caller>'`, GROUP BY `workload` — **≤1h windows**
   - If discovery shows **no** `body` / `message`: **skip text search** for URIs, query strings, or
     slowlog lines. Use `analyze-logs` error **counts** by workload + `analyze-traces` /
     `search-traces` on the caller for endpoint / resource attribution instead.

**URI / query-string hunts:** when MCP discovery lists `body` or `message`, use MCP filters. When
On KubeSense-primary orgs (acme), read **`kubesense-logs`** skill — use MCP `search-logs` with
`body` or `body LIKE` filters. SPL CLI per [kubesense-spl.md](kubesense-spl.md) only when MCP body
fails. If both return no rows, state in Gaps: *"Cannot
confirm query string from KubeSense logs."* Otherwise use endpoint attribution from traces only.

**Required** for ES/OpenSearch blast-radius callers when Datadog returns empty. **Recommended** for
Redis/Kafka callers under the same condition. Record both attempts in **Investigation attempts** and
`query_references[]`. If KubeSense is skipped while ✅, add `mcp_process_failure` to `evidence_links[]`.
On transient "unable to fetch logs", retry once with a narrower window before
`observability_backend_error`.

Announce in Phase 1 checkpoint:

> **Query execution profile (APM):** top resource `<name>` from `<caller>` — N spans, p95 Xms, errors Y%.

Do **not** set immediate trigger to **Unknown** on ES incidents until this pass completes (empty
result still counts — document "APM ES span pass returned no spans" under attempts).

### Wildcard / cross-index auto-flag (same turn as APM pass)

When **any** row in the Phase 1 APM aggregation matches the patterns below, record
`signal_type: "expensive_query_candidate"` in `evidence_links[]` and **immediately** run the
**expensive-query onset signature** (next subsection) — do not wait for Phase 3.

| APM `resource_name` pattern | Risk |
|----------------------------|------|
| `POST /?/_search` or `GET /?/_search` | Cross-index wildcard — highest priority |
| `POST /*/_search` with `?` index segment | Multi-index wildcard |
| `/_search` with no index segment in path | Unscoped search |
| Leading `*` or `wildcard` in `query_text` / slowlog | Term explosion |

All spans on `POST /?/_search` from one `@base_service` during onset → treat as **query_governance**
lead until disproven.

---

## Phase 1 — Expensive-query onset signature (mandatory for ES/OpenSearch)

**When:** OpenSearch/Elasticsearch is the saturated dependency **and** any of: CPU ≥90%, thread-pool
rejections, queue at max, or HTTP **429** on `service:elasticsearch` spans.

**Run in Phase 1 immediately after** the APM pass and wildcard auto-flag — **before the Phase 1
checkpoint** and **before** ranking `traffic_spike` or pure `infra_capacity`. Detail for Step 4b
pipeline lives below; this subsection is the **onset gate** agents skipped when the acme
2026-06-21 incident was mis-attributed to BFF traffic.

### 1 — CPU vs throughput divergence (disproves volume spike)

Query **the same 1-minute buckets** for onset ±5 min (`from_time` − 5m → `from_time` + 10m):

```text
get_datadog_metric:
  - avg:aws.es.cpuutilization.maximum{domainname:<cluster>}
  - sum:aws.es.elasticsearch_requests{domainname:<cluster>}.as_count()
  telemetry: {"intent": "test expensive-query signature — CPU vs request rate at onset"}
```

Also pull the **top caller** service hit rate for the same buckets:

```text
get_datadog_metric:
  - sum:trace.servlet.request.hits{service:<top_caller>,env:<env>}.as_count()
  # or trace.netty.request.hits for Netty BFFs
```

| Observation | Interpretation | Next step |
|-------------|----------------|-----------|
| CPU ↑ ≥2× while ES `elasticsearch_requests` **flat or declining** | **Expensive-query signature** — few costly queries, not volume | Rank `query_governance` ≥ `traffic_spike`; run steps 2–4 |
| CPU ↑ and ES requests ↑ ≥2× **and** caller hits ↑ ≥2× | Legitimate traffic spike | `traffic_spike` or multi-cause with `query_governance` |
| CPU ↑, caller hits flat, ES requests flat | **Expensive-query signature** (strong) | Steps 2–4 mandatory |
| Datadog `traffic_anomaly` change story at onset **without** caller hits ↑ ≥2× | **Correlation only** — not causation | Do **not** rank traffic as primary; note in contradicting evidence |

Record in `infra_signals[]`:

```json
{
  "signal_type": "expensive_query_signature",
  "magnitude": "CPU 24%→99% while elasticsearch_requests 2659→1979/min (declining)",
  "raw_summary": "Throughput flat/declining at CPU onset — volume spike ruled out"
}
```

Announce at checkpoint:

> **Expensive-query onset signature:** [present / absent / inconclusive] — CPU vs throughput at
> `from_time`: …

### 2 — Caller volume baseline (deny traffic-spike primary)

For the **top `@base_service`** from the APM pass, compare request rate:

| Window | Metric |
|--------|--------|
| Baseline | Same clock window **24h earlier** (or 7d median if campaign day) |
| Onset | `from_time` − 5m → `from_time` + 5m |

If onset rate is **<2× baseline**, add to **contradicting evidence** for any `traffic_spike` hypothesis
and +3 toward `query_governance` per [manual-scoring.md](manual-scoring.md).

**Do not** use downstream BFF traffic anomalies as the initiating event unless **that BFF's** hit
rate also rises ≥2× at onset **and** it is the direct ES caller (usually it is not — pivot to the
service that owns the ES client spans).

### 3 — Onset-window APM slice (first ±5 min)

Re-run `aggregate_spans` on **`from_time` − 2m → `from_time` + 5m** only (not the full incident
window). Full-window aggregations **drown** a 4-request wildcard event in retry noise.

```text
aggregate_spans:
  query: "service:elasticsearch env:<env>"
  group_by: ["resource_name", "@base_service"]
  from: from_time - 2m
  to: from_time + 5m
```

Map `resource_name` → API endpoint when obvious (e.g. `POST /?/_search` ↔ company/name search
code path). Record in `query_signals[]` with `detected_at` = onset.

### 4 — Application log / query-string hunt (top caller)

When step 1 or 3 suggests `query_governance`, hunt the **query string** — not just error counts:

1. **Datadog** — only when org ingests Datadog logs (not acme).
2. **KubeSense MCP body** — **mandatory** on KubeSense-primary orgs: `search-logs` with `body` on the
   caller `workload` in the **onset slice**; SPL per [kubesense-spl.md](kubesense-spl.md) if MCP fails;
   scan `body`
   for long `name=` parameters, Unicode prose, and client-channel tags.
3. Record longest observed query length and client identifier in `query_signals[].query_text` (truncate
   to 500 chars in evidence; full text in Gaps if redacted).

**A broad/aggregate log query does not satisfy this step.** A cluster-wide or GROUP-BY-`workload`
`analyze-logs` pull (e.g. run for Phase 3 error-count corroboration) is a **different query with a
different purpose** and cannot be logged as "query-string hunt attempted" even when it returns rows.
The mandatory query here is scoped **narrowly**: single `workload` = top caller, window = onset slice
(`from_time` ±1–2 min), filter on `body` text — not error level or row count alone. A single malformed
request (as few as 1–4 rows) will not surface in a broad aggregate and must not be treated as "no
signal" until the narrow-scope query has actually run. (Root-cause miss on the acme 2026-06-21
incident: a broad `analyze-logs GROUP BY workload` returned 0 rows and was logged as a gap; the narrow
`body`-scoped query that would have found the 4 malformed-request log lines at the exact onset second
was never run. A service-owner's manual log search found it 5 days later.)

**Fast pre-check without reading body text** (useful when body content may be sensitive/large, or as a
first pass before a full text scan): aggregate `body_length` (max or P99) grouped by `workload` in the
onset slice. An outlier `body_length` on one workload — even with zero visible text — is enough to flag
`expensive_query_candidate` and justify a full `body` read on that workload specifically.

If the narrow-scope query and SPL both return no rows after retry, set trigger to **Unknown** with P0
ops action — do **not** fall back to `traffic_spike` solely because a `traffic_anomaly` change story
exists. Note in Gaps: *"Query text not in APM; narrow-scope KubeSense body query + SPL both returned no
rows — confirm access-log indexing for `<endpoint>`."*

**Duplicate-request-burst check:** in the same narrow-scope pull, check for **identical or near-identical
request bodies repeating within seconds** (same `body` hash / same truncated prefix, ≥2 occurrences within
a ≤5s window). A duplicate burst is independent corroborating evidence for `query_governance` even before
the query content itself is judged expensive — record as `signal_type: "duplicate_request_burst"` in
`evidence_links[]` with occurrence count and span.

### 5 — User / service-owner reconciliation

When the user or on-call provides **backend findings** (log lines, screenshots, query text, client
channel name):

1. **Reconcile** against steps 1–4 — update ranked hypotheses; do not ignore domain evidence.
2. If user evidence **contradicts** telemetry (e.g. "no volume spike" vs your traffic hypothesis),
   **revise** the RCA and document the contradiction in **Gaps** / contradicting evidence.
3. Record `source: "user_provided"` or `source: "kubesense-spl"` in `query_signals[]` or
   `evidence_links[]` with `signal_type: "service_owner_finding"`.
4. If SPL was **not run** but user provided log text, record **process gap** in Gaps: *"KubeSense SPL
   should have confirmed query text before service-owner input."*

**Cannot proceed to Phase 2** on ES saturation incidents until steps **1** and **3** complete (step **4**
attempted when KubeSense ✅ or Datadog logs expected for the caller).

---

## Phase 3 — Full query investigation (all query engines)

For OpenSearch/ES, Phase 3 **continues** after Phase 1 APM pass (logs, slowlog, cross-service). For
PostgreSQL/MySQL/Redis, start the pipeline here.

Applies when any of:

- Primary or strong alternate hypothesis is `infra_capacity` on a **query engine** (OpenSearch,
  Elasticsearch, PostgreSQL, MySQL, Redis, Cassandra, ClickHouse, etc.)
- Symptom mentions search failure, slow query, thread-pool rejections, DB saturation, or index
- Metrics show throughput collapse + CPU/queue saturation without a deploy in window

Output feeds **Executed queries investigated** in the report and optional `query_signals[]` in evidence
JSON.

---

## Investigation pipeline (in order)

Run every step that applies. Stop early only when a step returns a **ranked top query** that aligns with
the incident window.

### Step 1 — APM spans to the dependency

**OpenSearch/Elasticsearch:** Phase 1 already ran the required `aggregate_spans` pass — reuse those
results; only run additional client-scoped queries if the saturated cluster is reached via a different
APM service name.

For other engines or supplemental ES attribution:

```text
aggregate_spans:
  query: "service:<client> resource_name:*search* env:production"
  group_by: ["resource_name", "service"]
  computes: COUNT, P95(@duration)
  from/to: incident window
```

Variants by engine:

| Engine | Span filters |
|--------|----------------|
| OpenSearch / Elasticsearch | `resource_name:*search*` OR `@db.system:elasticsearch` OR peer tags naming the cluster |
| PostgreSQL / MySQL | `@db.system:postgres` / `@db.system:mysql` OR `resource_name:*query*` |
| Redis | `@db.system:redis` OR `resource_name:*redis*` |
| HTTP to search API | `resource_name:*_search` OR `@http.url_details.path:*/_search` |

**Tool:** `search_datadog_spans` — pull 3–5 **slowest** spans in window for query text in
`resource_name`, `http.url`, or `db.statement` tags:

```text
search_datadog_spans:
  query: "@duration:>5000000000 service:<client> @db.system:elasticsearch"
  sort: -@duration
  limit: 5
```

Map hits → `query_signals[]` with `query_text`, `client_service`, `p95_latency_ms`, `link` (trace URL).

### Step 2 — Datadog DBM (databases)

When the saturated dependency is a DB with **DBM** enabled:

1. `load_datadog_skill` — e.g. `datadog/dbm-postgresql`, `datadog/dbm-mysql`, `datadog/dbm-mongodb`
2. `get_datadog_metric` — top queries by `query_signature` / `dbm` metrics in the incident window (per
   skill's `metrics-query.md` reference)
3. Record `query_signature`, normalized query text if present, exec count, and latency

**Dashboard fast-path:** open
[Database Slow Query](https://app.datadoghq.com/dashboard/uwk-w92-5ys/database-slow-query) or
`search_datadog_dashboards` with title `database-slow-query`. Use for top slow queries, signatures,
and client attribution before or alongside DBM MCP calls (set window from RCA inputs).

If DBM is not enabled, note **"DBM not available"** under investigation attempts — do not skip silently.

### Step 3 — Log aggregation for query text

**Tool:** `analyze_datadog_logs` — GROUP BY message or extracted query field:

```json
{
  "sql_query": "SELECT message, count(*) AS n FROM logs WHERE service='<engine-service>' GROUP BY message ORDER BY n DESC LIMIT 15",
  "from": "<from>",
  "to": "<to>",
  "telemetry": {"intent": "top log lines mentioning slow queries or search rejections in incident window"}
}
```

OpenSearch / ES log filters (adapt to your index):

```text
analyze_datadog_logs filter: "source:opensearch @message:*slowlog*"
analyze_datadog_logs filter: "service:opensearch status:error"
```

Search for: `slowlog`, `took_millis`, `search_phase`, `query_shard`, `rejected_execution`,
`too_many_buckets`, `wildcard`, `scroll`, `aggregation`.

### Step 4 — Cross-service attribution

**Tool:** `search_datadog_service_dependencies` or `aggregate_spans` GROUP BY `service` on spans whose
`peer.service` / `resource_name` points at the saturated engine.

Identify which **client service** drove the spike — fills `client_service` in trigger analysis.

If Phase 1 **upstream mandate** already produced top-3 `@base_service` callers, reuse those results;
only run supplemental attribution when the saturated cluster is reached via a non-standard APM service name.

### Step 4b — Expensive-query branch (saturation without throughput spike)

**Trigger:** when **any** of CPU saturation, thread-pool rejections, or queue-full signals are present
**and** search/request throughput is **flat or <2× baseline** (no legitimate traffic spike), branch
into expensive-query investigation **before** defaulting to pure `infra_capacity`.

| Signal | Threshold |
|--------|-----------|
| CPU saturation | CPU ≥90% sustained ≥5 min in incident window |
| Thread pool rejected | `rejected_execution` or thread-pool reject metric >0 |
| Queue full | search/bulk queue depth at max or `queue_full` in logs |
| Throughput flat / no spike | request rate change **<2×** baseline OR flat/declining |
| Expensive query (when above hold) | exec_rate **<10/min** on top resource **and** p95 **>30s** |

When the branch fires:

1. Rank top `resource_name` / query patterns from APM + logs (wildcard, aggregation, scroll).
2. Score toward **`query_governance`** (alias: `expensive_query` in narrative only — canonical
   hypothesis id is `query_governance`).
3. Cross-check: no deploy on the **client** service in window (+2 toward query_governance).
4. If slowlog exists, capture `took_millis` / query body (+2).
5. Report **multi-cause** when `query_governance` ≥5 **and** saturation metrics strong — co-cause
   `infra_capacity` (shared cluster headroom exhausted **by** the query workload).

Do **not** list "CPU 99%" alone as root cause when this branch applies — name the workload layer in
**Immediate trigger** when APM/log evidence supports it; otherwise **Unknown** with documented attempts.

### Step 5 — Engine admin / slow logs (gap if unreachable)

Datadog MCP is **read-only** — it cannot call OpenSearch `_cat/tasks`, PostgreSQL `pg_stat_statements`,
or pull slow-log indices directly unless they are **ingested as logs or DBM**.

When steps 1–4 do not surface query text:

1. List in report **Investigation attempts** every step run and its result
2. Add **Gaps**: *"Engine slow logs / admin API not in Datadog — request ops pull slowlog for window
   05:30–06:30 UTC"*
3. P0 action: enable slow-log shipping or DBM query metrics

Do **not** mark trigger Unknown without documenting attempts.

---

## Classify query pattern

Once text or `resource_name` is found, tag the pattern:

| Pattern | Indicators |
|---------|------------|
| Wildcard | leading `*`, `wildcard`, `query_string` |
| Aggregation | `aggs`, `terms`, `cardinality`, `date_histogram` |
| Scroll / PIT | `scroll`, `point_in_time`, `search_after` |
| Nested / join | `nested`, `has_child`, `join` |
| Sort on unmapped field | heavy `sort` + high `took` |
| Regex | `regexp` query type |
| Full table scan | `seq_scan` / missing index in DBM |

---

## Evidence JSON — `query_signals[]`

Optional array (append to evidence bundle before Phase 4):

```json
{
  "query_text": "GET /index/_search ...",
  "query_signature": "dbm:abc123",
  "source": "aggregate_spans",
  "client_service": "metadata-api",
  "index_or_table": "users",
  "pattern": "wildcard",
  "exec_count": 1200,
  "p95_latency_ms": 4500,
  "detected_at": "2026-06-28T05:40:00Z",
  "link": "https://app.datadoghq.com/apm/traces?query=..."
}
```

Also append queries run to `query_references[]` and notable rows to `evidence_links[]`.

---

## Report section — Query execution profile (Phase 1 APM)

Required for **OpenSearch/Elasticsearch** incidents. Populated from Phase 1 `aggregate_spans` —
index/resource, caller, status without slow logs.

```markdown
## Query execution profile

APM client spans during incident window (`aggregate_spans`: `service:elasticsearch`, group by
`resource_name` + `@base_service`).

| Resource / index | Caller (@base_service) | HTTP status | Span count | p95 (ms) | Error count | Link |
|------------------|------------------------|-------------|------------|----------|-------------|------|
| GET /metadata/_search | metadata-api | 503 | 1200 | 4200 | 890 | … |
```

If empty, state: *"APM ES span pass returned no spans — check service name mapping or @db.system fallback."*

## Report section — Executed queries investigated

Required when this playbook was triggered. Structure:

```markdown
## Executed queries investigated

### Investigation attempts
- [x] APM `aggregate_spans` grouped by resource_name — top 3: …
- [x] Log aggregation for slowlog pattern — no slowlog index in Datadog
- [ ] DBM — not enabled on cluster
- [ ] Engine slow log pull — **not attempted** (ops action)

### Top queries / workloads (incident window)

| Rank | Query / resource | Client | Pattern | Count / p95 | Source | Link |
|------|------------------|--------|---------|-------------|--------|------|
| 1 | … | metadata-api | wildcard | … | APM spans | … |

### Trigger workload analysis

| Field | Value |
|-------|-------|
| Index / table | … or **Unknown** |
| Query pattern | … or **Unknown** |
| Client service(s) | … |
| Legitimate vs abusive | **Unknown** until query confirmed |
```

If a top query is identified with high confidence, update **Immediate trigger** from **Unknown** to a
specific description (still evidence-safe — cite the row above).

---

## Pressure-test self-check

Before Phase 4 on search/DB saturation:

- [ ] Ran at least **two** of: APM spans, log aggregation, DBM
- [ ] **Expensive-query onset signature** — CPU vs ES throughput at `from_time`; caller baseline <2×
- [ ] **Onset APM slice** (`from_time` −2m → +5m) — not full window only
- [ ] **Wildcard auto-flag** — `POST /?/_search` or equivalent investigated
- [ ] **Upstream mandate:** top-3 `@base_service` callers in first 10 min when ES/Redis/Kafka in blast radius
- [ ] **Query-string hunt** — Datadog logs and/or KubeSense MCP `body LIKE` on top caller, **narrow-scoped to single workload + onset slice** (a broad/GROUP-BY-workload aggregate query does not count, even if it returned rows); SPL if MCP fails
- [ ] **`body_length` outlier check** run as pre-check when full body scan is deferred
- [ ] **Duplicate-request-burst check** — identical/near-identical request body repeating within seconds
- [ ] **User/service-owner findings** reconciled when provided
- [ ] **Parallel caller log pivot** attempted (Datadog + KubeSense) when Datadog logs empty for top caller
- [ ] **AWS-integration scope check** (managed data stores, e.g. AWS OpenSearch/RDS): confirmed whether the AWS integration supplies **metrics only** (CloudWatch metrics, e.g. `aws.es.*`) vs. **logs** (CloudWatch Logs group forwarded) — do not assume metrics access implies log/slowlog access; state which was verified
- [ ] Investigation attempts listed even when all return empty
- [ ] `query_signals[]` or evidence table populated when queries found
- [ ] Trigger left Unknown only with documented attempts + P0 slow-log action
