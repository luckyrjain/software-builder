# integration-test-creator

**Writes real, running integration tests** for a target repository — tests that exercise the seam between
a component and one real adjacent dependency (a database, queue, cache, or another internal service),
never a mock standing in for that dependency. Detects the repo's base test runner and its real-dependency
orchestration mechanism first, then generates tests that match both, runs them, and iterates on failures.
Two entry modes: **diff** (test what just changed in an MR/branch/working tree) and **backfill** (test an
existing coverage gap you point it at).

No MCP, no other skill required to run standalone — pure repository read/write plus the ability to
execute the target repo's own test command and (optionally) stand up a real dependency via testcontainers
or docker-compose.

## What it does

1. **Detects conventions** — two dimensions: the base test runner (pytest, Jest/Vitest/Mocha, Go
   `testing`, JUnit via Maven/Gradle, RSpec/Minitest, xUnit/NUnit/MSTest, `cargo test`) and the
   real-dependency orchestration mechanism (testcontainers, docker-compose, an embedded/in-memory DB
   convention), plus any integration-test naming/tag convention already in use (`tests/integration/`, a
   pytest `integration` marker, JUnit `@Tag("integration")`/Failsafe `*IT.java`, a Jest
   `*.integration.test.ts` pattern, a Go `//go:build integration` tag). Asks once if either dimension is
   genuinely ambiguous; asks before writing anything if the repo has no base runner markers at all.
2. **Selects targets** — diff mode: changed seams/files without matching test changes already in the
   diff. Backfill mode: the files/directories you scope it to. Either way, capped by
   `max_files_per_run` with every skipped target listed by name, never silently dropped.
3. **Generates tests** — happy path, an edge case, and an error case per target, run against the **real**
   dependency (never a mock of it), matching the repo's existing naming/layout and reusing its existing
   fixtures/testcontainers setup.
4. **Verifies and iterates** — spins up the real dependency (via testcontainers/docker-compose when
   available), runs the new tests, fixes genuine test bugs, and — critically — **never patches production
   code to force a failing test green**. If no orchestration mechanism is available and none can be stood
   up this session, targets are tagged `NEEDS_INTEGRATION_ENV` rather than silently falling back to
   mocking the dependency.
5. **Reports** — `INTEGRATION_TEST_REPORT.md`: per-target status, any production-bug findings with exact
   assertion/expected/actual, and a one-line next step.

## When to use

"Write an integration test for the payments service against a real Postgres", "test the seam between
`order-service` and the queue with testcontainers", "add integration coverage for `src/payments/` using
docker-compose." Not for a target that can be fully tested by mocking everything (**unit-test-creator**),
a consumer/provider contract agreement (**contract-test-creator**), or a full browser user journey
(**e2e-test-creator**). Full routing table: [SKILL.md](SKILL.md#when-to-use-not-to-use).

## Invocation examples

```
target: {mode: diff, source: "MR !123"}, repo_root: ./services/payments
target: {mode: backfill, scope: ["src/payments/charge.py"]}, repo_root: .
```

More scenarios, including a `NEEDS_INTEGRATION_ENV` degraded run and a cross-skill handoff:
[examples.md](examples.md).

## What you get

New/modified test files matching the repo's own conventions, running against a real dependency, plus
`INTEGRATION_TEST_REPORT.md` — format spec: [reference/report-format.md](reference/report-format.md).

## Install

```bash
cd software-builder
make install-integration-test-creator
```

## Related skills

- **unit-test-creator** — isolated, fully-mocked tests; integration-test-creator escalates here when a
  target doesn't actually need a real dependency
- **e2e-test-creator** — full browser user journeys; integration-test-creator escalates here when the
  caller wants the whole UI flow, not just the service seam
- **contract-test-creator** — consumer/provider interaction agreements (Pact); integration-test-creator
  escalates here when the caller wants an interface contract, not a live dependency test
- **test-writer** — the router that dispatches to this skill (and its three siblings) when the caller
  doesn't name a test level explicitly

Agent instructions: [SKILL.md](SKILL.md).
