# Changelog — architecture-remediation-loop

All notable changes to the architecture-remediation-loop skill. Per-file `workflow_version` in
`workflow/*.md` frontmatter should match the version of the latest entry below that names that file.

## [1.1.1] — 2026-09-11

### Fixed
- Found via a second, fresh 5-persona adversarial pass re-verifying the 1.1.0 fix round:
- **High:** `reference/phase-index.md` and `reference/smoke-test.md`'s "zero candidates" rows still
  described the pre-fix Gate-A-before-Gate-B ordering; reworded to match `workflow/converge.md`'s actual
  merge-checkpoint → Gate B → Gate A order.
- **High:** a holistic-remediation batch (opened from a Gate B finding, not a Discover cycle) could reach
  `COMPLETED` and skip the merge checkpoint entirely, since Converge's § 1 only explicitly named "this
  cycle's" architecture-candidate batches. § 2 now states explicitly that a holistic-finding batch
  re-enters § 1 before Gate B is considered passed.
- **Medium:** dedup (`workflow/discover.md` § 4) and the new stall breaker both matched on scope + root
  cause *text* alone — vulnerable to codebase-architecture-review's own non-deterministic phrasing evading
  the match. Both now also match on evidence overlap (`evidence_refs`), and the stall breaker is defined as
  the same tracking dedup already does, not a second independent (and possibly divergent) mechanism.
- **Medium:** `reference/pr-batching-policy.md` § 6 (inter-batch dependencies) described recording a
  dependency "on both rows" with no ledger field to hold it. Added `depends_on_batch` to
  `reference/candidate-ledger.md`'s schema and wired it into `workflow/remediate.md`'s dispatch-eligibility
  check.
- **Medium (documented, not new machinery):** `AWAITING_MERGE` has no wait-budget circuit breaker — this is
  now stated explicitly as an intentional choice (mirroring loop-task-implementer's own unbounded
  `HUMAN_ACTION_REQUIRED`) rather than an unstated gap, since re-invoking while unmerged is cheap and a
  caller-side wait policy belongs at the invocation layer, not inside this skill.
- Clarified `cycles_run`'s initial value and increment timing (starts at 1 on Discover's first call; never
  advances during an `AWAITING_MERGE` pause).

## [1.1.0] — 2026-09-11

### Fixed
- **Merge checkpoint (Critical):** this skill never merges, so a fresh Discover pass without confirming
  the prior cycle's PRs actually landed would just rescan the unmerged base branch — and the old dedup
  rule would silently fold the still-unfixed finding into `DUPLICATE`, letting the loop report
  `converged: true` without anything having changed. `workflow/converge.md` § 1 now confirms every
  accepted batch's PR is merge-confirmed (reusing backlog-runner's own merge-vs-open-PR distinction)
  before Gate A/B run, pausing at `stopped_reason: AWAITING_MERGE` otherwise — an expected pause, not a
  failure, and idempotently resumable since merge state is re-derived from each PR's own status, never
  session memory.
- `workflow/discover.md` § 4: rediscovering a candidate against an already merge-confirmed row is no
  longer `DUPLICATE` (which would hide a regression) — it's a new row, `source: regression`.
- `reference/convergence-gates.md` § Gate B: `production-readiness-review`'s own `UNKNOWN` verdict is now
  handled explicitly (not silently treated as a pass or looped on forever) — two consecutive cycles with
  the same unresolved finding or `UNKNOWN` dimension trips a new `NO_MATERIAL_PROGRESS` circuit breaker.
- `reference/pr-batching-policy.md` § 6 (new): batches with an inter-batch dependency now sequence instead
  of dispatching in parallel against code the dependency batch hasn't landed yet.
- `workflow/remediate.md`: module-design's required `module_scope`/`change_goal`/`repository_evidence`
  inputs are now explicitly mapped from the candidate row; batch retry is now tracked
  (`batch_attempt_count`) instead of only asserted in prose.
- Untrusted-content guard restated at each of the four downstream ingest phases (Discover, Disposition,
  Remediate, Converge), per this repo's own normative rule, not only once in `SKILL.md`.
- `capabilities.required` now correctly includes `codebase-architecture-review.invoke` and
  `production-readiness-review.invoke` (both invoked unconditionally every cycle) — previously misclassified
  `optional`.
- `docs/skill-framework/shared/cross-skill-escalation.md`'s → production-readiness-review row now names
  `assessment_context` (the actual consumed artifact), not `assessment_target` (one of its nested fields).
- `evals/negative/cases.yaml`'s case replaced — the prior prompt shared no words with this skill's own
  routing patterns and was never actually at risk of misrouting; the new one is a genuine near-miss
  (contains "architecture" and loop-task-implementer's own trigger words) verified against the dispatcher.
- `reference/report-format.md`: added the `stopped_reason` values above, `merge_attempted` (asserted
  `false` invariant, resolving a golden fixture assertion that previously had no schema definition), and
  per-batch `merged`/`pull_request_merge_sha`.
- Found via a 5-persona adversarial review (correctness/consistency, architecture, security/guardrails,
  adversarial break-it, registry/ops) — see the review's findings for full detail; two claimed anchor
  breakages (README.md, pressure-tests.md) were investigated and found to be false positives against this
  repo's actual GitHub-slug algorithm (`scripts/validate_references.py:github_style_slug`).

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
