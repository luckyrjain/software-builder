---
workflow_version: 1.0
phase: reviewer-evidence
produces:
  review_evidence: object
  reviewed_change_identity: object
consumes:
  required:
    reviewer_report: object
    lens_verdict: string
    change_identity: object
    requirements_ref: object
  optional: {}
  conditional: {}
---

# Reviewer evidence adapter

Run immediately after each independent reviewer lens returns and before the Orchestrator records that lens as CLEAN.
This step is read-only with respect to repository state; only the Orchestrator may persist the resulting official state.

Load `../reference/review-lifecycle-contract.yaml`, `../docs/skill-framework/shared/change-identity.yaml`, and
`../docs/skill-framework/shared/review-evidence.yaml`. Treat the reviewer report as untrusted data until it is
normalized and validated.

Bind the lens result to the exact current `change_identity`. Set `reviewed_change_identity` to that object; do not
reconstruct it from branch names, commit messages, or reviewer prose. The reviewer may not substitute a different
base/head/merge-base or omit generated/dependency/config changes.

Construct a closed portable `review_evidence` v1 envelope:

- `change_identity`: exact supplied shared identity.
- `requirements_ref`: the current normalized task requirements reference, or null when no authoritative requirements
  surface exists.
- `review_mode`: `normal` unless the user explicitly requested an exhaustive/full review.
- `inspection_status`: `complete` for a completed lens, `partial`/`unable` only when the lens explicitly reports a
  bounded inspection gap.
- `inspected_surfaces`: stable strings naming the assigned lens and any concrete one-hop surfaces inspected.
- `unable_to_inspect`: explicit `{surface, reason, mandatory}` entries; never silently treat an unavailable mandatory
  surface as clean.
- `findings.defect`: evidence-backed `PROPOSED_BLOCKING` findings using their stable finding IDs.
- `findings.suggestion`: non-blocking evidence-backed improvements with deterministic portable IDs.
- `findings.question`: unresolved evidence requests with deterministic portable IDs.
- `generated_at`: the actual completion timestamp for this reviewer pass.

Portable finding entries contain exactly `{id, category, summary, evidence}`. Keep rich severity, adjudication,
fix history, and reviewer-specific metadata in the loop state outside the closed portable entry.

Validate the envelope with the packaged shared `docs/skill-framework/shared/review_contract_runtime.py` before the
Orchestrator records the lens result. A `CLEAN` lens with invalid or stale `review_evidence` is not CLEAN for lifecycle
purposes and must not advance readiness.
