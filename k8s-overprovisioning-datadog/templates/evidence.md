## Evidence

**Evidence Registry appendix only** — provenance registry. Not shown in the Human Report.

Provenance for `OBS_*` — **no values**. Row ID = `EVID_<same suffix>`.

| EVID_ID | OBS_ID | Source | Metric | Aggregation | Window | Scope | Quality | Weight |
|---------|--------|--------|--------|-------------|--------|-------|---------|--------|
| EVID_CPU_USAGE_AVG | OBS_CPU_USAGE_AVG | Datadog | kubernetes.cpu.usage.total | avg | 7d | app container | measured | medium |
| EVID_CPU_P95_FLEET | OBS_CPU_P95_FLEET | Datadog | kubernetes.pod.cpu.usage.dist | p95.dist | 7d | pod-scoped | measured | critical |
| EVID_PDB_STATUS | OBS_PDB_STATUS | — | poddisruptionbudget | — | — | deployment | missing | low |

Quality: `measured` | `inferred` | `missing` | `unknown` | `not_applicable`
