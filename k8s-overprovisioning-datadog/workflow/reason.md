---
workflow_version: 3.0
phase: reason
produces:
  - inferences
  - decision_objects
  - assumptions
consumes:
  - observation_registry
  - evidence_registry
---

# Reasoning pipeline

Produce `DEC_*` objects with structured rationale — not recommendations.

Reasoning uses IDs internally. **Do not** expose `DEC_*` / `OBS_*` in the Human Report — render plain language per [workflow/report.md](report.md).

Precedence when specs conflict: [precedence.md](../reference/precedence.md).

## Decision object (`DEC_*`)

| Field | Required |
|-------|----------|
| DEC_ID | from [decision-ids.md](../reference/decision-ids.md) |
| Status | ALLOW \| BLOCKED \| DEFER |
| **Reasons** | `✓`/`✗` + `OBS_*` / `ASSUME_*` IDs only |
| **Explanation** | one sentence (also source for human Optimization Decision prose) |
| Blocking / Missing | `OBS_*` IDs |
| STOP_REASON | if any |

Example (graph / Decision Graph appendix):

```text
DEC_CPU_REQUEST | BLOCKED
Reasons: ✓ OBS_CPU_P95_FLEET ✓ OBS_KAFKA_LAG_MAX ✓ ASSUME_HPA_INTENTIONAL
Explanation: Fleet p95 exceeds sizing threshold.
```

Human render: *Keep CPU requests unchanged — fleet p95 exceeds the trim threshold.*

## WhyThisMatters

Reference `DEC_*` in the graph — do not repeat `OBS_*` values. Rendered human text cites evidence in prose; full ID linkage → Decision Graph appendix.

Dimension modules: [cpu-analysis.md](cpu-analysis.md), [memory-analysis.md](memory-analysis.md), [replica-analysis.md](replica-analysis.md).

## VPA alignment

When `OBS_VPA_TARGET_*` exists from COLLECT:

- VPA target **within 10%** of proposed cut → cite as corroborating evidence in DEC rationale.
- VPA target **above** current requests → BLOCK cut on that dimension; explain VPA recommends higher.
- VPA target **below** proposed cut → cap trim aggressiveness — do not go below VPA lowerBound without
  explicit user approval.

## VPA + HPA coexistence conflict

Before emitting any VPA-based cut recommendation, check for controller conflict:

```
IF OBS_VPA_TARGET_CPU is set AND hpa_targets_cpu == true:
  → STOP_REASON: vpa_hpa_conflict_cpu
  → Block ALL cut recommendations on the CPU dimension
  → Explanation: "VPA is adjusting CPU requests while HPA is scaling replicas on CPU
    utilization. When VPA raises CPU requests, HPA sees lower utilization and scales
    replicas down; when VPA lowers requests, HPA sees higher utilization and scales up.
    This creates oscillation. Disable CPU-dimension VPA or switch HPA to a custom/external
    metric before any sizing change."

IF OBS_VPA_TARGET_MEM is set AND hpa_targets_memory == true:
  → STOP_REASON: vpa_hpa_conflict_memory
  → Block ALL cut recommendations on the memory dimension
  → Explanation: same pattern — VPA memory adjustments fight HPA memory-based scaling.
```

When VPA targets a dimension that HPA does **not** target (e.g. VPA on memory, HPA on CPU only):
no conflict — VPA recommendation on memory is safe to use.

## Seasonality vs overprovisioning

Before ALLOW on CPU/memory trim, check [trends.md](trends.md) **seasonal** class:

- Weekday avg utilization **> 2×** weekend avg (or inverse for batch jobs) → classify **seasonal pattern
  — do not cut** on the full 7d average.
- Report: *"Utilization varies by day-of-week; weekly average understates peak-day need — size on peak
  window or defer."*
- DEC status → **DEFER** or **BLOCKED** with `seasonal_pattern` in Explanation — not Overprovisioned on
  blended average alone.

**Cut eligibility:** ALLOW on a dimension only when measured usage supports the proposed request.
VALIDATE applies the post-change projection gate ([validate.md](validate.md)) — a DEC that would permit a
cut below fleet p95 or peak proxy must be BLOCKED before recommendations.

## APM latency modifier (before BUILD_GRAPH)

When APM signals were collected, apply [confidence.md §APM latency modifier](confidence.md#apm-latency-modifier-recommendationconfidence-only) to CPU **cut** `REC_*` confidence scores **before** BUILD_GRAPH. Rising p99 + low CPU utilization reduces cut confidence — do not skip because pressure tests mention it only.
