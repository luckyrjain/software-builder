---
workflow_version: 1.2
phase: 1-2-coverage
produces:
  change_identity: object
  inspection_plan: object
  initial_unable_to_inspect: list
consumes:
  required:
    review_boundary: object
    capability_profile: object
    jira_ac_table: list
    head_sha: string
  optional:
    review_target: object
    context_cache: object
  conditional: {}
---

# Phase 1 → 2 coverage planning

Run immediately after Phase 1 and before Phase 2 for every non-listing review. This step is read-only.

Load `../reference/review-coverage-contract.yaml` and
`../reference/review-coverage-execution.md` §Phase 1→2 coverage.

Build the current shared `change_identity` from the normalized provider/Git state and canonical effective patch.
Do not invent a base SHA, merge-base SHA, generated path, dependency/config delta, or fingerprint. If a required
identity field cannot be established, stop before Phase 2 and report the unavailable identity rather than
substituting a placeholder.

Build the six-surface `inspection_plan` with exact entries
`{triggered, reason, mandatory, evidence_sources, status}`. Trigger and scope cross-file impact, hidden consumers,
schema/migration compatibility, rollout/rollback, test quality, and dependency/config/IaC according to the
canonical coverage contract. A triggered surface starts `pending`; an untriggered surface is `not_applicable`.

When an evidence capability required for a triggered surface is already known unavailable, append
`{surface, reason, mandatory}` to `initial_unable_to_inspect`; do not silently mark the surface clean.

Before continuing, validate the shared change identity using the packaged
`docs/skill-framework/shared/review_contract_runtime.py` → `validate_change_identity(...)`. This is the same
portable runtime used by Phase 2 evidence and is available in both source and installed skill layouts. It is the only
implementation: root `scripts/validate_review_contracts.py` loads this same module rather than re-implementing it, so
there is nothing to drift. The live installed workflow must not depend on that repository-root script.
Invalid identity blocks Phase 2.

Pass `change_identity`, `inspection_plan`, and `initial_unable_to_inspect` forward to Phase 2 and the mandatory
Phase 2 coverage-review subphase.
