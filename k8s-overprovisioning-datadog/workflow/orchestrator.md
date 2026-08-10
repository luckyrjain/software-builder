---
workflow_version: 3.5
phase: orchestrator
produces: {intent_route: string, modules_to_load: list}
consumes:
  required: {user_intent: string}
  optional: {}
  conditional: {}
---

# Orchestrator — decision tree and routing

## Instruction priority

| Priority | Scope | Examples |
|----------|-------|----------|
| **P0** | Safety & correctness | [stop-reasons.md](stop-reasons.md), scope, auth |
| **P1** | Evidence | COLLECT + NORMALIZE, [evidence.md](evidence.md) |
| **P2** | Reasoning | [reason.md](reason.md), [validate.md](validate.md), dimension modules |
| **P3** | Graph + render | [build-graph.md](build-graph.md), [render.md](render.md) |

## Pipeline

```
DISCOVER_SOURCES → RESOLVE → COLLECT → NORMALIZE → REASON → VALIDATE → [COST] → BUILD_GRAPH → VALIDATE_INVARIANTS → RENDER
```

| Phase | Module | Output |
|-------|--------|--------|
| DISCOVER_SOURCES | [discover-sources.md](discover-sources.md) | `source_profile` before any workload query |
| RESOLVE | [resolve-service.md](resolve-service.md) | `service_identity` using selected routes |
| COLLECT | [collect-metrics.md](collect-metrics.md) | raw observations + updated source failures |
| NORMALIZE | [evidence.md](evidence.md) | `OBS_*`, `EVID_*` |
| REASON | [reason.md](reason.md) + dimensions | inferences, `DEC_*` candidates |
| VALIDATE | [validate.md](validate.md) | gates, contradictions |
| COST | [cost-analysis.md](cost-analysis.md) | optional — populates `appendix.cost` on graph |
| BUILD_GRAPH | [build-graph.md](build-graph.md) | **`decision_graph`** (primary artifact) |
| VALIDATE_INVARIANTS | [validate-invariants.md](validate-invariants.md) | `validated_graph` |
| RENDER | [render.md](render.md) | markdown (default) and/or JSON |

**Reasoning never writes markdown.** Markdown is a [render/markdown.md](../render/markdown.md) view of the graph.

## Intent routing

`intent_route` (this phase's own output) takes exactly one of the five values below — the ID column is
canonical and referenced by [workflow-contract.yaml](../workflow-contract.yaml).

| ID | User intent | Through BUILD_GRAPH | Skip |
|----|-------------|---------------------|------|
| `full` | Full / overprovisioned | discover → resolve → collect → cpu → memory → replica → workload → reason → validate → cost → graph → render | — |
| `cost_savings` | Cost savings | … → cpu → memory → workload → reason → validate → cost → graph → render | replica deep-dive |
| `replicas_too_high` | Replicas too high? | … → replica → workload → reason → validate → graph → render | cost |
| `throttle_oom` | Throttle / OOM | … → cpu → memory → workload → reason → validate → graph → render | replica cuts, cost |
| `namespace_ranking` | Namespace waste / cost ranking | resolve (namespace_ranking) → reason → graph → render | replica deep-dive, per-svc memory |

Workload always loads alongside any of cpu/memory/replica — its `OBS_KAFKA_LAG_*`/SLO-correlation
output feeds every dimension module's own gating (`reason.md`'s `DEC_CPU_REQUEST` example cites
`OBS_KAFKA_LAG_MAX`), not just replica sizing. Cost savings needs `DEC_CPU_REQUEST`/`DEC_MEMORY_REQUEST`
ALLOW/DEFER decisions to evaluate its own skip condition ("No ALLOW/DEFER dimension with savings
potential", [cost-analysis.md](cost-analysis.md#when-to-skip)) and `cost-estimation.md`'s savings
formulas consume cpu-analysis.md's/memory-analysis.md's percentile and peak-proxy output directly — so
cpu and memory always run for a cost-savings ask; only the replica deep-dive is skipped.

Before BUILD_GRAPH: [confidence.md](confidence.md). Graph schema: [decision-graph-schema.md](../reference/decision-graph-schema.md).

Optional pre-render gate: [validate.md#deploy-freeze-check-optional](validate.md#deploy-freeze-check-optional) —
run when Jira, user calendar, or GitLab merge-freeze MCP is available; skip otherwise.

## Decision tree

```
START → discover-sources.md (capability inventory; no workload query)
  ↓
resolve-service.md (consume source_profile)
  ↓
Workload kind = StatefulSet (per resolve-service.md `kube_statefulset`)? YES → load
  [workload-analysis.md § StatefulSets](workload-analysis.md#statefulsets) before REASON
  ↓
Pre-flight: active incident + redeploy staleness + VPA read ([collect-metrics.md](collect-metrics.md#pre-flight-before-metric-queries))
  ↓
Combined evidence sufficient for a requested sizing dimension? NO → insufficient_metrics → minimal blocked graph → render
  ↓
REASON + VALIDATE
  ↓
BUILD_GRAPH (typed object — not markdown)
  ↓
VALIDATE_INVARIANTS — fail? → emit graph + violations only
  ↓
RENDER (markdown default; json on request)
```

## Underprovisioned path

`throttle_high`, `oom_kills`, HPA max → skip cost; `assessment.final_decision: SCALE_UP`; graph includes `scale_up_advisory` recs.

## Dashboards

Optional. `search_datadog_dashboards` by title — see [SETUP.md](../SETUP.md).
