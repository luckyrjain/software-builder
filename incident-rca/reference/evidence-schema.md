# Evidence JSON schema

Write this before calling the correlator CLI (Phase 4). Full example: [evidence.example.json](evidence.example.json). OpenSearch / `query_governance`:
[evidence.example.opensearch-query-governance.json](evidence.example.opensearch-query-governance.json).

Numeric thresholds and confidence cutoffs: [thresholds.md](thresholds.md). Validate bundles with
`python3 incident-rca/scripts/validate_evidence_json.py <path>`.

> **Schema versioning:** `schema_version` in the evidence JSON (currently **4**) tracks correlator input
> shape — independent of **`skill_version`** in `SKILL.md` frontmatter (skill doc releases). Increment
> evidence `schema_version` when adding hypothesis types or signal fields. Check SETUP.md for CLI schema
> compatibility before using a newer schema with an older CLI binary.

```json
{
  "schema_version": 4,
  "window": { "from_time": "2026-06-28T14:00:00Z", "to_time": "2026-06-28T16:00:00Z" },
  "service": "neo-disbursement-service",
  "symptom": "5xx spike on transfer-money",
  "environment": "production",
  "error_signals": [],
  "deploy_events": [],
  "jira_issues": [],
  "infra_signals": [],
  "known_issue_matches": [],
  "evidence_links": [],
  "query_references": [],
  "recurrence_history": [],
  "query_signals": []
}
```

Optional top-level field when KubeSense field discovery matches a known org profile:

| Field | When to set |
|-------|-------------|
| `kubesense_schema_profile` | `"acme"` when MCP discovery shows `workload` and no `service` / `message` |
| `logs_primary` | `"kubesense"` when org does not ingest Datadog logs (acme default) |

When set, use MCP `search-logs` with `body` per **`kubesense-logs`** skill ([dependencies.md](../dependencies.md)).
Map MCP output to `error_signals[]` with `source: "kubesense-mcp"`. **Run SPL CLI** per
[kubesense-spl.md](kubesense-spl.md) only when MCP body fails. Map SPL output with
`source: "kubesense-spl"`.

When both MCP body and SPL are unavailable or return no rows, record counts-only findings in `evidence_links[]`:

```json
{
  "signal_type": "kubesense_metadata_only",
  "source": "kubesense",
  "finding": "ERROR count 1,240 on workload user-metadata-service — no message body in schema",
  "workload": "user-metadata-service"
}
```

## `query_signals[]` (optional — query investigation)

Populated in **Phase 1** for OpenSearch/Elasticsearch (`aggregate_spans` APM pass) and in **Phase 3**
when [query-investigation.md](query-investigation.md) runs for other engines or ES follow-up. Each entry:

**Required:** `query_text`, `source`, `detected_at` (non-empty strings). **Optional:** remaining fields below.

| Field | Description |
|-------|-------------|
| `query_text` | **Required.** Normalized query, resource_name, or slow-log line |
| `query_signature` | DBM signature when available |
| `source` | **Required.** `aggregate_spans`, `search_datadog_spans`, `analyze_datadog_logs`, `dbm` |
| `client_service` | Upstream APM service |
| `index_or_table` | Index / table name when known |
| `pattern` | `wildcard`, `aggregation`, `scroll`, etc. |
| `exec_count` | Count in window (number or string) |
| `p95_latency_ms` | Optional |
| `detected_at` | **Required.** ISO-8601 |
| `link` | Datadog deep link |

```json
{
  "query_text": "GET /users/_search",
  "source": "aggregate_spans",
  "client_service": "metadata-api",
  "pattern": "wildcard",
  "detected_at": "2026-06-28T05:40:00Z",
  "link": "https://app.datadoghq.com/apm/traces?query=..."
}
```

## Field mapping (MCP → JSON)

| JSON field | Source | MCP origin |
|------------|--------|------------|
| `error_signals[].detected_at` | First spike timestamp | Datadog metric anomaly / `analyze_datadog_logs` |
| `error_signals[].magnitude` | Rate vs baseline | Datadog metric / log count |
| `error_signals[].sample_messages` | Top error messages | Datadog `search_datadog_logs` / KubeSense MCP `search-logs` with `body` / SPL CLI `--evidence` fallback |
| `error_signals[].link` | Deep link | Datadog APM/logs URL |
| `deploy_events[].deployed_at` | Deploy/change time | `get_change_stories` / Jenkins build timestamp |
| `deploy_events[].sha` | Commit SHA | Jenkins `getBuildScm` / GitLab `get_commit` |
| `deploy_events[].author` | Deploy author | `getBuildChangeSets` / `get_commit` |
| `deploy_events[].change_summary` | Change description | `getBuildChangeSets` / MR title / `get_commit_diff` |
| `deploy_events[].mr_url` / `mr_iid` | MR link | GitLab MR matched by SHA |
| `deploy_events[].services` | Affected service(s) | Change story / mapping |
| `deploy_events[].link` | Deploy deep link | Change story / Jenkins build URL |
| `jira_issues[].key` / `summary` / `status` / `priority` / `created_at` / `link` | Ticket fields | `searchJiraIssuesUsingJql` / `getJiraIssue` |
| `jira_issues[].comment_snippets` | Relevant comments | `getJiraIssue` |
| `infra_signals[].signal_type` | `oom`, `pod_restart`, `hpa_max`, `crashloopbackoff`, etc. | Datadog K8s metrics / `get_change_stories` / KubeSense |
| `infra_signals[].signal_type: "kafka_lag_spike"` | Consumer group lag > 10× normal, rebalance events | KubeSense `analyze-metrics` / Datadog `kafka.consumer_lag` metrics |
| `deploy_events[].event_type: "feature_flag"` | Feature flag toggle event from `get_change_stories` | Datadog `get_change_stories` (`feature_flag` event type) |
| `deploy_events[].event_type: "configuration_change"` | ConfigMap/Secret/env mutation from `get_change_stories` or infra audit | Datadog `get_change_stories` (`configuration` / env-change types) |
| `known_issue_matches[]` | Matched documented issue | user-provided KNOWN_ISSUES |
| `evidence_links[]` | Notable finding + URL | All sources |
| `query_references[]` | Query strings used (appendix) | All sources |
| `recurrence_history[].key` / `summary` / `created_at` | Similar past incident ticket | Phase 3 recurrence JQL results |
| `evidence_links[].signal_type: "log_coverage_gap"` | Datadog returned 0 log rows for service S | Phase 1 fallback — **not** acme (use `logs_source_profile`) |
| `evidence_links[].signal_type: "logs_source_profile"` | Org uses KubeSense as primary log store; Datadog logs N/A | acme / `logs_primary: kubesense` |
| `evidence_links[].signal_type: "mcp_process_failure"` | KubeSense connected but agent skipped mandatory attempt | Phase 1 gate violation |
| `evidence_links[].signal_type: "observability_backend_error"` | KubeSense called; backend returned fetch error **after retry** | Distinct from skip — backend/MCP failure |
| `evidence_links[].signal_type: "kubesense_metadata_only"` | KubeSense returned counts/metadata only — no log message body | acme / metadata-only profiles |
| `evidence_links[].signal_type: "expensive_query_candidate"` | Wildcard / cross-index APM resource at onset | Phase 1 wildcard auto-flag |
| `evidence_links[].signal_type: "expensive_query_signature"` | CPU↑ while ES throughput flat/declining at onset | Phase 1 onset metric pair |
| `evidence_links[].signal_type: "service_owner_finding"` | Backend/on-call log or query text from user | User reconciliation step |

## `query_governance` — investigation steps

When primary or strong alternate is `query_governance` (or expensive-query branch triggered):

1. Phase 1 APM pass + **expensive-query onset signature** (CPU vs throughput, onset slice, caller baseline).
2. Wildcard auto-flag (`POST /?/_search` etc.) + query-string hunt (Datadog logs + KubeSense SPL).
3. Upstream mandate (top-3 `@base_service` in first 10 min).
4. Expensive-query branch evaluation (saturation + flat/<2× throughput).
5. Parallel caller log pivot when Datadog empty for top caller.
6. Slowlog / DBM when available; ops pull when not ingested.
7. **User/service-owner reconciliation** when backend findings provided.
8. Often **multi-cause** with `infra_capacity` when cluster headroom exhausted by the query workload.

## Process failure guardrails

When **immediate trigger** remains **Unknown** after query investigation **and** KubeSense was
**skipped** while profile showed ✅:

- Cap confidence at **MEDIUM** (never HIGH).
- Always flag in **Gaps**: *"KubeSense mandatory log fallback skipped — process failure."*
- Record `mcp_process_failure` in `evidence_links[]`.

When KubeSense **was attempted** but returned "unable to fetch logs" or equivalent:

- **Retry once** with a narrower time window (≤1h slice) before recording failure.
- Record `observability_backend_error` — **not** `mcp_process_failure`.
- Note backend error in Gaps; confidence cap follows single-source rules if KubeSense was the only log source.

**Metadata-only KubeSense (acme):** error counts by `workload` are valid signals; empty
`sample_messages` is expected — do not downgrade to "no logs". Note text attribution gap in Gaps.

## Hypothesis types (correlator output)

| Type | When it wins |
|------|--------------|
| `deploy_regression` | Deploy/change 0–60 min before error spike on the **same service**, diff touches the failing path |
| `configuration_change` | Config mutation or env diff 0–30 min before spike on the **same service**, no code deploy in window |
| `infra_capacity` | OOM / restarts / HPA-max / crashloop without a deploy |
| `query_governance` | Expensive or abusive query workload under saturation without client deploy; canonical id — narrative alias `expensive_query` |
| `dependency_failure` | Downstream / cascade errors in messages |
| `known_issue_match` | Symptom matches a documented known issue |
| `external_third_party` | Bank / payment-rail / third-party HTTP errors, no deploy — **external services only**; internal Kafka infrastructure → `kafka_lag_spike` |
| `feature_flag_regression` | Feature flag change (`feature_flag` event from `get_change_stories`) 0–30 min before error spike on the **same service** |
| `kafka_lag_spike` | Consumer group lag spike in window with no deploy or external event; service is a Kafka consumer |
| `slo_breach` | SLO error budget exhausted in window with no accompanying error rate spike or deploy event — SLO breach is the primary observable; use when `error_signals` contains `signal_type: "slo_breach"` but no other signal type reaches HIGH magnitude |
| `inconclusive` | Insufficient overlapping evidence |

## `dependency_failure` — cascade investigation steps

When `dependency_failure` is a top-scoring hypothesis, trace the cascade before writing the final report:

1. **Identify the error path** — scan `error_signals[].sample_messages` for upstream service names, gRPC status codes, circuit breaker messages, or timeout patterns that point to a downstream call.
2. **Pivot to the downstream service** — re-run Phase 1 queries (`analyze_datadog_logs` or `analyze-logs`) scoped to `service:<downstream>` in the same window. If the downstream also has error spikes, it is a cascade candidate.
3. **Iterate until the chain terminates** — repeat step 2 on each new downstream until either:
   - A service has errors but its downstream does not → **root service found**
   - The chain exceeds **3 hops** → note *"Deep cascade — recommend distributed tracing for full chain"* and stop manual pivoting.
4. **Use traces when available (preferred)** — `search_datadog_spans` or `analyze-traces` scoped to the upstream service can reveal the actual call chain directly, without manual pivoting.
5. **Report the chain** — list hops in order: `A → B → C (root)`. State primary hypothesis `dependency_failure`; identify root service as `C`. Note each hop's error rate and approximate timing.

**Confidence cap:** if the root service (C) is outside your Datadog/KubeSense scope (third-party, different org), cap confidence at **MEDIUM**.

**`slo_breach` confidence cap:** use `search_datadog_slos` to confirm breach duration and error-budget consumed. Without a corroborating error-rate spike (`magnitude > 10×` baseline), cap `slo_breach` confidence at **MEDIUM** — an SLO breach alone does not identify root cause.

## `dependency_chain` (optional, multi-hop)

When step 5 reports A→B→C hops, also set top-level `dependency_chain` in the evidence bundle:

```json
"dependency_chain": ["caller-service", "middleware", "downstream-db"]
```

Order is caller → root. Each hop should have corroborating `error_signals`, `query_signals`, or
`evidence_links`. Omit when single-service scope.

## Correlation vs causation guardrails

- **Minimum evidence gate:** if `error_signals` **and** `infra_signals` are both empty after Phases
  1–3, **do not** run hypothesis ranking. Emit a blocked/partial report with primary hypothesis
  `inconclusive` / confidence **UNKNOWN** and the explicit message *"No observability data found for
  this window."* Deploy events or Jira tickets alone do not satisfy this gate.
- **Signal timing (mandatory for HIGH/MEDIUM):** every signal counted toward confidence must have
  `detected_at` (or equivalent timestamp) **within** `[window.from_time, window.to_time]`. A signal
  55 minutes after the window ends does **not** qualify — cap confidence at **LOW** and note the
  out-of-window signal in Gaps.
- **HIGH** confidence requires **≥2 independent signal types** that agree (e.g. a deploy change story
  **and** an error spike on the same service within minutes) — and you must state the
  counter-evidence / alternates you considered.
- If **only one observability source responded** (Datadog, KubeSense, Prometheus, Loki — GitLab/Jenkins/Jira
  don't count), cap confidence at **MEDIUM** regardless of how clean the signal looks.
- Always name at least one **alternate hypothesis** and why it scored lower.
- "Deploy just before the spike" is suggestive, not proof — confirm the deploy actually touched the
  failing path (`get_commit_diff` / `getBuildChangeSets`) before calling it the cause.

### Common mistakes (rationalizations → reality)

| Rationalization | Reality |
|-----------------|---------|
| "A deploy happened near the spike, so it's the cause." | Timing ≠ causation. Need the diff to touch the failing path **and** a confirmed error overlap. |
| "Only Datadog responded but the signal is obvious — call it HIGH." | One source = **MEDIUM** cap. State the gap. |
| "No deploy found, so it must be infra." | Absence of a deploy event is not evidence of infra cause — `get_change_stories` may be incomplete; say so. |
| "The CLI isn't installed but I'll present ranked hypotheses anyway." | Without the CLI, label ranking **manual** and add a Gaps note. |
| "Ticket says X, so X is the root cause." | Tickets capture human hypotheses, not verified causes — corroborate with telemetry. |
| "Datadog logs empty — skip KubeSense, Datadog is enough." | On acme, Datadog logs are **N/A** — KubeSense MCP body (+ SPL fallback) mandatory for log text. |
| "Datadog logs empty — log coverage gap." | On acme, **wrong** — record `logs_source_profile`, run KubeSense MCP; 0 Datadog rows is expected. |
| "KubeSense failed — same as skipped." | Backend fetch error → `observability_backend_error`; skip while ✅ → `mcp_process_failure`. |
| "`traffic_anomaly` change story at onset — must be the trigger." | Change stories are **correlated** events — require caller request rate ≥2× baseline **and** ES throughput ≥2× before `traffic_spike` primary; else run expensive-query onset signature. |
| "Top ES caller has most spans in the full window — traffic spike." | Full-window counts include **retry storms** after saturation; use onset slice (`from_time` ±5m) and caller baseline. |
| "CPU 99% on search cluster — undersized / need bigger nodes." | Capacity symptom ≠ root cause — run query investigation; CPU↑ + requests↓ implies `query_governance`. |
| "Backend team says no volume spike — ignore, telemetry shows BFF anomaly." | **Reconcile** service-owner findings; revise hypotheses; record `service_owner_finding`. |

**`external_third_party` verification:** MCP cannot access third-party status pages. For this hypothesis to reach MEDIUM or higher confidence, the user must manually verify the relevant external status pages (AWS Status, Confluent Cloud, Stripe/Razorpay/Juspay, etc.) and report the outcome. Record the verification result in `evidence_links[]`. Without this confirmation, `external_third_party` confidence is capped at **LOW**.

**Multi-cause incidents:** when the top-2 hypotheses are within 20% raw score of each other after penalties (e.g. both `deploy_regression` and `infra_capacity` score highly), report both as co-contributors rather than picking one primary:

**Independent causal chains may both rank HIGH** when each has ≥2 independent signal types. Do **not**
force a single root cause. Customer-visible symptoms (5xx, timeout) belong at the bottom of the **Causal
graph**, not as competing hypotheses.

```json
"causality": "multi-cause",
"primary": "<higher-scoring hypothesis>",
"co-cause": "<within-20% hypothesis>"
```

State: *"Evidence supports multiple contributing causes — do not optimize for one while ignoring the other."*

**Hypothesis deduplication:** merge steps of one causal chain (slow query → saturation → errors) into a
single causal graph — do not rank chain steps as separate competing hypotheses. See
[evidence-quality.md](evidence-quality.md) §Hypothesis deduplication.
