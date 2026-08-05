# Recommendation IDs (`REC_`)

Prefix **required**. Stable across report versions.

## CPU

| ID | Action |
|----|--------|
| `REC_CPU_KEEP` | Keep CPU request |
| `REC_CPU_REDUCE` | Lower CPU request |
| `REC_CPU_INCREASE` | Raise CPU request |
| `REC_CPU_DIST_QUERY` | Query fleet `.dist` percentiles |

## Memory

| ID | Action |
|----|--------|
| `REC_MEMORY_KEEP` | Keep memory request |
| `REC_MEMORY_REDUCE` | Lower memory request |
| `REC_MEMORY_INCREASE` | Raise memory request |

## Replicas / HPA

| ID | Action |
|----|--------|
| `REC_REPLICA_KEEP` | Do not change replicas |
| `REC_REPLICA_REDUCE` | Reduce replicas (staged) |
| `REC_HPA_OBSERVE` | Phase 1 — observe scaling signals |
| `REC_HPA_EVALUATE` | Phase 2 — evaluate metric correlation |
| `REC_HPA_ADJUST` | Change min/max replicas |

## Kafka / observability

| ID | Action |
|----|--------|
| `REC_KAFKA_LAG_INSTRUMENT` | Instrument all consumer groups |
| `REC_PARTITION_VALIDATE` | Validate partition assignment |
| `REC_SLO_BASELINE` | Capture SLO baseline |

## Ops

| ID | Action |
|----|--------|
| `REC_MANIFEST_RECONCILE` | Reconcile repo vs running |
| `REC_SIDECAR_ACCOUNT` | Account for sidecars in packing |
| `REC_RESTART_INVESTIGATE` | Investigate restarts before cuts |

## State machine (finite — no other values)

| State | Meaning |
|-------|---------|
| `READY` | Prerequisites met; safe to execute |
| `BLOCKED` | Hard stop — dependency or decision blocks execution |
| `DEFERRED` | Waiting on evidence or observation period |
| `REJECTED` | Analysis concluded this action is wrong |
| `COMPLETED` | Done (repeat assessments only) |

Do not use `Observe`, `Ready`, or `Blocked` — use the enum above exactly in the **graph**.

## Appendix display labels

Graph `status` is unchanged. The **Technical Appendix** (LifecycleSummary + per-rec detail) translates:

| Graph `status` | Rec pattern | Appendix State |
|----------------|-------------|----------------|
| `BLOCKED` | `REC_*_KEEP`, `REC_*_OBSERVE` | **KEEP** |
| `BLOCKED` | change rec blocked by STOP_REASON | **BLOCKED** |
| `READY` / `COMPLETED` | actionable change | **CHANGE** |
| `DEFERRED` | | **DEFER** |
| `REJECTED` | | **NOT RECOMMENDED** |

## Human render notes

**Sort tier (Human Report Recommendations section):** Tier 1 observability → Tier 2 actionable change → Tier 3 hold. Full rule: [render/markdown.md](../render/markdown.md#recommendationssummary-sort-order).

Graph `status` values are unchanged. The **Human Report** translates by rec intent ([workflow/report.md](../workflow/report.md)):

| Graph `status` | Rec pattern | Human line |
|----------------|-------------|------------|
| `BLOCKED` | `REC_*_KEEP`, `REC_*_OBSERVE` | **Decision: Keep** |
| `BLOCKED` | change rec blocked by STOP_REASON | **Blocked** |
| `READY` / `COMPLETED` | actionable change | **Ready** |
| `DEFERRED` | | **Defer** |
| `REJECTED` | | **Changes evaluated but not recommended** section only |

