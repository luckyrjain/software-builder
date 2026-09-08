# Changelog — production-readiness-review

All notable changes to the production-readiness-review skill. Per-file `workflow_version` in
`workflow/*.md` frontmatter should match the version of the latest entry below that names that file.

## [1.0.0] — 2026-08-27

### Added
- Initial skill release — read-only orchestrator composing pr-review, change-impact-analyzer,
  deployment-risk-review, security-review, observability-review, resilience-review,
  api-design-review, database-review, performance-review, capacity-planner, and
  dependency-upgrade-review into one production-readiness verdict for a single PR/MR/
  release-candidate.
- `workflow/inputs.md` — `assessment_target` (mr_context or direct `source_revision`) and
  `criticality` resolution, HARD STOP on missing/empty target
- `workflow/collect-evidence.md` — CI status, SCM policy, build provenance, and refreshed/reused
  change-impact and deployment-risk evidence collection
- `workflow/dispatch.md` — pr-review always invoked retrospectively with posting forbidden; every
  applicable specialist dispatched per its own mandatory-input contract, never with a
  knowingly-incomplete mandatory input
- `workflow/aggregate.md` — evidence-authority ladder and operational-gate application, worst-first
  verdict derivation
- `workflow/report.md` — `production_readiness_report` emission with the safe rendered-output
  boundary applied to every untrusted field
- `reference/gate-policy.md` — normative gate answers: pr-review posting always held/forbidden, no
  child ever receives merge/deploy/rollback authority, no dispatch on a knowingly-incomplete mandatory
  input, an embedded child's interactive question surfaces as `BLOCKED` rather than a live prompt
  mid-aggregation
- `reference/evidence-authority-policy.md` — the evidence-authority ladder (`caller`,
  `model_knowledge` < `repository`, `authoritative_host`, `trusted_runtime`) and the no-laundering
  rule: a trusted child producer can never turn caller/model-knowledge-only evidence into `PASS`
- `reference/operational-gates.md` — the four operational dimensions (ownership, rollback/abort,
  post-deploy verification plan, recovery) and their tier-sensitive PASS/CONDITIONAL/FAIL/UNKNOWN
  rules
- `reference/child-input-map.md` — per-child mandatory-input table matching each specialist's own
  documented HARD STOP fields
- `reference/report-format.md` — normative `production_readiness_report` structure, verdict
  precedence, and safe rendered-output boundary (escape/fence untrusted text, redact secrets/PII)
- No `disable-model-invocation` — ambiently invocable, like `release-readiness-checker`
- Shared framework compliance (confidence-bands, cross-skill-escalation, prompt-injection,
  skill-routing, runtime-contract)
