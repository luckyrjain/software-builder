# MCP Capability Matrix — k8s-overprovisioning-datadog

> **Re-verify at COLLECT** — tool names change across MCP upgrades; match **capabilities**, not exact strings.

All Datadog calls require `telemetry.intent` (one-line English, no secrets).

## Required

### Datadog (`plugin-datadog-datadog`)

| Capability | Tool | k8s use |
|------------|------|---------|
| K8s CPU/memory metrics | `get_datadog_metric` | Utilization, throttle, fleet p95 |
| Metric discovery | `get_datadog_metric_context` / `search_datadog_metrics` | Resolve metric names; APM optional |
| Dashboards | `search_datadog_dashboards` / `get_widget` | Fast-path context (title search) |
| Monitors | `search_datadog_monitors` | Active alerts before downsizing |
| Incidents | `search_datadog_incidents` | Block cuts during open incidents |
| Change stories | `get_change_stories` | Redeploy / staleness detection |

**Setup:** **ddsetup** if tools missing; **ddtoolsets** for Metrics, Dashboards, Monitors.

| Degraded mode | When | Behavior |
|---------------|------|----------|
| **Datadog auth failure** | 403 / missing tools | Run **ddconfig** / **ddsetup**; max 2 retries → `STOP_REASON: auth_failure` blocked report |
| **Partial metrics** | Single dimension missing | Register `OBS_*` as `missing`; defer cuts on that dimension; never invent utilization |
| **Rate limit (429)** | Quota exhausted | Narrow window; note gap; do not tight-loop retry |

## Optional

### Cloud Cost Management (Datadog CCM)

| Capability | Tool | k8s use |
|------------|------|---------|
| AWS cost by service | `get_datadog_metric` (`aws.cost.*`, `use_cloud_cost: true`) | $/mo savings in cost gate |

| Degraded mode | When | Behavior |
|---------------|------|----------|
| **CCM unavailable** | Cost toolset off or no `aws.cost.*` | Skip cost appendix; `cost_skipped` with gate reason; assessment continues on utilization |

### Git provider MCP (GitLab / GitHub)

| Capability | Tool | k8s use |
|------------|------|---------|
| Manifest read | `get_file_contents` | Requests/limits, HPA, VPA, KEDA ScaledObject, PDB, ResourceQuota |
| Tree browse | `get_repository_tree` | Bounded manifest discovery ([SETUP.md](../SETUP.md)) |

| Degraded mode | When | Behavior |
|---------------|------|----------|
| **No git MCP** | Server absent or lookup fails | Ask user to paste `resources.requests/limits` and replica counts; skip manifest drift automation; **Where to apply** uses user path only |
| **Tree too large** | >500 entries at searched path | Stop traversal; ask for Deployment/Helm path |

### KubeSense (`user-kubesense`)

| Capability | Tool | k8s use |
|------------|------|---------|
| Metrics / traces | `analyze-metrics`, `search-traces` | Cross-check when Datadog sparse |

| Degraded mode | When | Behavior |
|---------------|------|----------|
| **KubeSense only** | No Datadog | Not supported as primary — ask user to enable Datadog or paste metric snapshots |

### Jira (`user-Atlassian-MCP-Server`)

| Capability | Tool | k8s use |
|------------|------|---------|
| Deploy freeze | `searchJiraIssuesUsingJql` | Optional pre-render gate ([validate.md](../workflow/validate.md)) |

| Degraded mode | When | Behavior |
|---------------|------|----------|
| **Jira absent** | No ticket MCP | Assessment completes; Risks notes *deploy freeze not checked* |

## Not supported (v1)

| Server | Behavior |
|--------|----------|
| Grafana MCP | ❌ Use Datadog dashboards/metrics only |
| Prometheus MCP | ❌ Use Datadog `kubernetes.*` metrics; document gap if user insists |
| Direct cluster API | ❌ No `kubectl` — metrics via Datadog integration only |

## COLLECT detection checklist

```
1. Datadog metrics tools present?  → required; else ddsetup or stop
2. CCM / cost toolset?             → optional; note in MCP profile
3. GitLab or GitHub MCP?           → optional; paste fallback documented
4. Jira?                           → optional deploy-freeze check
5. Announce profile before queries.
```

Example announcement:

> **k8s MCP profile:** Datadog ✅ | CCM ❌ | GitLab ✅ | Jira ❌
