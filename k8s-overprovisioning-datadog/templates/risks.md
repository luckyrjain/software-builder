## Risks

### StopReasons

| STOP_REASON | Severity | Effect |
|-------------|----------|--------|
| … | critical / high / medium | … |

### ReadinessChecklist

| Check | OBS_ID | Status |
|-------|--------|--------|
| Fleet p95 | OBS_CPU_P95_FLEET | ✅ / ❌ |
| All consumer lag | OBS_KAFKA_LAG_MAX_* | ✅ X/N / ❌ |
| PDB | OBS_PDB_STATUS | ✅ / missing |

### ConfidenceSummary

| REC_ID | RECOMMENDATION_CONFIDENCE |
|--------|---------------------------|
| REC_CPU_KEEP | 0.9 (Very High) |
| REC_REPLICA_REDUCE | 0.3 (Very Low) |

Reference IDs — values in `Observations`.
