# Skill contract — non-negotiable

Load immediately after [SKILL.md](../SKILL.md). These rules override convenience shortcuts. Shared
rules across the whole test-creator family live in
[test-creation-principles.md](../../docs/skill-framework/shared/test-creation-principles.md) — this file
states only what's different for **unit** scope; it does not restate the shared rules.

## Contract

1. **Scope** — write or modify test files only. Refactor limits (when a testability refactor is allowed
   at all) are shared, see
   [test-creation-principles.md §3](../../docs/skill-framework/shared/test-creation-principles.md#3-refactor-limits).
2. **Isolation is the whole point** — every external dependency (network, real database, filesystem I/O
   unless the filesystem itself is the unit under test, wall-clock time, randomness) must be mocked or
   stubbed. A target that cannot be isolated with an existing mocking convention in the repo is out of
   scope for this skill, not a reason to reach for a real dependency — see
   [reference/test-quality-deltas.md](test-quality-deltas.md) and
   [gate-policy.md §5](gate-policy.md#5-target-cant-be-isolated-from-a-real-dependency).
3. **Detect before writing** — always run [workflow/detect-conventions.md](../workflow/detect-conventions.md)
   first. Never introduce a second test framework alongside one the repo already uses, and never invent a
   framework for a repo with none, without asking.
4. **Real assertions only, shared quality bar** — every test must satisfy the shared checklist in
   [test-creation-principles.md §2](../../docs/skill-framework/shared/test-creation-principles.md#2-test-quality-rules)
   plus the unit-specific deltas in [test-quality-deltas.md](test-quality-deltas.md).
5. **Gate, don't guess** — HARD STOP / ask per [reference/gate-policy.md](gate-policy.md) rather than
   guessing a framework, fabricating a mock for infra that isn't reachable, or inventing test data that
   contradicts the code's real contract.
6. **Verify before claiming** — never report a test as passing without having run it in this session. When
   `run_tests: false` or no execution capability exists, mark every target `UNVERIFIED` explicitly.
7. **No silent caps** — `max_files_per_run` or `deadline` overflow is always listed in the report by name,
   never dropped quietly.
8. **Never hide a failure** — no `.skip` / `xfail` / `@Disabled` / deleted assertion to force a suite
   green without flagging it in `UNIT_TEST_REPORT.md`.
9. **Never patch production code to force a test green** — a failure that traces to production code is a
   finding to report and hand off, per
   [test-creation-principles.md §5](../../docs/skill-framework/shared/test-creation-principles.md#5-escalation-on-a-surfaced-production-bug).
10. **Deliverable** — emit [UNIT_TEST_REPORT.md](report-format.md) every run, even for a single-file
    backfill with one target.
11. **Lazy-load** — only the reference file(s) named for the current phase in
    [lazy-load-index.md](lazy-load-index.md); do not bulk-read all of `reference/`.

Routing: [skill-routing.md](../../docs/skill-framework/shared/skill-routing.md).
