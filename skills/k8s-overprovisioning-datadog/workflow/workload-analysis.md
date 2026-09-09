---
workflow_version: 3.5
phase: workload-analysis
produces: {workload_signals: object, slo_correlation: object}
consumes:
  required: {raw_metrics: object, evidence_ids: list, service_identity: object}
  optional: {}
  conditional: {}
---

# Workload analysis

Required for replica paths; recommended for full review.

## Drivers

Correlate utilization with Kafka/SQS/job traffic — not HTTP alone. [queries.md](../queries.md). Confirm trace tags via `get_datadog_metric_context`.

## Kafka consumer lag

Mandatory if consume rate > 0 or consumer-heavy. Per group: lag avg/max, consume msg/s, est. lag seconds `lag / consume_rate`, validated ✅/❌. Any unvalidated group → `missing_kafka_lag` — block replica cut. Validate partition **assignment**, not count alone.

## SLO correlation

p95/p99 latency, error rate, request rate (APM). Every proposed change: customer-visible metrics **must remain unchanged**. Missing SLO → label Unknown; lower confidence.

## Active monitors

`search_datadog_monitors` (`service:<name> status:alert`). Required-severity firing → `firing_required_monitor`.
When `search_datadog_incidents` is available, also check for open/active incidents → `active_incident` (blocks all downsizing).

## Network I/O (optional)

CPU avg < 20% on I/O-bound services: `kubernetes.network.rx_bytes` / `tx_bytes`. High network + low CPU → network-bound, not overprovisioned.

## Stability

Restarts per [thresholds.md](../thresholds.md#container-restarts). Throttle > 5% → `throttle_high`.

## StatefulSets

StatefulSets have different scaling semantics than Deployments. When the assessed workload is a
StatefulSet (detected via `kind: StatefulSet` in manifest or `kubernetes_state.statefulset.*` metrics):

| Difference | Impact on assessment |
|-----------|---------------------|
| Ordered scaling (pods 0…N-1) | Scale-down removes highest-ordinal first; data redistribution may be required |
| Stable network identity | Clients may hardcode pod DNS; reducing replicas breaks direct connections |
| Persistent volumes | Each pod owns a PVC; scaling down does NOT delete volumes (orphaned PVCs = cost) |
| No surge during rolling update | `maxUnavailable` only — updates are slower; headroom more critical |
| Partition-affinity workloads | Kafka/ES/Cassandra often pin partitions to ordinals |

**Assessment guardrails for StatefulSets:**

1. **Never recommend replica reduction without confirming data redistribution is automatic** (e.g.
   Kafka partition reassignment, ES shard rebalancing). If unclear → `STOP_REASON: statefulset_data_affinity`.
2. **Check for orphaned PVCs** after any prior scale-down — `kubernetes_state.persistentvolumeclaim.*`
   with no matching pod indicates prior incomplete cleanup.
3. **CPU/memory request trims** are safe — same logic as Deployments. Apply standard thresholds.
4. **Replica cuts** require partition/shard awareness. For databases and message brokers, treat as
   higher risk than Deployment replicas (impact = Critical in risk scoring).
5. **Flag in report:** include a `Workload type: StatefulSet` line and note ordered-scaling implications.
