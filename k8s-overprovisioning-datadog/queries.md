# Datadog Fallback Queries Reference

Use these queries only for capabilities routed to Datadog by
[mcp-capabilities.md](reference/mcp-capabilities.md). Kubernetes MCP remains the preferred source for
live cluster state and equivalent metrics.

Replace `{scope}` with resolved tags, e.g. `kube_deployment:example-service,env:production`.

**Two scope tokens — do not reuse one across all metrics:**

| Token | Tags | Use for |
|-------|------|---------|
| `{deploy_scope}` | deployment/env, **no** `kube_container_name` | pod-/deployment-level + fleet `.dist` metrics: `kubernetes.pods.running`, `kubernetes_state.deployment.replicas_ready`, `kubernetes.pod.cpu.usage.dist`, `kubernetes.pod.cpu.usage.req_pct.dist` |
| `{app_scope}` | `{deploy_scope}` **plus** `,kube_container_name:<app>` | application-container metrics: `cpu.requests`, `cpu.usage.total`, `memory.*`, CFS throttle/period, OOM, restarts |

Filtering pod-/deployment-level or `.dist` metrics by `kube_container_name` returns **empty data** (the
tag is not present on those series) — that is why `{deploy_scope}` must omit it. Conversely, summing
`cpu.requests`/`memory.*` without `kube_container_name` is **pod-level (sidecar-inclusive)** and must
not be compared against app-container requests — that is why `{app_scope}` pins the container.
Example: `{deploy_scope}` = `kube_deployment:example-service,env:production`; `{app_scope}` =
`kube_deployment:example-service,env:production,kube_container_name:app`.

This file holds **query strings and scalar JSON only**. Verdict bands, cost formulas, and confidence
scoring live in [thresholds.md](thresholds.md). Load per intent via
[workflow/orchestrator.md](workflow/orchestrator.md) pre-flight — not necessarily the full file every run.

**Telemetry block (required on every Datadog MCP call):** `get_datadog_metric`, `get_widget`,
`search_datadog_dashboards`, and `get_datadog_metric_context` all require a `telemetry` object with a
one-line English `intent`. Never include secrets, tokens, or raw tag values in `intent`. Every scalar
JSON example below includes the block — keep it on real calls:

```json
"telemetry": {"intent": "assess CPU/memory rightsizing for a k8s deployment"}
```

## Core metrics

| Metric | Unit | Notes |
|--------|------|-------|
| `kubernetes.cpu.usage.total` | nanocores | Divide by 1e9 for cores; use for avg/max |
| `kubernetes.pod.cpu.usage.dist` | distribution | **Fleet p95/p99 for sizing** — query without `by {pod_name}` |
| `kubernetes.pod.cpu.usage.req_pct.dist` | distribution | Fleet CPU as **% of request** — sizing decisions |
| `kubernetes.cpu.requests` | cores | Per-container sum at pod level |
| `kubernetes.cpu.limits` | cores | |
| `kubernetes.memory.usage` | bytes | Working set style usage |
| `kubernetes.memory.requests` | bytes | |
| `kubernetes.memory.limits` | bytes | |
| `kubernetes.pods.running` | count | |
| `kubernetes.network.rx_bytes` | bytes/s | Optional I/O signal — consult when CPU avg < 20% on I/O-bound services |
| `kubernetes.network.tx_bytes` | bytes/s | Optional I/O signal — pairs with rx_bytes |
| `kubernetes_state.deployment.replicas_ready` | count | |
| `kubernetes_state.hpa.current_replicas` | count | Tag: `horizontalpodautoscaler` |
| `kubernetes_state.hpa.min_replicas` | count | |
| `kubernetes_state.hpa.max_replicas` | count | |
| `kubernetes_state.hpa.desired_replicas` | count | |
| `kubernetes.cpu.cfs.throttled.periods` | count | Cumulative throttled CFS periods |
| `kubernetes.cpu.cfs.periods` | count | Total CFS enforcement periods (denominator for throttle rate) |
| `kubernetes_state.container.restarts` | count | Cumulative per container; use `monotonic_diff` for events in window |
| `kubernetes_state.container.status_report.count.terminated` | count | Filter `reason:oomkilled` |

## Namespace / cluster ranking (scalar, 7d)

For cluster-wide or namespace waste asks. Use `"aggregator": "avg"` and a telemetry block; compute
waste % per namespace `(reserved − used) / reserved × 100` and rank top 5 by wasted CPU cores.

```text
sum:kubernetes.cpu.requests{env:production} by {kube_namespace}
sum:kubernetes.cpu.usage.total{env:production} by {kube_namespace}   # ÷ 1e9 for cores
sum:kubernetes.memory.requests{env:production} by {kube_namespace}    # ÷ 1 GiB
sum:kubernetes.memory.usage{env:production} by {kube_namespace}
```

Drill-down within a chosen namespace — rank deployments by wasted cores, then continue with Step 1
using `kube_deployment:<name>`:

```text
sum:kubernetes.cpu.requests{kube_namespace:<ns>,env:production} by {kube_deployment}
sum:kubernetes.cpu.usage.total{kube_namespace:<ns>,env:production} by {kube_deployment}   # ÷ 1e9 for cores
```

## Deployment totals (scalar, 7d)

Resolve the HPA name first (`get_datadog_metric_context` on `kubernetes_state.hpa.current_replicas`
filtered by `kube_deployment:<name>`) — the HPA tag value may differ from the deployment name.

> **Use the right scope token per metric.** Pod-/deployment-level and fleet `.dist` metrics use
> `{deploy_scope}` (**no** `kube_container_name`); application-container metrics use `{app_scope}`
> (`…,kube_container_name:<app>`). Filtering a pod/replica/`.dist` metric by `kube_container_name`
> returns **empty data**; summing an app metric without it is **pod-level (sidecar-inclusive)** and must
> not be compared against app-container requests. The `*_max_per_pod` rows already pin the app
> container (they are `{app_scope}`). HPA queries use the resolved `horizontalpodautoscaler` tag and
> the **same `env` as Step 1** (`<env>` — do not hardcode `production`).

```json
{
  "response_format": "scalar",
  "from": "now-7d",
  "to": "now",
  "telemetry": {"intent": "collect deployment totals (cpu/mem/replicas/hpa/throttle/oom) for rightsizing"},
  "queries": [
    {"name": "pods", "query": "sum:kubernetes.pods.running{deploy_scope}", "aggregator": "avg"},
    {"name": "cpu_req", "query": "sum:kubernetes.cpu.requests{app_scope}", "aggregator": "avg"},
    {"name": "cpu_use", "query": "sum:kubernetes.cpu.usage.total{app_scope}", "aggregator": "avg"},
    {"name": "cpu_use_max_per_pod", "query": "max:kubernetes.cpu.usage.total{app_scope} by {pod_name}", "aggregator": "max"},
    {"name": "cpu_use_p95", "query": "p95:kubernetes.pod.cpu.usage.dist{deploy_scope}", "aggregator": "max"},
    {"name": "cpu_req_pct_p95", "query": "p95:kubernetes.pod.cpu.usage.req_pct.dist{deploy_scope}", "aggregator": "max"},
    {"name": "mem_req", "query": "sum:kubernetes.memory.requests{app_scope}", "aggregator": "avg"},
    {"name": "mem_use", "query": "sum:kubernetes.memory.usage{app_scope}", "aggregator": "avg"},
    {"name": "mem_use_max_per_pod", "query": "max:kubernetes.memory.usage{app_scope} by {pod_name}", "aggregator": "max"},
    {"name": "replicas_ready", "query": "avg:kubernetes_state.deployment.replicas_ready{deploy_scope}", "aggregator": "avg"},
    {"name": "hpa_current", "query": "avg:kubernetes_state.hpa.current_replicas{horizontalpodautoscaler:<hpa>,env:<env>}", "aggregator": "avg"},
    {"name": "hpa_min", "query": "avg:kubernetes_state.hpa.min_replicas{horizontalpodautoscaler:<hpa>,env:<env>}", "aggregator": "avg"},
    {"name": "hpa_max", "query": "avg:kubernetes_state.hpa.max_replicas{horizontalpodautoscaler:<hpa>,env:<env>}", "aggregator": "avg"},
    {"name": "hpa_desired_max", "query": "avg:kubernetes_state.hpa.desired_replicas{horizontalpodautoscaler:<hpa>,env:<env>}", "aggregator": "max"},
    {"name": "cpu_throttled_rate", "query": "avg:non_zero_raw_rate(kubernetes.cpu.cfs.throttled.periods{app_scope})", "aggregator": "avg"},
    {"name": "cpu_period_rate", "query": "avg:non_zero_raw_rate(kubernetes.cpu.cfs.periods{app_scope})", "aggregator": "avg"},
    {"name": "oom", "query": "max:kubernetes_state.container.status_report.count.terminated{app_scope,reason:oomkilled}", "aggregator": "max"},
    {"name": "restarts_max_per_pod", "query": "sum:monotonic_diff(kubernetes_state.container.restarts{app_scope}) by {pod_name}", "aggregator": "max"}
  ]
}
```

`<env>` in the HPA rows must mirror the `env` in your `{scope}` from Step 1 (e.g. `env:production` or
`env:staging`) — it is not always `production`.

`mem_use_max_per_pod` is the **conservative memory peak proxy** (worst-pod app-container max — not a
true p95; see [thresholds.md](thresholds.md#memory-request-utilization)). If all `hpa_*` return null,
the deployment has no HPA (or KEDA — probe `keda.scaler.active`); use `replicas_ready` instead.

## Example scalar queries

**Default scope:** When sidecars are present, filter to app container:

```text
avg:kubernetes.cpu.usage.total{scope,kube_container_name:<app>} by {pod_name}
avg:kubernetes.cpu.requests{scope,kube_container_name:<app>} by {pod_name}
```

Per-pod average usage vs request (7d) — single-container pods:

```text
avg:kubernetes.cpu.usage.total{scope} by {pod_name}
avg:kubernetes.cpu.requests{scope} by {pod_name}
avg:kubernetes.memory.usage{scope} by {pod_name}
avg:kubernetes.memory.requests{scope} by {pod_name}
```

Multi-container pods — same metrics by `{pod_name,kube_container_name}` to isolate the app container from sidecars:

```text
avg:kubernetes.cpu.usage.total{scope} by {pod_name,kube_container_name}
avg:kubernetes.cpu.requests{scope} by {pod_name,kube_container_name}
avg:kubernetes.memory.usage{scope} by {pod_name,kube_container_name}
avg:kubernetes.memory.requests{scope} by {pod_name,kube_container_name}
```

Deployment totals:

```text
# Per-pod first, then multiply — do NOT use raw sum if it double-counts containers
avg:kubernetes.cpu.requests{scope} by {pod_name}     # × replicas for deployment total
avg:kubernetes.memory.requests{scope} by {pod_name}  # × replicas for deployment total
avg:kubernetes.memory.usage{scope} by {pod_name}     # × replicas for deployment usage total

# Cross-check only (should match per_pod × replicas within ~5%):
sum:kubernetes.cpu.requests{scope}
sum:kubernetes.memory.requests{scope}
sum:kubernetes.memory.usage{scope}
```

**Arithmetic validation:** `per_pod × replicas ≈ sum(...)`. Example: 576 MiB × 10 = 5.6 GiB — if sum shows 11.3 GiB, re-query with `by {pod_name}` or isolate `kube_container_name` (sidecar double-count).

Per-pod CPU — **two metrics, two purposes:**

| Purpose | Metric | Query |
|---------|--------|-------|
| **Sizing decisions** (p95/p99) | Fleet `.dist` | `p95:kubernetes.pod.cpu.usage.dist{scope}` — no `by {pod_name}` |
| **Burst / outlier checks** | App container max per pod | `max:kubernetes.cpu.usage.total{scope,kube_container_name:<app>} by {pod_name}` |

**Fleet percentiles for sizing** (7d):

```text
p95:kubernetes.pod.cpu.usage.dist{scope}              # cores — fleet distribution
p99:kubernetes.pod.cpu.usage.dist{scope}
p95:kubernetes.pod.cpu.usage.req_pct.dist{scope}        # % of request — fleet distribution
```

Use fleet p95/p99 for trim/right-size verdicts and `ceil(p95 × 1.5)` sizing. Do **not** use per-pod dist percentiles for sizing — the fleet aggregate is the decision signal.

**App container max per pod for burst/outlier** (7d):

```text
max:kubernetes.cpu.usage.total{scope,kube_container_name:<app>} by {pod_name}   # ÷ 1e9 for cores
```

Report the **worst pod** app-container max vs its request. If any pod max exceeds **150% of request**, treat as **bursty** for outlier analysis. Compare fleet p95 (sizing) separately from per-pod max (burst).

**Do not recommend enabling gauge percentiles** on `kubernetes.cpu.usage.total` unless your org has a confirmed UI toggle. Query fleet `.dist` first.

**Fallback** (only if dist metrics return no data):

```text
p95:kubernetes.cpu.usage.total{scope}    # fleet — ÷ 1e9 for cores; may need gauge percentile toggle
```

## Peak-window queries (Step 4a)

When the 7d CPU timeseries shows a cyclic pattern (daily peak, weekday-only load, nightly batch), re-run
the CPU avg/p95 over the **peak window only** — sizing on the weekly avg would under-provision the peak.

**Deriving the window:** open the 7d CPU timeseries (`get_widget`, CPU usage vs requests), read the
recurring high-load band off the chart (e.g. weekdays 09:00–13:00), and convert its start/end to **UNIX
epoch seconds**. Use those literal values for `from` / `to` (not `now-7d`) so the scalar covers only the
busy period. Repeat for one representative peak; widen if peaks vary.

```json
{
  "response_format": "scalar",
  "from": "<unix_peak_start>",
  "to": "<unix_peak_end>",
  "telemetry": {"intent": "re-measure CPU avg/p95 over the peak window for a cyclic k8s deployment"},
  "queries": [
    {"name": "cpu_use_peak_avg", "query": "avg:kubernetes.cpu.usage.total{app_scope}", "aggregator": "avg"},
    {"name": "cpu_req_pct_peak_p95", "query": "p95:kubernetes.pod.cpu.usage.req_pct.dist{deploy_scope}", "aggregator": "max"}
  ]
}
```

Per [thresholds.md](thresholds.md): peak-window avg > 60% of request while 7d avg < 30% → **Mixed /
cyclic** — size on the peak window. **Report both the 7d avg and the peak-window avg.**

## Active monitors / alerts (check before recommending downsizing)

Use `search_datadog_monitors` to find currently-firing alerts for the service — a firing
required-severity monitor blocks downsizing (see [thresholds.md](thresholds.md#active-monitors)).

When `search_datadog_incidents` is available, also query for **open/active** incidents affecting the
service or deployment in the analysis window — an active incident blocks **all** downsizing
(`STOP_REASON: active_incident`). Run this check in COLLECT pre-flight
([collect-metrics.md](workflow/collect-metrics.md#pre-flight-before-metric-queries)).

```text
service:<name> status:alert
# also try scope tags the org uses, e.g. kube_deployment:<name> status:alert
search_datadog_incidents: service=<name>, state=active  # when tool available
```

Pass a telemetry block, e.g. `{"intent": "check for firing monitors before recommending downsizing"}`.
Record monitor name, status, and severity/priority; ignore `status:no data` and warn-only monitors when
deciding whether downsizing is blocked.

## Network I/O (optional scaling signal)

Consult when CPU avg < 20% but the service type suggests I/O-bound work (log shippers, proxies, file
processors) — low CPU/memory then does **not** mean overprovisioned.

```text
sum:kubernetes.network.rx_bytes{scope}.as_rate()
sum:kubernetes.network.tx_bytes{scope}.as_rate()
```

High sustained network throughput with low CPU is a sign the workload is network-bound; do not size on
CPU/memory alone in that case.

## Kafka consumer lag

Discover metric via `get_datadog_metric_context` — names vary by integration:

```text
avg:kafka.consumer_lag{consumer_group:<group>,env:production}
max:kafka.consumer_lag{consumer_group:<group>,env:production}
avg:confluent.kafka.consumer.lag{consumer_group:<group>,env:production}
```

Tag with `consumer_group`, `topic`, or `env` as available.

**Enumerate all consumer groups** for the service — do not report lag for one topic only. Use `get_datadog_metric_context` on the lag metric to list `consumer_group` tag values, or query by known group names from the codebase/Helm config.

**Lag duration (required in report):** raw message count is not actionable without consume rate.

```text
estimated_lag_seconds = lag_messages / consume_msg_per_sec
```

Example: `571 messages ÷ 403 msg/s ≈ 1.4 s` vs `571 ÷ 2 msg/s ≈ 285 s` — very different risk.

Query consume rate per group (APM or Kafka integration):

```text
avg:kafka.consumer.messages_consumed.rate{consumer_group:<group>,env:production}
# or service-level: avg:trace.kafka.consume.hits{service:<name>,env:production}.as_rate()
```

Report a **coverage table** — one row per consumer group with lag avg/max, consume rate, estimated lag (s), and validated ✅/❌. Replica reduction blocked until all groups validated.

**Per-partition and assignment metrics** (when available):

```text
avg:kafka.consumer_lag{consumer_group:<group>,partition:*}
avg:kafka.consumer.messages_consumed.rate{consumer_group:<group>,partition:*}
```

Validate partition **assignment** via consumer group distribution — 30 partitions / 10 consumers does not imply 3 per pod. Skewed assignment (e.g. `20, 5, 3, 2, 0` partitions across consumers) explains low avg CPU with high peak on subset of pods.

## JVM GC (Java services)

```text
avg:jvm.gc.pause{service:<name>,env:production}
avg:jvm.gc.major_collection_count{service:<name>,env:production}.as_rate()
avg:jvm.heap_memory{service:<name>,env:production}
```

Correlate GC pause spikes with CPU p95/max to distinguish GC-driven bursts from traffic.

## SLO and customer impact

Tie optimization to business outcomes — query before recommending changes:

```text
p95:trace.servlet.request{service:<name>,env:production}           # latency — adapt framework tag
p99:trace.servlet.request{service:<name>,env:production}
sum:trace.servlet.request.errors{service:<name>,env:production}.as_rate()
sum:trace.servlet.request.hits{service:<name>,env:production}.as_rate()
```

For payment/domain SLAs, use service-specific trace or monitor metrics. Every proposed change must state impact on p99 latency, error rate, and domain SLOs.

## CPU throttle rate

Throttle rate is the fraction of CFS periods where the container hit its CPU quota:

```text
Throttle % = (rate(kubernetes.cpu.cfs.throttled.periods) / rate(kubernetes.cpu.cfs.periods)) × 100
```

In scalar queries, use `non_zero_raw_rate()` on both metrics over the window, then divide. Thresholds: [thresholds.md](thresholds.md).

Scalar example (7d) — compute throttle % as `(cpu_throttled_rate / cpu_period_rate) * 100` after querying:

```json
{
  "response_format": "scalar",
  "from": "now-7d",
  "to": "now",
  "telemetry": {"intent": "compute CPU CFS throttle rate for a k8s deployment"},
  "queries": [
    {"name": "cpu_throttled_rate", "query": "avg:non_zero_raw_rate(kubernetes.cpu.cfs.throttled.periods{scope})", "aggregator": "avg"},
    {"name": "cpu_period_rate", "query": "avg:non_zero_raw_rate(kubernetes.cpu.cfs.periods{scope})", "aggregator": "avg"}
  ]
}
```

## Container restarts (monotonic_diff)

`kubernetes_state.container.restarts` is a cumulative counter. Use `monotonic_diff` to count restart events in the window:

```text
sum:monotonic_diff(kubernetes_state.container.restarts{scope})
```

Scalar example (7d) — total restart events and worst pod:

```json
{
  "response_format": "scalar",
  "from": "now-7d",
  "to": "now",
  "telemetry": {"intent": "count container restart events per pod for a k8s deployment"},
  "queries": [
    {"name": "restarts", "query": "sum:monotonic_diff(kubernetes_state.container.restarts{scope})", "aggregator": "sum"},
    {"name": "restarts_max_per_pod", "query": "sum:monotonic_diff(kubernetes_state.container.restarts{scope}) by {pod_name}", "aggregator": "max"}
  ]
}
```

Per-pod breakdown: `sum:monotonic_diff(kubernetes_state.container.restarts{scope}) by {pod_name}`. Apply per-pod thresholds in [thresholds.md](thresholds.md) — a single rolling restart on one pod does not block downsizing.

## get_widget timeseries — sidecar scope warning

> ⚠️ **The `get_widget` examples below use pod-level `{scope}` (no `kube_container_name`) — they are
> sidecar-inclusive.** They are visual sanity checks of usage-vs-request-vs-limit shape, **not** the
> sizing source of truth. Do **not** read app-container utilization off these widgets when sidecars
> (Istio, Datadog Agent, Vault) are present — use the app-container-scoped scalar queries above. To
> make a widget app-only, add `,kube_container_name:<app>` to each `{scope}` token.

## get_widget — CPU usage vs requests (timeseries)

```json
{
  "type": "timeseries",
  "requests": [{
    "display_type": "line",
    "response_format": "timeseries",
    "queries": [
      {"data_source": "metrics", "name": "query0", "query": "avg:kubernetes.cpu.usage.total{scope}"},
      {"data_source": "metrics", "name": "query1", "query": "avg:kubernetes.cpu.requests{scope}"},
      {"data_source": "metrics", "name": "query2", "query": "avg:kubernetes.cpu.limits{scope}"}
    ],
    "formulas": [
      {"alias": "CPU Usage (cores)", "formula": "query0 / 1000000000"},
      {"alias": "CPU Requests (cores)", "formula": "query1"},
      {"alias": "CPU Limits (cores)", "formula": "query2"}
    ]
  }]
}
```

## get_widget — Memory usage vs requests (timeseries)

```json
{
  "type": "timeseries",
  "requests": [{
    "display_type": "line",
    "response_format": "timeseries",
    "queries": [
      {"data_source": "metrics", "name": "query0", "query": "avg:kubernetes.memory.usage{scope}"},
      {"data_source": "metrics", "name": "query1", "query": "avg:kubernetes.memory.requests{scope}"},
      {"data_source": "metrics", "name": "query2", "query": "avg:kubernetes.memory.limits{scope}"}
    ],
    "formulas": [
      {"alias": "Memory Usage (GiB)", "formula": "query0 / 1073741824"},
      {"alias": "Memory Requests (GiB)", "formula": "query1 / 1073741824"},
      {"alias": "Memory Limits (GiB)", "formula": "query2 / 1073741824"}
    ]
  }]
}
```

## get_widget — CPU % of request (timeseries)

```json
{
  "type": "timeseries",
  "requests": [{
    "display_type": "line",
    "response_format": "timeseries",
    "queries": [
      {"data_source": "metrics", "name": "query0", "query": "avg:kubernetes.cpu.usage.total{scope}"},
      {"data_source": "metrics", "name": "query1", "query": "avg:kubernetes.cpu.requests{scope}"}
    ],
    "formulas": [
      {"alias": "CPU % of Request", "formula": "query0 / query1 / 10000000"}
    ]
  }]
}
```

Note: `query0` is nanocores and `query1` is cores. Percent = `(query0 / 1e9) / query1 × 100`, so the divisor is `1e7` (10,000,000).

## get_widget — CPU throttle rate (timeseries)

```json
{
  "type": "timeseries",
  "requests": [{
    "display_type": "line",
    "response_format": "timeseries",
    "queries": [
      {"data_source": "metrics", "name": "query0", "query": "avg:non_zero_raw_rate(kubernetes.cpu.cfs.throttled.periods{scope})"},
      {"data_source": "metrics", "name": "query1", "query": "avg:non_zero_raw_rate(kubernetes.cpu.cfs.periods{scope})"}
    ],
    "formulas": [
      {"alias": "CPU Throttle %", "formula": "query0 / query1 * 100"}
    ]
  }]
}
```

## get_widget — Pod count + HPA

```json
{
  "type": "timeseries",
  "requests": [{
    "display_type": "bars",
    "response_format": "timeseries",
    "queries": [
      {"data_source": "metrics", "name": "query0", "query": "sum:kubernetes.pods.running{scope}"}
    ],
    "formulas": [
      {"alias": "Pods running", "formula": "query0"}
    ]
  }, {
    "display_type": "line",
    "response_format": "timeseries",
    "queries": [
      {"data_source": "metrics", "name": "query1", "query": "avg:kubernetes_state.hpa.current_replicas{horizontalpodautoscaler:<name>,env:<env>}"},
      {"data_source": "metrics", "name": "query2", "query": "avg:kubernetes_state.hpa.desired_replicas{horizontalpodautoscaler:<name>,env:<env>}"}
    ],
    "formulas": [
      {"alias": "HPA current", "formula": "query1"},
      {"alias": "HPA desired", "formula": "query2"}
    ]
  }]
}
```

## Dashboard search patterns

```text
title:<service-name>
title:UHD - <service-name>
widgets.metrics:kubernetes.cpu.usage.total <service-name>
example-service
team:<team-name>
```

## Service SLI dashboard template variables

Dashboard `tyu-gyn-za6`:

- `$service` — APM service name
- `$horizontalpodautoscaler` — HPA name (often matches deployment)
- `$kube_cluster_name` — e.g. your production EKS cluster name

## Cost metrics

Requires Datadog Cloud Cost Management with container cost allocation enabled. If queries return no data, report savings in cores/GiB only (see [thresholds.md](thresholds.md)).

| Metric | Unit | Notes |
|--------|------|-------|
| `aws.cost.amortized.shared.resources.allocated` | $ | Total allocated EC2+EBS cost per pod/deployment |
| `aws.cost.amortized.cpu.allocated` | $ | CPU portion of allocated cost |
| `aws.cost.amortized.mem.allocated` | $ | Memory portion of allocated cost |
| `aws.cost.net.amortized.shared.resources.allocated` | $ | Net amortized (preferred if available) |

Tags: `kube_deployment`, `kube_cluster_name`, `kube_namespace`, `service`, `env`.

### Current monthly cost (scalar, 30d)

Use 30d for a stable monthly estimate (7d is too noisy for $). **Every `aws.cost.*` query via
`get_datadog_metric` must set `use_cloud_cost: true`** and use `"aggregator": "sum"` with
`"from": "now-30d"`. Do not use `.rollup()` in the query string (rollup applies to timeseries, not
scalar). CCM cost is already monthly $.

```text
sum:aws.cost.amortized.shared.resources.allocated{scope}
sum:aws.cost.amortized.cpu.allocated{scope}
sum:aws.cost.amortized.mem.allocated{scope}
```

Example scalar JSON (note `use_cloud_cost` and the telemetry block):

```json
{
  "response_format": "scalar",
  "from": "now-30d",
  "to": "now",
  "use_cloud_cost": true,
  "telemetry": {"intent": "pull monthly CCM cost allocated to a k8s deployment"},
  "queries": [
    {"name": "cost_total", "query": "sum:aws.cost.amortized.shared.resources.allocated{scope}", "aggregator": "sum"},
    {"name": "cost_cpu", "query": "sum:aws.cost.amortized.cpu.allocated{scope}", "aggregator": "sum"},
    {"name": "cost_mem", "query": "sum:aws.cost.amortized.mem.allocated{scope}", "aggregator": "sum"}
  ]
}
```

To derive `$/core/mo` and `$/GiB/mo`, run the cost queries above (with `use_cloud_cost: true`, 30d)
alongside `sum:kubernetes.cpu.requests{scope}` / `sum:kubernetes.memory.requests{scope}`
(`aggregator: avg`, 30d) — **then apply the derivation formula in
[cost-estimation.md](cost-estimation.md#calibrating-core-and-gib).** Do not re-derive it here.

**CCM returns no data** → label savings **resource-only**; do not apply fallback $ rates without user
confirmation. **CCM without container allocation** (`aws.cost.amortized` exists but `.cpu.allocated` /
`.mem.allocated` do not) → container allocation is disabled; cluster-level
`aws.cost.amortized{kube_cluster_name:...}` is context only. `aws.cost.*` is AWS-specific — for
GCP/Azure ask the user for their CCM metric paths.

Apply derived/fallback rates to `freed_cpu_cores` and `freed_giB` per [thresholds.md](thresholds.md).

### Kubernetes Cost by Service dashboard

Search `search_datadog_dashboards` with exact title `Kubernetes Cost by Service` (fast-path ID `rmx-fwy-naj`
only when search confirms the title). Use `get_widget` to pull service-level cost vs requests charts for
sanity check against computed savings.

## Node packing (cost savings sanity check)

Reserved capacity reduction does not save money if pods still occupy the same number of nodes. Query
the inputs here; the `nodes_needed` formula and worked example live in
[cost-estimation.md](cost-estimation.md#node-packing).

```text
# Deployment total CPU requests (cores)
sum:kubernetes.cpu.requests{scope}

# Node allocatable CPU (typical node size — verify metric in your org)
avg:kubernetes_state.node.cpu_allocatable{kube_cluster_name:<cluster>}

# Cluster Autoscaler scale-down activity (is CA already removing nodes?)
sum:cluster_autoscaler.scaled_down_nodes_total{kube_cluster_name:<cluster>}
```

If `cluster_autoscaler.scaled_down_nodes_total` shows CA is already aggressively removing nodes, the
"likely no immediate node reduction" caveat may be too pessimistic — freed capacity could translate to
real node removal sooner. Note CA activity when framing $ savings.

If `kubernetes_state.node.cpu_allocatable` returns no data, discover the metric/cluster tag via
`get_datadog_metric_context` — always use `kube_cluster_name` (not `cluster_name`). Also check
cluster-level utilization vs Cluster Autoscaler scale-down thresholds when claiming $ impact.

## VPA recommendations (manifest / git MCP)

Read from the workload's VerticalPodAutoscaler resource when available (not a Datadog metric):

```yaml
# Record from status.recommendation.containerRecommendations[] for the app container:
target:     { cpu: "500m", memory: "1Gi" }
lowerBound: { cpu: "250m", memory: "512Mi" }
upperBound: { cpu: "1",   memory: "2Gi" }
```

Compare VPA **target** to running `resources.requests` and to fleet p95 sizing. Use as positive signal
in REASON when VPA target aligns with a proposed trim; block cuts when VPA target exceeds current requests.
See [collect-metrics.md](workflow/collect-metrics.md#vpa-recommendations-positive-signal).
