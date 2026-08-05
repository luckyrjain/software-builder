# Evidence weights (v3.0)

Weight tiers affect `evidence_quality` inputs and contradiction resolution priority. Confidence is computed
via weighted sum — [confidence-formula.md](confidence-formula.md).

## Weight tiers

| Tier | `OBS_*` examples | Contradiction priority |
|------|------------------|------------------------|
| **critical** | `OBS_CPU_P95_FLEET`, `OBS_MEMORY_OOM_COUNT`, `OBS_CPU_THROTTLE_RATE` | Wins over medium/low |
| **high** | `OBS_KAFKA_LAG_MAX_*`, `OBS_RESTART_MAX_POD`, `OBS_MANIFEST_CPU_REQUEST` | Strong blockers |
| **medium** | `OBS_CPU_USAGE_AVG`, `OBS_MEMORY_USAGE_AVG`, `OBS_HTTP_RPS` | Supporting only |
| **low** | `OBS_PDB_STATUS` (unverified), inferred counts | Never sole basis for cuts |

Assign **Weight** on every `EVID_*` row.

## Unresolved contradictions

`contradiction_resolution: 0.6` in assessment formula. No cut `REC_*` in `READY` on affected dimensions.

## Contradiction resolution

| Signals | Resolution |
|---------|------------|
| `OBS_DERIVED_CPU_UTIL_AVG` vs `OBS_DERIVED_CPU_UTIL_P95` | Sizing follows `OBS_CPU_P95_FLEET` |

Reference `OBS_*` IDs in Contradictions table — no values.
