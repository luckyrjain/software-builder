---
workflow_version: 1.3
phase: 3
produces:
  - core_domain_deep_dive
  - implementation_matrix
  - data_ownership_refined
  - draft_five_questions
  - overall_confidence
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
| Draft five questions | `EXEC_SUMMARY.md` | Updated through P3 — all five present | Phase incomplete |
| Overall confidence | `EXEC_SUMMARY.md` + `manifest.overall_confidence` | Per confidence-rubric.md | Phase incomplete |

## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md)
