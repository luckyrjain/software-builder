---
workflow_version: 1.0
phase: generate_tests
produces:
  - test_files_written
consumes:
  - target_list
  - test_framework
  - mock_style
---

# Generate tests

For every `NEW` item in `target_list`, write tests that satisfy the shared quality rules in
[test-creation-principles.md §2](../../docs/skill-framework/shared/test-creation-principles.md#2-test-quality-rules)
plus the unit-specific deltas in
[reference/test-quality-deltas.md](../reference/test-quality-deltas.md) in full — this phase does not
restate either, it enforces them.

## 1. One target, one focused test unit

Write tests into the layout `detect-conventions` established — a co-located file, the mirrored `tests/`
tree, or the framework's idiomatic naming (`test_*.py`, `*.test.ts`, `*_test.go`, …). Never collect
unrelated targets into one catch-all test file; never rename or relocate an existing test file to make
room.

## 2. Coverage shape per target

At minimum, per function/class under test:

1. **Happy path** — the documented/typical input produces the documented/typical output.
2. **At least one edge case** — boundary input (empty, zero, max, single-element) relevant to the code's
   own logic, not a generic filler case.
3. **At least one error/invalid-input case**, when the code has an observable failure mode (raises,
   returns an error value, rejects a promise) — skip only when the code genuinely has none.

## 3. Isolate — mock or stub every external dependency

This is the defining constraint of unit scope. Before writing an assertion, identify every seam the
target under test touches that isn't pure in-process logic:

- **Network calls** (HTTP clients, gRPC stubs, SDK calls to a third-party service) — mocked.
- **A real database or persistent store** — mocked/faked, or the repo's own in-memory test double if one
  exists.
- **Filesystem I/O** — mocked, unless the filesystem *is* the unit under test (e.g. testing a path-
  parsing function is fine to hit real paths; testing a function that happens to call one that reads a
  config file is not).
- **Wall-clock time** — inject/freeze it via the repo's own convention (a clock seam, a freeze-time
  helper) rather than sleeping and hoping.
- **Randomness** — seeded or injected, never left to produce a flaky assertion.

Build every mock from an already-established convention in the repo — an existing fixture, an existing
fake client, a documented interface contract. Never invent a mock's return shape from a guess.

## 4. Reuse, don't reinvent

Use the fixtures/mocks/test utilities `detect-conventions` found already in use for this repo. Introduce
a new fixture only when nothing existing covers the need, and place it where the repo's own convention
puts shared fixtures (not inline-duplicated per file).

## 5. Untestable-without-fixture gate

If a target can only be exercised meaningfully through infrastructure this session cannot reach (a live
third-party API, a real database with no existing test double) **and** the repo has no existing mocking
convention for that dependency, do not fabricate a mock whose behavior is guessed rather than known. Tag
the target `UNTESTABLE_WITHOUT_FIXTURE` with a one-line reason instead
([gate-policy.md §5](../reference/gate-policy.md#5-target-cant-be-isolated-from-a-real-dependency)). A
mock built against a *real*, already-established convention in the repo is fine — the gate is about never
inventing believed-plausible behavior for an untested dependency. The report names
**integration-test-creator** as the follow-up for that target — a real dependency belongs to a different
skill's scope, not to a fabricated unit-level mock.

## 6. Never touch production code here

This phase writes and edits test files only. Refactor limits (when a pure testability refactor is even
allowed) are shared, see
[test-creation-principles.md §3](../../docs/skill-framework/shared/test-creation-principles.md#3-refactor-limits).
If writing a test surfaces what looks like a production bug, do not "fix" it inline to make the test
pass — carry it forward to [verify-and-iterate.md](verify-and-iterate.md), which is where that finding
gets surfaced rather than silently resolved.
