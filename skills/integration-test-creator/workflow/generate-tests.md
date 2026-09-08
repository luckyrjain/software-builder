---
workflow_version: 1.1
phase: generate_tests
produces:
  - test_files_written
consumes:
  - target_list
  - test_framework
  - orchestration
  - mock_style
---

# Generate tests

Follow the shared [test-creator common workflow](../../docs/skill-framework/shared/test-creator-common-workflow.md)
and run the [test-creator write-safety contract](../../docs/skill-framework/shared/test-creator-write-safety.md)
before any test file, report, or coverage-state write. The integration-specific rules below are deltas only.

For every `NEW` item in `target_list`, write tests that satisfy the shared
[test-creation-principles.md §2](../../docs/skill-framework/shared/test-creation-principles.md#2-test-quality-rules)
in full, **plus** the integration-specific deltas in
[reference/test-quality-deltas.md](../reference/test-quality-deltas.md) — this phase does not restate
either, it enforces them.

## 1. One seam, one focused test unit

Write tests into the layout `detect-conventions` established — a `tests/integration/`/`test/integration/`
tree, `*IT.java` naming with Failsafe, or `*.integration.test.ts` co-located files. Never collect
unrelated seams into one catch-all test file; never rename or relocate an existing test file to make room.

## 2. Coverage shape per target

At minimum, per seam under test, exercised against the **real** dependency:

1. **Happy path** — the documented/typical call against the real dependency produces the documented/
   typical result (a row actually persisted and re-read, a message actually consumed, a cache entry
   actually round-tripped).
2. **At least one edge case** — a boundary condition the real dependency itself can produce (a unique-
   constraint conflict, an empty result set, a queue with zero messages), not a generic filler case.
3. **At least one error/invalid-input case**, when the seam has an observable failure mode against the
   real dependency (a connection drop, a constraint violation, a timeout) — skip only when the code
   genuinely has none.

## 3. Never mock the dependency under test

This is the one rule that distinguishes this skill from unit-test-creator, and it is absolute: the
component under test always talks to a **real** instance of its adjacent dependency — spun up via
testcontainers, docker-compose, or the repo's own embedded convention, per `orchestration`. Auxiliary test
data setup (seeding fixtures, an unrelated third dependency the seam doesn't touch) may reuse the repo's
existing `mock_style` conventions; the seam itself never may. See
[test-quality-deltas.md](../reference/test-quality-deltas.md) for the anti-pattern this guards against.

## 4. Reuse, don't reinvent

Use the fixtures/testcontainers setup/docker-compose service definitions `detect-conventions` found
already in use for this repo. Introduce new container/compose wiring only when nothing existing covers the
need, and place it where the repo's own convention puts shared test infrastructure (not inline-duplicated
per file).

## 5. `NEEDS_INTEGRATION_ENV` gate

If `orchestration` is `none` and this session has no other way to stand up the real dependency (no
reachable Docker daemon, no embedded-DB convention already in the repo), still write the test against the
real dependency's real interface — do not fabricate the dependency or quietly mock it — but tag the target
`NEEDS_INTEGRATION_ENV` for Verify & iterate to carry forward unrun
([gate-policy.md §5](../reference/gate-policy.md#5-zero-orchestration-mechanism-detected)). This is
distinct from `UNTESTABLE_WITHOUT_FIXTURE`-style gates in sibling skills — the test is genuinely written
and correct, it simply cannot be executed without infrastructure this session lacks.

## 6. Never touch production code here

This phase writes and edits test files only. If writing a test surfaces what looks like a production
bug, do not "fix" it inline to make the test pass — carry it forward to
[verify-and-iterate.md](verify-and-iterate.md), which is where that finding gets surfaced rather than
silently resolved.
