# ID namespaces (globally stable)

Primary artifact: typed `decision_graph` ([decision-graph-schema.md](decision-graph-schema.md)).
**Never** use `E1`, `R1`, or unprefixed slugs.

Build: [build-graph.md](../workflow/build-graph.md). Render: [render/README.md](../render/README.md).

| Prefix | Object | Example | Registry |
|--------|--------|---------|----------|
| `OBS_` | Observation value | `OBS_CPU_USAGE_AVG` | [observation-ids.md](observation-ids.md) |
| `EVID_` | Evidence provenance row | `EVID_CPU_USAGE_AVG` | links to `OBS_*` |
| `DEC_` | Decision object | `DEC_CPU_REQUEST` | [decision-ids.md](decision-ids.md) |
| `REC_` | Recommendation | `REC_CPU_KEEP` | [recommendation-ids.md](recommendation-ids.md) |
| `ASSUME_` | Assumption | `ASSUME_HPA_INTENTIONAL` | [templates/assumptions.md](../templates/assumptions.md) |

Derived observations: `OBS_DERIVED_CPU_UTIL_P95` (or `OBS_CPU_UTIL_P95`).

New signals **append** to registries — never renumber.

## DRY rule

After `observations[]` and `evidence[]`, **reference IDs only** in the graph and Technical Appendix — do not repeat values in
`decisions[]`, `recommendations[]`, `why_this_matters[]`, or `contradictions[]`.

The **Human Report** repeats values with human labels and never exposes registry IDs ([workflow/report.md](../workflow/report.md)).

```
Observation (value) → Evidence (provenance) → reference by ID everywhere else
```
