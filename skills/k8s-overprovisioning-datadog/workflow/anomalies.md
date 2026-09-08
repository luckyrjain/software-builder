---
workflow_version: 3.5
phase: normalize-anomalies
produces: {anomaly_flags: list}
consumes:
  required: {raw_metrics: object, evidence_ids: list}
  optional: {}
  conditional: {}
---

# Anomaly detection

During NORMALIZE, flag operational weirdness — not sizing verdicts.

| Pattern | Look for | Effect |
|---------|----------|--------|
| CPU reset | Sudden drop to ~0 across pods | Recent restart/deploy — shorten trust in 7d avg |
| Redeploy mid-window | `kubernetes.cpu.requests` step change, pod name churn, or deployment event < 7d ago | **`metrics_stale_redeploy`** — pre-change metrics pull p95 down; narrow window to post-redeploy or defer cuts |
| Replica oscillation | HPA current swings > 2×/day | Classify trend **oscillating** — defer replica cuts |
| Request doubled | `kubernetes.cpu.requests` step change in window | **recently_changed** — do not size on pre-change avg |
| Limit missing | limits null or 0 | OOM risk unknown — block memory trim |
| OOM spike | terminated reason oomkilled | `oom_kills` |
| Metric disappearance | Series absent mid-window | Lower observation confidence |
| Node migration | pod churn + new node names | Note in anomalies; check restarts |
| HPA disabled | hpa metrics vanish | Fixed replicas — branch replica-analysis |
| Autoscaler stuck | desired ≠ current sustained days | Do not reduce — scale-up lag |

List anomalies in report **Anomalies** section with evidence IDs.
