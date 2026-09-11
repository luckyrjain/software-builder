# Changelog — architecture-remediation-loop

All notable changes to the architecture-remediation-loop skill. Per-file `workflow_version` in
`workflow/*.md` frontmatter should match the version of the latest entry below that names that file.

## [1.0.0] — 2026-09-11

### Added
- Initial skill release — an autonomous whole-codebase architecture remediation loop composed entirely
  from existing skills, requested explicitly as a replacement for an external "Matt" architecture-review
  tool: **codebase-architecture-review** is the sole discovery engine.
- No new review, grilling, design, implementation, or PR logic of its own — composes
  codebase-architecture-review (discover), engineering-decision-discovery (grill/disposition),
  module-design (design, when needed), loop-task-implementer (implement/test/review/commit/push/PR), and
  production-readiness-review (the holistic gate) each cycle.
- `reference/candidate-ledger.md` — the one genuinely new schema: a session-level candidate ledger with a
  six-way terminal disposition contract (ACCEPT / ACCEPT WITH MODIFICATION / ALREADY SATISFIED / DUPLICATE
  / REJECT / OUT OF SCOPE), extending each composed skill's own artifact without modifying it.
- `reference/pr-batching-policy.md` — the other genuinely new logic: dedicated-PR-vs-grouped-batch rules so
  large/high-risk candidates never share a PR with unrelated small cleanups, and small cohesive candidates
  don't each demand their own review cycle.
- `reference/convergence-gates.md` — Gate A (fresh codebase-architecture-review) and Gate B (fresh
  production-readiness-review) must both pass in the same cycle; explicit anti-gaming rules against
  reaching zero by narrowing scope, reclassifying real findings, or skipping grilling.
- `autonomous_merge_authorized` has no input path in this skill at all — hardcoded never-`true`, same
  precedent as backlog-runner.
- Shared framework compliance (cross-skill-escalation, prompt-injection, safe-output, skill-routing).
