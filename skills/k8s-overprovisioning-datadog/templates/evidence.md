## Evidence

**Evidence Registry appendix only** — provenance registry. Not shown in the Human Report.

Provenance for `OBS_*` — **no values**. Row ID = `EVID_<same suffix>`.

| EVID_ID | OBS_ID | Source | Metric | Aggregation | Window | Scope | Quality | Weight |
|---------|--------|--------|--------|-------------|--------|-------|---------|--------|
| EVID_CPU_REQUEST | OBS_CPU_REQUEST | Kubernetes MCP | Deployment resources.requests.cpu | current | point-in-time | app container | measured | high |
| EVID_CPU_REQUEST_ALT_DATADOG | OBS_CPU_REQUEST_ALT_DATADOG | Datadog | kubernetes.cpu.requests | latest | point-in-time | app container | measured | medium |
| EVID_CPU_USAGE_AVG | OBS_CPU_USAGE_AVG | Datadog | kubernetes.cpu.usage.total | avg | 7d | app container | measured | medium |
| EVID_CPU_P95_FLEET | OBS_CPU_P95_FLEET | Datadog | kubernetes.pod.cpu.usage.dist | p95.dist | 7d | pod-scoped | measured | critical |
| EVID_PDB_STATUS | OBS_PDB_STATUS | — | poddisruptionbudget | — | — | deployment | missing | low |

Quality: `measured` | `inferred` | `missing` | `unknown` | `not_applicable`

If both sources expose the same signal, keep canonical + `_ALT_<SOURCE>` observation/evidence pairs;
label live and historical windows explicitly. Material disagreement belongs in Contradictions with
`conflicting_signals`.
