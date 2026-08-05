---
workflow_version: 3.0
phase: confidence
produces:
  - telemetry_quality
  - assessment_confidence
  - recommendation_confidences
consumes:
  - observation_registry
  - evidence_registry
  - contradiction_gate
---

# Confidence (deterministic)

[reference/confidence-formula.md](../reference/confidence-formula.md) — **weighted sum, not product**.

## ASSESSMENT_CONFIDENCE

```
round(0.35×completeness + 0.35×quality + 0.15×contradiction_resolution + 0.15×telemetry_availability, 1)
```

Store `arithmetic` on the graph for INV-07. Default render: band + factor list in Assessment Metadata — **no weighted-sum arithmetic** ([report.md](report.md)).

## RECOMMENDATION_CONFIDENCE

Per `REC_*` — separate formula (0.40/0.30/0.15/0.15 weights). Apply caps after compute.

**Never** copy assessment score to recommendations.

## Bands

1 decimal + label: `0.9 (Very High)`.

## Telemetry → telemetry_availability

★5=1.0 · ★4=0.95 · ★3=0.85 · ★2=0.75 · ★1=0.70

## Assessment severity

| Severity | When |
|----------|------|
| `CRITICAL` | `auth_failure`, `insufficient_metrics`, severe underprovisioned |
| `WARNING` | Valid assessment; optimization blocked (`DEC_*` BLOCKED/DEFER) |
| `INFO` | No material blockers |

## APM latency modifier (RECOMMENDATION_CONFIDENCE only)

Apply **before** finalizing per-`REC_*` confidence scores, when APM signals were collected:

```
IF OBS_APM_LATENCY_P99_TREND == "rising"
AND OBS_DERIVED_CPU_UTIL_P95 < 50%  (CPU looks healthy)
→ Subtract 0.15 from RECOMMENDATION_CONFIDENCE for any CPU cut recommendation
→ Add note to DEC rationale:
  "APM p99 latency is trending upward despite low CPU utilization. The bottleneck may be
  non-CPU (connection pool, DB saturation, thread limit, GC pressure). Confidence in CPU
  cut reduced — investigate APM before trimming."
```

This modifier does NOT apply to:
- Keep/hold recommendations (only cut recommendations are affected)
- Memory or replica recommendations (CPU-specific bottleneck signal)
- When `OBS_APM_LATENCY_P99_TREND` is `missing` (absent metrics cannot lower confidence)
