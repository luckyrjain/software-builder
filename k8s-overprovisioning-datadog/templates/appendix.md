## Technical Appendix

*Internal IDs, hashes, and graph structure for audit and automation. Omitted in summary-only render mode.*

### Decision Graph

`DEC_*` status, Reasons, blocking edges, assumptions. Template: [decision.md](decision.md).

### Evidence Registry

Grouped by dimension — observations, provenance, and recommendations together.

#### Observations & provenance

Full `OBS_*` value tables and `EVID_*` provenance. Templates: [observations.md](observations.md), [evidence.md](evidence.md).

#### Recommendations

Lifecycle summary and per-`REC_*` detail. Template: [recommendations.md](recommendations.md).

#### Extended detail (optional)

When present on the graph — configuration drift, cost, queries, trends:

##### ConfigurationDrift

*Only when MANIFEST_* ≠ RUNNING_*. Advisory only until reconciled.*

| Source | CPU request | Memory request |
|--------|-------------|----------------|
| Repo | X | Y |
| Running | X | Y |

##### CurrentConfiguration

| Resource | Per pod | Deployment total |
|----------|---------|------------------|
| Replicas | — | N |
| HPA | min / max / current | N/A |
| CPU request | X cores | Y cores |
| Memory request | X GiB | Y GiB |
| Sidecars | Istio / … | node packing |

##### DimensionDetail

CPU, memory, replicas, stability — reference `OBS_*` IDs; values in Observations table only.

##### LowUtilizationInvestigation

| Hypothesis | Observation IDs | Status |
|------------|-----------------|--------|
| Hot partition | OBS_KAFKA_LAG_* | … |

##### SloCorrelation

| SLO | Current | If optimized |
|-----|---------|--------------|
| p99 latency | missing / X ms | Must hold |

##### WasteEstimate / CostImpact

| Dimension | Reserved | Used | Waste % |
|-----------|----------|------|---------|
| CPU | X | Y | Z |

##### StagedRollout

1. Verify partitions and lag at peak.
2. Step: 10 → 8 replicas, monitor ≥ 1 week.
3. Rollback triggers per step.

##### QueryReferences

| Query | Intent |
|-------|--------|
| `avg:kubernetes.cpu.usage.total{…}` | OBS_CPU_USAGE_AVG |

##### Caveats

- …

### Assessment Metadata

`schema_version`, `threshold_version`, `AssessmentFingerprint`, hashes, decision history — no weighted-sum arithmetic in default render. Template: [metadata.md](metadata.md).

### Validation

`INV-01`–`INV-13` results, contradiction gate, cost gate. Templates: [contradictions.md](contradictions.md); spec: [validate-invariants.md](../workflow/validate-invariants.md).
