# Evidence schema (v3.0 — graph objects)

Namespaces: [id-namespaces.md](id-namespaces.md). **DRY rule:** values only in `Observations`.

## Layers

| Layer | Prefix | Section | Contains |
|-------|--------|---------|----------|
| Observation | `OBS_` | `Observations` | ID + value |
| Evidence | `EVID_` | `Evidence` | Provenance for `OBS_*` (no value) |
| Decision | `DEC_` | `DecisionObjects` | Status + Reasons + Explanation |
| Recommendation | `REC_` | `Recommendations` | State + deps (reference IDs only) |

```
OBS_* (value) → EVID_* (provenance) → reference by ID in DEC_* / REC_* / Contradictions / WhyThisMatters
```

## Observation (`OBS_*`)

| Field | Required |
|-------|----------|
| ID | `OBS_*` from [observation-ids.md](observation-ids.md) |
| Value | number + unit, or state row |

## Evidence (`EVID_*`)

| Field | Required |
|-------|----------|
| EVID_ID | `EVID_<suffix>` matching `OBS_*` |
| OBS_ID | link |
| Source, Metric, Aggregation, Window, Scope, Quality, Weight | yes |

No confidence column on evidence — confidence is computed at assessment/recommendation level.

## Decision rationale (structured)

```text
Reasons: ✓ OBS_CPU_P95_FLEET ✓ OBS_KAFKA_LAG_MAX ✓ ASSUME_HPA_INTENTIONAL
Explanation: <one sentence>
```

## Confidence (separate scores)

- `ASSESSMENT_CONFIDENCE` — [confidence-formula.md](confidence-formula.md)
- `RECOMMENDATION_CONFIDENCE` — per `REC_*`, same doc, different weights

Never conflate the two.

Schema: [report-schema.md](report-schema.md)
