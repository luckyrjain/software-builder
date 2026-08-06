# Changelog — cost-optimization-sprint-planner

All notable changes to the cost-optimization-sprint-planner skill. Per-file `workflow_version` in
`workflow/*.md` frontmatter should match the version of the latest entry below that names that file.

## [1.0.0] — 2026-08-05

### Added
- Initial skill release — org-wide sweep wrapper around k8s-overprovisioning-datadog, implementing
  [org-rollup-schema.md](../docs/skill-framework/shared/org-rollup-schema.md)'s `k8s_waste` adapter
  (already fully specified in Phase 4, before this skill existed)
- `workflow/inputs.md` — `sweep_scope` (explicit deployment list or namespace pre-filter config) +
  `cost_rate` (no default — an operational policy decision) + `max_deployments_per_run`/`deadline`/
  `session_token_budget` parsing, HARD STOP on missing required fields
- `workflow/run-sweep.md` — optional namespace/deployment waste-ranking pre-filter (Datadog MCP queries
  run directly, reusing k8s-overprovisioning-datadog's own Phase 0b query definitions rather than
  delegating to a standalone-ranking mode that skill doesn't document), sequential per-deployment sweep
  loop, join, rank, render
- `reference/gate-policy.md` — every live k8s-overprovisioning-datadog gate (ambiguous service/tag
  confirmation, insufficient-metrics/name-mismatch, VPA-active-unconfirmed, cost-rate confirmation,
  CCM-empty fallback, manifest-lookup-not-found) with a scripted answer reused from k8s's own documented
  fallback — the cost-rate gate is the one genuinely new resolution: asked once, sweep-wide, before the
  loop starts, never re-derived per deployment
- `reference/sweep-policy.md` — the sweep loop's own session-level state, candidate-list construction,
  per-deployment failure isolation, and batch-level stop conditions, modeled directly on
  [backlog-runner/reference/queue-policy.md](../backlog-runner/reference/queue-policy.md) — **not**
  loop-task-implementer's own orchestrator, which works exactly one task at a time and has no
  multi-item batch loop of its own (a fabrication risk caught during design research and corrected before
  this skill was built, not after)
- No `disable-model-invocation` — ambiently invocable, like release-readiness-checker; a human is present
  for this flow but a gate-policy file is still needed because the fan-out over potentially many
  deployments would otherwise interrupt once per deployment
- No scripts of its own — k8s-overprovisioning-datadog has no CLI to wrap (unlike mysql-to-postgres-sql,
  which migration-program-manager wraps via a real Python script); this skill is pure markdown-workflow,
  like release-readiness-checker
- Shared framework compliance (confidence-bands, cross-skill-escalation, prompt-injection, skill-routing,
  phase-glossary)
- Design spec: [docs/superpowers/specs/2026-08-05-cost-optimization-sprint-planner-design.md](../docs/superpowers/specs/2026-08-05-cost-optimization-sprint-planner-design.md)
  — corrects two claims in the roadmap item's own wording that didn't match the actual code (the
  loop-task-implementer modeling claim above, and Phase 0b's namespace ranking not actually being
  documented as a standalone report-only mode) before designing against them
