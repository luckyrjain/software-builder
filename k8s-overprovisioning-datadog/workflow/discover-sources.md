---
workflow_version: 3.4
phase: collect-source-discovery
produces:
  - source_profile
consumes:
  - user_intent
---

# Discover evidence sources

Run this read-only discovery step before service resolution or any data query. Inventory connected
tools by capability rather than exact server/tool names.

Build `source_profile` with this shape:

```yaml
sources:
  kubernetes_mcp:
    status: connected | absent | unreachable | unauthorized
    capabilities: [live_state, current_metrics, historical_metrics, events]
    failures: []
  datadog:
    status: connected | absent | unreachable | unauthorized
    capabilities: [current_metrics, historical_metrics, incidents_monitors, apm_slo, change_history, cost]
    failures: []
routes:
  live_state: kubernetes_mcp | unavailable
  current_metrics: kubernetes_mcp | datadog | unavailable
  historical_metrics: kubernetes_mcp | datadog | unavailable
  incidents_monitors: datadog | kubernetes_mcp | unavailable
  manifest_config: kubernetes_mcp | git | user_provided | unavailable
  cost: datadog | unavailable
```

Select each route independently using [mcp-capabilities.md](../reference/mcp-capabilities.md). A
capability probe may call only harmless discovery/list/schema operations; do not query workload data
until the profile exists. Record failed probes in `sources.<name>.failures` and continue discovering
the other source.

`live_state` means Kubernetes API state (running workload configuration and status), so Datadog is
never a valid route for it. When Kubernetes MCP is unavailable, route `live_state` to `unavailable`
and route Datadog independently for `current_metrics` and `historical_metrics`. Use
`manifest_config` for Git- or user-provided desired configuration.

Pass `source_profile` unchanged to RESOLVE, COLLECT, NORMALIZE, and BUILD_GRAPH. Announce the selected
routes before workload queries.
