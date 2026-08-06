---
workflow_version: 3.4
phase: resolve
produces:
  - service_identity
  - namespace_ranking
consumes:
  - user_intent
  - source_profile
---

# Resolve service identity

Use the routes already selected in `source_profile`; discovery must have completed before this file is
loaded. Resolve through Kubernetes MCP first when it can list/read workloads in the named cluster/namespace.
Match Deployment, StatefulSet, or DaemonSet by exact name; ask before fuzzy matches. Record UID,
namespace, workload kind, container names, and autoscaler names from live state.

For capabilities routed to Datadog, map the resolved workload to tags (try in order):

| Tag | Example | Use when |
|-----|---------|----------|
| `kube_deployment` | `example-service` | Deployment-level K8s metrics (preferred) |
| `kube_statefulset` | `redis-cluster` | StatefulSet workloads |
| `kube_daemonset` | `fluentd` | DaemonSet (scales with nodes) |
| `service` | `example-service` | APM / Service SLI |
| `horizontalpodautoscaler` | `example-service` | HPA replica metrics |

Cross-check with `get_datadog_metric_context` on `kubernetes.cpu.requests` (`tag_filter:
kube_deployment`) when Datadog is available. If live and historical identities disagree, emit
`conflicting_signals`; do not silently remap. If ambiguous, ask the user or default `env:production`
when present.

**HPA name:** read the live HPA target through Kubernetes MCP first. Fall back to
`get_datadog_metric_context` on `kubernetes_state.hpa.current_replicas` filtered by
`kube_deployment:<name>`. Never assume the HPA name equals the deployment name.

**Workload notes:** StatefulSets may have fixed replicas by design. DaemonSets — skip replica/HPA logic.

## Empty-data fallback

Try Kubernetes workload lookup plus alternate Datadog tags/capabilities; broaden historical search to
14d/30d where valid. Still empty across available sources → `STOP_REASON: insufficient_metrics` —
report attempted sources and scopes; do not guess a verdict.

### Service name mismatch (when `insufficient_metrics`)

Before concluding the service is unobservable, treat empty metrics as a **possible name mismatch**:

1. **Suggest the name may be wrong** — state explicitly: *"No workload or metrics for
   `<provided_name>` — the cluster name or telemetry tag may differ."*
2. **Disambiguation steps:**
   - Use Kubernetes MCP to list bounded workload-name matches in the named namespace/cluster.
   - `get_datadog_metric_context` on `kubernetes.cpu.requests` — list `kube_deployment`, `service`, `kube_statefulset` tag values matching a substring of the user input.
   - `search_datadog_metrics` with the user's keyword — surface close tag values.
   - If APM `service:` tag differs from `kube_deployment:` (common), try both scopes.
   - Ask the user to confirm the correct deployment name, namespace, or APM service tag.
3. **Report attempted sources and scopes** in the blocked report (cluster/namespace, tags, env filters, window lengths).
4. Only emit `insufficient_metrics` after **≥2 tag strategies** and user confirmation (or explicit *"proceed with unknown"*).

## Namespace ranking

Cluster-wide / namespace waste asks only: run namespace ranking queries ([queries.md](../queries.md), `aggregator: avg`, 7d), waste % `(reserved − used) / reserved × 100`, rank top 5, drill into worst deployment, then continue resolve.
