# Skill contract — non-negotiable

Load immediately after [SKILL.md](../SKILL.md). These rules override convenience shortcuts.

Shared rules for every skill in the test-creation family — test-first evidence, test-quality rules,
refactor limits, the shared report skeleton, and the production-bug escalation — live in
[test-creation-principles.md](../../docs/skill-framework/shared/test-creation-principles.md) and are
**normative here by reference**, not restated. This file states only what's different for the
integration level.

## Integration-level deltas

1. **Never mock the seam under test.** The one rule that makes this skill exist as its own skill: every
   test writes against a **real** instance of the adjacent dependency (via testcontainers,
   docker-compose, or an embedded convention already in the repo). A target fully testable by mocking
   everything belongs to **unit-test-creator** — escalate, don't write a mocked "integration" test (see
   [test-quality-deltas.md](test-quality-deltas.md)).
2. **Detect two dimensions before writing** — always run
   [workflow/detect-conventions.md](../workflow/detect-conventions.md) first: the base test runner *and*
   the real-dependency orchestration mechanism. Never introduce a second base framework or orchestration
   mechanism alongside one the repo already uses, and never invent either for a repo with none, without
   asking.
3. **No orchestration ≠ mock the dependency.** When no orchestration mechanism is detected and this
   session cannot stand one up, tag the target `NEEDS_INTEGRATION_ENV`
   ([gate-policy.md §5](gate-policy.md#5-zero-orchestration-mechanism-detected)) — never fabricate a fake
   dependency and never silently fall back to mocking it, which would secretly turn the test into a unit
   test without saying so.
4. **Lazy-load** — only the reference file(s) named for the current phase in
   [lazy-load-index.md](lazy-load-index.md); do not bulk-read all of `reference/`.

Everything else — real assertions only, gate-don't-guess, verify-before-claiming, no silent caps, never
hide a failure, the `INTEGRATION_TEST_REPORT.md` deliverable every run — is exactly the shared contract
in [test-creation-principles.md](../../docs/skill-framework/shared/test-creation-principles.md).

Routing: [skill-routing.md](../../docs/skill-framework/shared/skill-routing.md).
