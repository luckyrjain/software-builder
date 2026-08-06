---
workflow_version: 3.0
phase: validate
produces:
  - validated_decisions
  - cost_gate
  - contradiction_gate
consumes:
  - inferences
  - decision_objects
  - assumptions
---

# Validation

Run after [reason.md](reason.md), before recommendations and [cost-analysis.md](cost-analysis.md).

Validation output (`INV-*`, gate tables, contradiction resolution) → **Appendix D only** in rendered markdown. Human Report Risks section summarizes outcomes in plain language ([workflow/report.md](report.md)).

## Contradiction gate

Unresolved contradictions set `contradiction_factor: 0.6` — no cut recommendations on affected dimensions.

| Signals | Typical resolution | Status |
|---------|-------------------|--------|
| DERIVED_CPU_UTIL_AVG low vs DERIVED_CPU_UTIL_P95 high | Sizing follows CPU_P95_FLEET | Resolved |
| Overprovisioned vs KAFKA_LAG rising | Observe only | Unresolved |

Record in `contradictions[]` for Appendix D. Human Report: one sentence (e.g. *Average CPU looks low but fleet p95 is high — sizing follows burst behavior, not weekly average.*).

Critical-weight wins per [evidence-weights.md](../reference/evidence-weights.md).

## Post-change projection gate

Before any CPU or memory **cut** recommendation reaches BUILD_GRAPH, verify the proposed new request
still clears measured usage:

| Dimension | Rule | Block when |
|-----------|------|------------|
| CPU cut | `proposed_cpu_request >= fleet_p95_cores` (from `OBS_CPU_P95_FLEET`) | Proposed request < measured fleet p95 |
| Memory cut | `proposed_mem_request >= peak_proxy` (worst-pod app-container max) | Proposed request < peak proxy |

If projection fails → dimension **BLOCKED**, cut rec **REJECTED**, `STOP_REASON: projection_failed`. Do
not emit the cut; keep current requests or defer. Formulas in [thresholds.md](../thresholds.md).

## Cross-dimension consistency

| Check | Rule |
|-------|------|
| Recommendations vs decisions | No ALLOW rec on BLOCKED dimension |
| Semantic ID refs | All Depends on IDs exist in Observations or registry |
| Contradictions vs recs | No cuts when Unresolved |
| Projection vs recs | No cut rec when post-change projection fails |
| Delivery pointer vs recs | No actionable **READY** rec without `delivery_pointer.path` **and** `verified: true` (INV-12) |

## Delivery pointer gate

Before BUILD_GRAPH, every **READY** recommendation that changes manifests (`REC_*_REDUCE`, `REC_*_INCREASE`,
`REC_HPA_ADJUST`, `REC_MANIFEST_RECONCILE`) must include:

```yaml
delivery_pointer:
  path: <helm/kustomize/manifest/terraform/gitops path>
  field: <yaml or tf attribute, optional>
  format: helm_values | kustomize | manifest | terraform | gitops
  verified: true | false
```

Obtain the path from Git-backed configuration ([collect-metrics.md](collect-metrics.md)) or explicit user
confirmation and set `verified: true`. Never infer a delivery path. **`verified: false` blocks `READY`** —
a recommendation cannot carry the "safe to execute" label while its own delivery pointer is unconfirmed.
Downgrade the recommendation's status to `DEFERRED` (missing evidence: unverified delivery path) until the
path is confirmed. **KEEP** / **OBSERVE** recs omit `delivery_pointer`. Enforced at INV-12 (**critical** —
blocks RENDER).
Schema: [decision-graph-schema.md](../reference/decision-graph-schema.md#recommendation).

## Cost gate

Skip cost when: Critical STOP_REASON, Unresolved contradiction, `optimization_not_feasible`, or user excludes cost.

## Namespace ResourceQuota / LimitRange gate

Before emitting a **cut** recommendation, verify proposed values fit namespace constraints (git MCP,
user paste, or cluster API when available):

| Check | Rule | Block when |
|-------|------|------------|
| **ResourceQuota** `requests.cpu` / `requests.memory` | `namespace_used + (current − proposed) × replicas` must stay ≤ quota hard limit | Cut would violate quota — recommend quota increase first |
| **LimitRange** min/max per container | Proposed request must be ≥ LimitRange minimum and ≤ maximum | Proposed value outside LimitRange bounds |
| Quota/LimitRange unknown | Mark `quota_unverified` — cap cut confidence ≤ 0.50; note in Risks | — |

Do not recommend cuts the namespace cannot admit at apply time.

## Deploy freeze check (optional)

Before marking any change recommendation **READY**, optionally verify the org is not in a merge or
deploy freeze. **Skip gracefully** when no source is available — never block the assessment.

| Source | Check | When unavailable |
|--------|-------|------------------|
| Jira | Search freeze tickets (`project=OPS AND summary ~ "deploy freeze" AND status != Done`) or linked INC | Note *deploy freeze not checked* in Risks |
| User | User-provided freeze calendar or *"we are frozen until …"* | — |
| GitLab | Project/group merge freeze via GitLab MCP if exposed | Skip silently |

When freeze is **active**:

- Downgrade affected recs from **READY** → **DEFERRED**
- Human Report Risks: *Deploy freeze in effect — defer apply until freeze lifts*
- Do not suppress the recommendation — keep rationale and delivery pointer for post-freeze apply

## Anomalies and trends

[anomalies.md](anomalies.md), [trends.md](trends.md) — lower inference confidence when regressing; **Seasonal**
trend blocks cuts per [reason.md](reason.md). Trend tables → Appendix E; human summary in Current Health or Risks if material.
