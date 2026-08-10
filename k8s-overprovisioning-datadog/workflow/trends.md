---
workflow_version: 3.5
phase: normalize-trends
produces: {trend_classification: object}
consumes:
  required: {raw_metrics: object, evidence_ids: list}
  optional: {}
  conditional: {}
---

# Trend detection

Classify per dimension using the 7d window (or first half vs second half of 7d; prior 7d if available).

| Class | Rule (indicative) | Inference impact |
|-------|-------------------|------------------|
| **Stable** | Utilization change < 10% | Baseline trustworthy |
| **Improving** | Usage down, throttle/OOM down | Slightly higher trim confidence |
| **Regressing** | Avg up > 15% or lag up trend | Lower trim confidence; defer |
| **Oscillating** | Replica or CPU CV high | Defer replica/HPA changes |
| **Recently changed** | Request/limit/replica step in window | Size on post-change period only |
| **Seasonal** | Weekday vs weekend (or business-hours vs off-hours) avg differs **> 2×** | **Do not cut** on blended 7d avg — flag *seasonal pattern — do not cut* |

### Seasonality detection

Split the 7d window by day-of-week (Mon–Fri vs Sat–Sun) or by business-hours bucket when hourly metrics
exist. When peak-day (or peak-hour) utilization **> 2×** trough-day avg **and** trough-day avg alone
would qualify as overprovisioned → classify **Seasonal**, not Stable/Improving.

Human Report: *"Seasonal pattern — do not cut based on weekly average; peak-day utilization requires
current headroom."*

Report trends in **Trends** table separate from snapshot verdicts.
