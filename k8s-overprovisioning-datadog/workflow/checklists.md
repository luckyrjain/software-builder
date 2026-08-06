---
workflow_version: 3.4
phase: checklists
produces:
  - checklist_status
consumes:
  - dimension_context
---

# Checklists

Single source for repeated guardrails. Complete relevant checklist before marking a dimension done.

## CPU sizing

- [ ] Units converted (nanocores → cores)
- [ ] Scope: app container (`kube_container_name`) vs pod (sidecars)
- [ ] Fleet p95 from `.dist` for sizing (not avg alone)
- [ ] App max per pod for burst (> 150% request = bursty)
- [ ] Throttle rate checked
- [ ] Cyclic pattern ([cpu-analysis.md](cpu-analysis.md#cyclic-check)) if trim proposed
- [ ] Manifest vs running reconciled or drift flagged
- [ ] Trend classified ([trends.md](trends.md))

## Memory sizing

- [ ] Peak proxy = worst-pod app max (**not p95**)
- [ ] Java heap cross-check if applicable
- [ ] requests:limits ratio before trim
- [ ] OOM kills checked
- [ ] Deployment total cross-check (per-pod × replicas)

## Replica / HPA

- [ ] HPA name resolved (≠ deployment name)
- [ ] KEDA probed if no HPA metrics
- [ ] `scaleDown` stabilization + policies read
- [ ] Kafka lag all groups validated
- [ ] Partition assignment (not count alone)
- [ ] PDB + ResourceQuota known or marked `missing` / `unknown`
- [ ] Active monitors checked

## Collection / scope

- [ ] Source profile inventories Kubernetes and Datadog capabilities independently
- [ ] Kubernetes MCP used for live state when available; Datadog fallback selected per capability
- [ ] Source/tool/query/window/aggregation recorded per observation
- [ ] Dual-source disagreement preserved and gated as `conflicting_signals`
- [ ] `telemetry.intent` on every Datadog call
- [ ] `{deploy_scope}` vs `{app_scope}` correct ([queries.md](../queries.md))
- [ ] HPA queries use resolved `horizontalpodautoscaler` tag

## Report (v3.0 — graph-first)

- [ ] `decision_graph` built before any markdown ([build-graph.md](../workflow/build-graph.md))
- [ ] INV-01–INV-14 pass ([validate-invariants.md](../workflow/validate-invariants.md))
- [ ] `schema_version: 3` on graph
- [ ] `OBS_*` / `EVID_*` / `DEC_*` / `REC_*` namespaced IDs
- [ ] Values only in `observations[]` — DRY elsewhere
- [ ] `ASSESSMENT_CONFIDENCE` and `RECOMMENDATION_CONFIDENCE` with arithmetic
- [ ] Render via [render/markdown.md](../render/markdown.md) — not hand-authored tables
