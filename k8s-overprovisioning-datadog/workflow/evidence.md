---
workflow_version: 3.5
phase: normalize-evidence
produces:
  observation_registry: object
  evidence_registry: object
  evidence_ids: list
  assessment_fingerprint: string
consumes:
  required:
    raw_metrics: object
    source_profile: object
    metrics_queried_count: string
    query_references: list
    manifest_bytes: content
    threshold_hash: string
  optional: {}
  conditional: {}
---

# Evidence model

Assign **`OBS_*`** during NORMALIZE. Evidence rows **`EVID_*`** link to `OBS_*`.

Namespaces: [reference/id-namespaces.md](../reference/id-namespaces.md).

## DRY (graph and appendix)

Values in `observations[]` only. `evidence[]` has provenance only. Appendix sections reference IDs.

## Human Report display

The **Evidence Registry** (`OBS_*` / `EVID_*` tables) is **appendix-only**. The Human Report Evidence section uses **human labels + values**, sorted by importance — see [workflow/report.md](report.md#human-first-rules) and [templates/human-report.md](../templates/human-report.md).

Build and link with IDs; translate at render time.

## Fingerprint

Include `threshold_hash`, `manifest_hash`, `metric_query_hash` in the graph — render to **Assessment Metadata** appendix only ([templates/metadata.md](../templates/metadata.md)).
Carry `source_profile` unchanged for BUILD_GRAPH; NORMALIZE may append source failures observed during
queries but must not rewrite successful route selections without recording the reason.

## Example

**Graph (internal):**

**Observations:** `OBS_CPU_P95_FLEET = 0.90 cores`

**Evidence:** `EVID_CPU_P95_FLEET` → `<selected source>` · `<metric/query>` · p95 · 7d · …

Every evidence row records the actual source selected for that capability. When Kubernetes MCP and
Datadog both supply the signal, keep the routed value on the canonical ID and create an
`_ALT_<SOURCE>` observation/evidence pair for the other value per
[observation-ids.md](../reference/observation-ids.md). This preserves INV-03's one-to-one provenance;
never overwrite one source or attach two evidence rows to one observation.

**Decision:** `DEC_CPU_REQUEST` BLOCKED — `Reasons: ✓ OBS_CPU_P95_FLEET` — no value repeated.

**Human Report (rendered):**

> Fleet CPU p95 is 0.90 cores (90% of the 1-core request). **CPU requests:** keep unchanged — fleet p95 exceeds the trim threshold.
