## Recommendations

**Evidence Registry subsection (full rec tables)** — Human Report uses prose in [human-report.md](human-report.md#recommendationssummary).

Sorted: **Tier 1 observability** → **Tier 2 actionable change** → **Tier 3 hold**; within tier: `priority` → confidence → benefit → effort. Rule: [render/markdown.md](../render/markdown.md#recommendationssummary-sort-order). IDs: [recommendation-ids.md](../reference/recommendation-ids.md).

### LifecycleSummary

| REC_ID | State |
|--------|-------|
| REC_KAFKA_LAG_INSTRUMENT | DEFER |
| REC_MEMORY_INCREASE | CHANGE |
| REC_CPU_KEEP | KEEP |
| REC_REPLICA_KEEP | KEEP |
| REC_CPU_REDUCE | NOT RECOMMENDED |

Appendix **State** labels: `KEEP` | `DEFER` | `CHANGE` | `NOT RECOMMENDED` | `BLOCKED` (change rec gated by STOP_REASON only).

Graph stores raw enum (`READY` | `BLOCKED` | `DEFERRED` | `REJECTED` | `COMPLETED`) — map at render per [render/markdown.md](../render/markdown.md#appendix-recommendation-status).

Human Report maps separately — see [human-report.md](human-report.md#recommendationssummary).

---

### REC_CPU_KEEP

- **State:** KEEP
- **Decision confidence:** 0.9 (Very High)
- **Depends on:** `OBS_CPU_P95_FLEET`, `OBS_CPU_THROTTLE_RATE`, `ASSUME_P95_REPRESENTATIVE`
- **Blocked by:** `DEC_CPU_REQUEST`
- **Risk:** Likelihood Low · Impact Low · Residual Low

### REC_KAFKA_LAG_INSTRUMENT

- **State:** DEFER
- **Decision confidence:** 0.4 (Low)
- **Depends on:** `OBS_KAFKA_LAG_MAX_*` (missing)
- **Blocked by:** —
- **Risk:** Likelihood Low · Impact Low · Residual Low

### REC_CPU_REDUCE

- **State:** NOT RECOMMENDED
- **Decision confidence:** 0.3 (Very Low)
- **Depends on:** `OBS_CPU_P95_FLEET`, `REC_PARTITION_VALIDATE` (READY)
- **Blocked by:** `DEC_CPU_REQUEST`
- **Rollback:** structured `ROLLBACK_IF <metric> <comparator> <threshold> FOR <duration> REVERT_TO <action>` per [recommendation-framework.md](../recommendation-framework.md#rollback-trigger-format-required-on-every-ready-change-rec)

**DRY:** Reference `OBS_*` / `DEC_*` only — no duplicated metric values. Per-rec confidence arithmetic stays in graph `recommendation_confidence.arithmetic` — not default appendix render.

### Delivery pointer (CHANGE recs only)

Each graph-`READY` change recommendation must include `delivery_pointer` in the graph (rendered as
**Where to apply** in the Human Report). Infer from git MCP manifest lookup:

| Repo signal | Typical path |
|-------------|--------------|
| Helm chart | `helm/<release>/values.yaml` or `charts/<svc>/values.yaml` — `resources.requests` |
| Kustomize | `k8s/<env>/<svc>/kustomization.yaml` + overlay patch |
| Raw manifest | `deploy/<svc>/deployment.yaml` |
| Terraform | `modules/<svc>/main.tf` — `kubernetes_deployment` resource |
| GitOps | ArgoCD Application / Flux Kustomization path referencing the chart or overlay |

When git MCP is unavailable, use user-provided path or *path not verified*.
