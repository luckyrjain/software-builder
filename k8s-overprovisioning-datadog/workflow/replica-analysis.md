---
workflow_version: 3.3
phase: replica-analysis
produces:
  - replica_verdict
  - hpa_analysis
consumes:
  - raw_metrics
  - evidence_ids
---

# Replica and HPA analysis

Checklist: [checklists.md](checklists.md#replica-hpa).

## KEDA

If `hpa_*` null or `OBS_KEDA_SCALER_ACTIVE` is set, this is a KEDA-managed workload. Follow the
KEDA path — do **not** use CPU target % for the replica verdict.

### Collection
Load `OBS_KEDA_SCALER_TYPE`, `OBS_KEDA_METRIC_VALUE`, and `OBS_KEDA_METRIC_TARGET` from COLLECT
(see `collect-metrics.md` § KEDA workloads). If either value is `missing` →
`STOP_REASON: missing_keda_metrics`; defer replica verdict.

### Evaluation

| Condition | Verdict |
|-----------|---------|
| `OBS_KEDA_METRIC_VALUE` consistently < `OBS_KEDA_METRIC_TARGET × 0.3` (7d avg) AND replicas > `spec.minReplicaCount` | **Candidates for `spec.minReplicaCount` reduction** — KEDA is keeping replicas alive for a metric that rarely triggers |
| `OBS_KEDA_METRIC_VALUE` near zero for the entire 7d window | Strong signal: minimum replica floor may be too high |
| `OBS_KEDA_METRIC_VALUE` frequently >= `OBS_KEDA_METRIC_TARGET` | Under-scaled or target too low — do not reduce |
| KEDA scaler type is `kafka` | Cross-check with `OBS_KAFKA_LAG_*` (see HPA metric suitability table) |

### Guardrails
- Never recommend cutting below `spec.minReplicaCount`.
- Never recommend setting a CPU HPA target on a KEDA workload — use the external metric.
- If VPA is also present on this deployment, check for VPA+HPA conflict per `reason.md`.

## HPA metric suitability

[thresholds.md](../thresholds.md#hpa-metric-suitability). Phase 1 observe ≥2 weeks → Phase 2 evaluate before metric changes.

## Scale-down behavior

From manifest `spec.behavior.scaleDown`:

- `stabilizationWindowSeconds` (default 300) — desired < current ≠ immediate scale-down
- `policies` (Pods/Percent limits) — replicas trail utilization
- Restrictive policies + low CPU → `scale_down_policy_lag` — not overscaled

## Replica reduction candidate

**All** required: HPA min=max=current; `hpa_desired ≈ hpa_current ≈ replicas_ready`; fleet p95 < 50% request; Kafka lag stable **every** group (or no Kafka); `proposed ≤ partitions`; drivers understood. Never cut > 25% per step.

Missing lag → `missing_kafka_lag`. Missing PDB → cap confidence; mark Unknown if not provided.

## Verdicts

[thresholds.md](../thresholds.md#replica-hpa).

PDB / ResourceQuota via git MCP (same guardrails as collect-metrics) or user paste.

## Workload context

See [workload-analysis.md](workload-analysis.md) — mandatory for replica recommendations.
