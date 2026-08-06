# Phase index

Canonical names: [phase-glossary](../../docs/skill-framework/shared/phase-glossary.md#4-k8s-mapping)

**One workflow file per phase** — never bulk-load workflow or reference files. Optional **COST** runs
only when the cost gate is open ([validate.md](../workflow/validate.md#cost-gate)).

| Order | Phase | Workflow file | Produces |
|-------|-------|---------------|----------|
| 0 | Detect / route | [orchestrator.md](../workflow/orchestrator.md) | `intent_route`, modules to load |
| 0a | DISCOVER_SOURCES | [discover-sources.md](../workflow/discover-sources.md) | `source_profile` before any workload query |
| 0b | RESOLVE | [resolve-service.md](../workflow/resolve-service.md) | `service_identity` using selected routes |
| 0c | Namespace waste ranking *(cluster-wide)* | [resolve-service.md](../workflow/resolve-service.md) §Namespace ranking | `namespace_ranking`, drill-down target |
| 1 | COLLECT | [collect-metrics.md](../workflow/collect-metrics.md) | raw metrics, pre-flight |
| 2 | NORMALIZE | [evidence.md](../workflow/evidence.md) | `OBS_*`, `EVID_*` registries |
| 3 | REASON | [reason.md](../workflow/reason.md) (+ [confidence.md](../workflow/confidence.md) §APM latency modifier) + dimension modules | `DEC_*` candidates, inferences |
| 4 | VALIDATE | [validate.md](../workflow/validate.md) | gates, `validated_decisions` |
| 5 | COST *(optional)* | [cost-analysis.md](../workflow/cost-analysis.md) | `appendix.cost` on graph |
| 6 | BUILD_GRAPH | [build-graph.md](../workflow/build-graph.md) | **`decision_graph`** |
| 7 | VALIDATE_INVARIANTS | [validate-invariants.md](../workflow/validate-invariants.md) | `validated_graph` |
| 8 | RENDER | [render.md](../workflow/render.md), [report.md](../workflow/report.md) | Human Report + appendix |

```
DISCOVER_SOURCES → RESOLVE → COLLECT → NORMALIZE → REASON → VALIDATE → [COST] → BUILD_GRAPH → VALIDATE_INVARIANTS → RENDER
```

Dimension modules (loaded on intent during REASON): [cpu-analysis.md](../workflow/cpu-analysis.md),
[memory-analysis.md](../workflow/memory-analysis.md), [replica-analysis.md](../workflow/replica-analysis.md),
[workload-analysis.md](../workflow/workload-analysis.md).

Precedence when specs conflict: [precedence.md](precedence.md). Lazy-load map: [lazy-load-index.md](lazy-load-index.md).
