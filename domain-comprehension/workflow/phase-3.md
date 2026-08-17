---
workflow_version: 1.4
phase: 3
produces:
  - core_domain_deep_dive
  - implementation_matrix
  - data_ownership_refined
  - draft_five_questions
  - overall_confidence
  - data_ownership_graph_refined
  - capability_traceability_refined
consumes:
  - bounded_contexts
  - data_ownership
  - business_flows
  - state_machine
  - runtime_validation_table
---

# Comprehension Phase P3 — Core domain section

Synthesize bounded contexts, data flows, and architectural non-negotiables into a core domain snapshot.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Core domain section | `{map_file}` § `core_section` | Idempotency, routing, failure, retry, concurrency, PII | Phase incomplete |
| Implementation matrix | `EXEC_SUMMARY.md` | implementation + exercise axes per [implementation-status.md](../reference/implementation-status.md) | Phase incomplete |
| Data ownership (refined) | `DATA_OWNERSHIP.md` | Complete entity table | Phase incomplete |
| Machine data ownership (refined) | `DATA_OWNERSHIP_GRAPH.yaml` | authoritative writer/source + replicas/caches/indexes/consumers reconciled | Phase incomplete in FULL mode |
| Capability traceability (refined) | `CAPABILITY_TRACEABILITY.yaml` | material capabilities mapped to all evidenced code locations | Phase incomplete in FULL mode |
| Draft five questions | `EXEC_SUMMARY.md` | Updated through P3 — all five present | Phase incomplete |
| Overall confidence | `EXEC_SUMMARY.md` + `manifest.overall_confidence` | Per confidence-rubric.md | Phase incomplete |

## Machine-domain projection (required in FULL mode)

Reconcile the P1 machine artifacts against this phase's completed `DATA_OWNERSHIP.md` entity table and core
domain deep dive per [machine-domain-model.md](../reference/machine-domain-model.md):

- **`DATA_OWNERSHIP_GRAPH.yaml`** ([§ Data ownership projection](../reference/machine-domain-model.md#data-ownership-projection)) — every entity in the refined `DATA_OWNERSHIP.md` table gets its authoritative writer, replicas, caches, and indexes reflected as nodes/edges; multiple evidenced writers stay visible and feed the Multiple writers smell rather than being resolved to one owner.
- **`CAPABILITY_TRACEABILITY.yaml`** ([§ Capability-to-code projection](../reference/machine-domain-model.md#capability-to-code-projection)) — extend the P1 initial pass with any capability, code location, or owner refined during this phase's core domain deep dive.

## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md)
