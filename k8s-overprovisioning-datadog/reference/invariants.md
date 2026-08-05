# Graph invariants (self-validating)

Run after [build-graph.md](../workflow/build-graph.md), before [render.md](../workflow/render.md).

**Critical violations** → populate `invariant_violations[]` on the graph; emit graph + violations only (no polished markdown).

| ID | Invariant | Severity |
|----|-----------|----------|
| **INV-01** | Every `REC_*` has ≥1 `DEC_*` in `depends_on.decisions` | critical |
| **INV-02** | Every `DEC_*` has ≥1 `OBS_*` in `supports` | critical |
| **INV-03** | Every `OBS_*` has exactly one `EVID_*` with matching `observation_id` | critical |
| **INV-04** | Every `EVID_*` has non-empty `source` unless `quality: missing` | critical |
| **INV-05** | No `value` fields on `decisions[]`, `recommendations[]`, or `evidence[]` | warning |
| **INV-06** | All IDs use correct prefix (`OBS_`, `EVID_`, `DEC_`, `REC_`, `ASSUME_`) | critical |
| **INV-07** | `assessment.assessment_confidence.value` equals weighted sum of `factors` (1 decimal) | critical |
| **INV-08** | No `REC_*` with `status: READY` when any `depends_on.decisions` is `BLOCKED` | critical |
| **INV-09** | Unresolved `contradictions[]` → no cut `REC_*` (`REC_CPU_REDUCE`, `REC_REPLICA_REDUCE`, `REC_MEMORY_REDUCE`) in `READY` | critical |
| **INV-10** | Every ID in `supports`, `blocking`, `missing`, `depends_on` references an existing graph node | critical |
| **INV-11** | Each `RECOMMENDATION_CONFIDENCE.value` matches its `factors` arithmetic (±0.1 after caps) | critical |
| **INV-12** | Every `REC_*` with `status: READY` and actionable change id (`*_REDUCE`, `*_INCREASE`, `*_ADJUST`, `REC_MANIFEST_RECONCILE`) has non-empty `delivery_pointer.path` | critical |
| **INV-13** | Every `ASSUME_*` ID in any `depends_on.assumptions` array references an existing entry in `assumptions[]` | critical |

## Validation output

On success: proceed to `RENDER`.

On failure:

```yaml
invariant_violations:
  - id: INV-03
    message: OBS_CPU_THROTTLE_RATE has no matching EVID_*
    nodes: [OBS_CPU_THROTTLE_RATE]
```

## Checklist (agent)

See [validate-invariants.md](../workflow/validate-invariants.md).
