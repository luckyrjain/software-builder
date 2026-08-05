---
workflow_version: 3.3
phase: resolve
produces:
  - service_identity
  - namespace_ranking
consumes:
  - user_intent
---

# Resolve service identity

Map the user's service name to Datadog tags (try in order):

| Tag | Example | Use when |
|-----|---------|----------|
| `kube_deployment` | `example-service` | Deployment-level K8s metrics (preferred) |
| `kube_statefulset` | `redis-cluster` | StatefulSet workloads |
| `kube_daemonset` | `fluentd` | DaemonSet (scales with nodes) |
| `service` | `example-service` | APM / Service SLI |
| `horizontalpodautoscaler` | `example-service` | HPA replica metrics |

Confirm with `get_datadog_metric_context` on `kubernetes.cpu.requests` (`tag_filter: kube_deployment`). If ambiguous, ask the user or default `env:production` when present.

**HPA name:** resolve via `get_datadog_metric_context` on `kubernetes_state.hpa.current_replicas` filtered by `kube_deployment:<name>` — do not assume HPA name equals deployment name.

**Workload notes:** StatefulSets may have fixed replicas by design. DaemonSets — skip replica/HPA logic.

## Empty-data fallback

Retry alternate tags; broaden to 14d/30d; list tag values via metric context. Still empty → `STOP_REASON: insufficient_metrics` — report attempted scopes; do not guess a verdict.

### Service name mismatch (when `insufficient_metrics`)

Before concluding the service is unobservable, treat empty metrics as a **possible name mismatch**:

1. **Suggest the name may be wrong** — state explicitly: *"No metrics for `<provided_name>` — the service tag may not match Datadog."*
2. **Disambiguation steps:**
   - `get_datadog_metric_context` on `kubernetes.cpu.requests` — list `kube_deployment`, `service`, `kube_statefulset` tag values matching a substring of the user input.
   - `search_datadog_metrics` with the user's keyword — surface close tag values.
   - If APM `service:` tag differs from `kube_deployment:` (common), try both scopes.
   - Ask the user to confirm the correct deployment name, namespace, or APM service tag.
3. **Report attempted scopes** in the blocked report (tags tried, env filters, window lengths).
4. Only emit `insufficient_metrics` after **≥2 tag strategies** and user confirmation (or explicit *"proceed with unknown"*).

## Namespace ranking

Cluster-wide / namespace waste asks only: run namespace ranking queries ([queries.md](../queries.md), `aggregator: avg`, 7d), waste % `(reserved − used) / reserved × 100`, rank top 5, drill into worst deployment, then continue resolve.
