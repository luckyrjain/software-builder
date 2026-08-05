## Observations

**Evidence Registry appendix only** — full ID registry. Human Report uses [human-report.md](human-report.md#evidencesummary) with human labels.

Values only — provenance in `Evidence` (`EVID_*`). IDs: [observation-ids.md](../reference/observation-ids.md).

### Measured

| ID | Value |
|----|-------|
| OBS_CPU_USAGE_AVG | 2.12 cores |
| OBS_CPU_REQUEST | 20 cores |
| OBS_CPU_P95_FLEET | 30.4 cores |
| … | … |

### Derived

| ID | Value | Formula |
|----|-------|---------|
| OBS_DERIVED_CPU_UTIL_AVG | 10.6% | OBS_CPU_USAGE_AVG ÷ OBS_CPU_REQUEST |
| OBS_DERIVED_CPU_UTIL_P95 | 152% | OBS_CPU_P95_FLEET ÷ OBS_CPU_REQUEST |

### Missing / unknown / N/A

| ID | State |
|----|-------|
| OBS_PDB_STATUS | missing |

**DRY:** Do not repeat these values outside `Observations` and `Evidence`.
