---
workflow_version: 3.0
phase: normalize-evidence
produces:
  - observation_registry
  - evidence_registry
  - assessment_fingerprint
consumes:
  - raw_metrics
  - metrics_queried_count
  - query_references
  - manifest_bytes
  - threshold_hash
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

## Example

**Graph (internal):**

**Observations:** `OBS_CPU_P95_FLEET = 0.90 cores`

**Evidence:** `EVID_CPU_P95_FLEET` → Datadog · `kubernetes.pod.cpu.usage.dist` · p95.dist · …

**Decision:** `DEC_CPU_REQUEST` BLOCKED — `Reasons: ✓ OBS_CPU_P95_FLEET` — no value repeated.

**Human Report (rendered):**

> Fleet CPU p95 is 0.90 cores (90% of the 1-core request). **CPU requests:** keep unchanged — fleet p95 exceeds the trim threshold.
