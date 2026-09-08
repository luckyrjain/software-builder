# MCP Capability Matrix — k8s-overprovisioning-datadog

> **Discover and verify in DISCOVER_SOURCES** — tool names change across MCP upgrades; match
> capabilities, not server or tool names. The legacy skill name does not define source priority.

All Datadog calls require `telemetry.intent` (one-line English, no secrets).

## Routing contract

Inventory every connected source before querying. Record a source profile and provenance on every
observation. Fall back per capability; never switch the whole run merely because one capability is
missing.

| Capability | Preferred source | Fallback | No source behavior |
|------------|------------------|----------|--------------------|
| Running Deployment/StatefulSet, requests/limits, replicas, HPA/VPA/KEDA/PDB/ResourceQuota | Kubernetes MCP | Git provider manifest, then user-provided YAML/values | Mark live-state/manifest checks unverified; ask for values when required |
| Current pod status, restarts, OOM, CPU/memory usage when exposed | Kubernetes MCP | Datadog | Mark affected observations `missing` |
| Seven-day utilization, fleet p95/peak, throttling, Kafka lag | Kubernetes MCP only when it exposes equivalent history and aggregation | Datadog | Defer the affected dimension; never size from a point-in-time sample |
| Active incidents, monitors, APM/SLO, deployment/change history | Datadog | Kubernetes events only when equivalent | Mark optional signals missing; apply existing confidence and safety gates |
| Cloud cost | Datadog CCM | None | Skip cost output; report resource-only savings |

When both sources expose the same signal, retain both observations. Treat Kubernetes MCP as
**live-state truth** and Datadog as **historical truth**. Material disagreement emits
`STOP_REASON: conflicting_signals`; preserve both values and do not choose the more convenient one.

## Source adapters

### Kubernetes MCP — preferred for cluster truth

Discover semantically equivalent read-only capabilities such as workload/resource lookup, pod status,
events, metrics, and autoscaler/configuration reads. Do not require an exact server or tool name. Never
use a mutating capability (`apply`, `patch`, `delete`, `scale`, `rollout restart`).

Kubernetes MCP is history-capable only when it exposes an equivalent time window and aggregation for
the signal being sized (normally 7d fleet p95 for CPU and a 7d memory peak proxy). A current Metrics
API sample is live evidence, not historical sizing evidence.

### Datadog — capability fallback and historical/operational source

| Capability | Typical tool | K8s use |
|------------|--------------|---------|
| K8s CPU/memory metrics | `get_datadog_metric` | Utilization, throttle, fleet p95/peak |
| Metric discovery | `get_datadog_metric_context` / `search_datadog_metrics` | Resolve metric names; APM optional |
| Dashboards | `search_datadog_dashboards` / `get_widget` | Fast-path context |
| Monitors | `search_datadog_monitors` | Active alerts before downsizing |
| Incidents | `search_datadog_incidents` | Block cuts during open incidents |
| Change stories | `get_change_stories` | Redeploy and staleness detection |

Authentication and reachability failures are source-scoped. If Kubernetes MCP is absent,
unreachable, unauthorized, or lacks a capability, use Datadog for that capability. If Datadog fails,
continue with sufficient equivalent Kubernetes evidence. Retry a failing source at most twice; never
tight-loop on 429 responses.

### Cloud Cost Management (Datadog CCM)

`get_datadog_metric` with `use_cloud_cost: true` can provide observed monthly savings. CCM is optional;
without it, skip the cost appendix and report resource-only savings.

### Git provider MCP (GitLab / GitHub)

Use bounded manifest reads for requests/limits, HPA, VPA, KEDA, PDB, and ResourceQuota only when the
Kubernetes MCP cannot provide running configuration. If unavailable, ask the user to paste the values;
do not invent a path or YAML.

### KubeSense or other observability MCPs

Treat any source by capabilities it actually exposes. Metrics with equivalent history and aggregation
may satisfy a sizing signal; point-in-time or trace-only data may only cross-check it.

### Jira

Use optional ticket search for deploy-freeze checks. Its absence does not block the assessment.

## Degraded modes

| Mode | Behavior |
|------|----------|
| **Kubernetes MCP absent** | Continue with Datadog as the primary telemetry source for the run |
| **Kubernetes capability missing** | Fall back only that capability to Datadog |
| **Datadog absent; Kubernetes history sufficient** | Continue; mark Datadog-only operational/cost signals unavailable |
| **Datadog absent; Kubernetes live state only** | Report live observations; defer sizing dimensions that require history |
| **One source auth failure** | Record the failure and continue querying the other source |
| **Both sources insufficient** | Emit `STOP_REASON: insufficient_metrics`; blocked assessment, attempted sources and missing capabilities; no sizing recommendation |

## DISCOVER_SOURCES checklist

```text
1. Inventory Kubernetes and observability tools by capability.
2. Record live-state, current-metric, historical-metric, incident/monitor/APM/change, manifest, and cost coverage.
3. Select preferred + fallback independently for each capability.
4. Announce the source profile before queries.
5. Record source and query/tool provenance on every observation.
```

Example:

> **k8s source profile:** Kubernetes MCP ✅ live / ❌ history | Datadog ✅ history + monitors |
> GitLab ✅ manifest fallback | CCM ❌ | Jira ❌
