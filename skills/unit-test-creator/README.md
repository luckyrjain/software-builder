# unit-test-creator

**Writes real, running unit tests** for a target repository — isolated, fast, function/class-level, with
every external dependency mocked or stubbed. Detects the repo's own test framework and conventions
first, then generates tests that match them, runs them, and iterates on failures. Two entry modes:
**diff** (test what just changed in an MR/branch/working tree) and **backfill** (test an existing
coverage gap you point it at).

No MCP, no other skill required to run standalone — pure repository read/write plus the ability to
execute the target repo's own test command (optional; see `run_tests` below).

## What it does

1. **Detects conventions** — scans for a test framework (pytest, Jest/Vitest/Mocha, Go `testing`, JUnit
   via Maven/Gradle, RSpec/Minitest, xUnit/NUnit/MSTest, `cargo test`), its layout, and existing fixture/
   mock helpers. Asks once if detection is genuinely ambiguous; asks before writing anything if the repo
   has no framework markers at all — it never invents one.
2. **Selects targets** — diff mode: changed functions/classes without matching test changes already in
   the diff. Backfill mode: the files/directories you scope it to. Either way, capped by
   `max_files_per_run` with every skipped target listed by name, never silently dropped.
3. **Generates tests** — happy path, an edge case, and an error case per target, matching the repo's
   existing naming/layout, reusing its existing fixtures/mocks, and mocking every network call, real
   database, filesystem I/O, wall-clock dependency, and source of randomness. No tautological assertions.
4. **Verifies and iterates** — runs the new tests, fixes genuine test bugs, and — critically — **never
   patches production code to force a failing test green**. If the code is what's actually wrong, that's
   reported as a finding, not silently resolved.
5. **Reports** — `UNIT_TEST_REPORT.md`: per-target status, any production-bug findings with exact
   assertion/expected/actual, any target that couldn't be isolated (with a pointer to
   **integration-test-creator**), and a one-line next step.

## When to use

"Write unit tests for MR !123", "backfill unit tests for `src/payments/`", "add isolated test coverage
for this branch." Not for a target needing a real adjacent dependency (**integration-test-creator**),
reviewing someone else's existing test quality (**pr-review**), or implementing the production feature
itself (**loop-task-implementer**). Full routing table:
[SKILL.md](SKILL.md#when-to-use-not-to-use).

## Invocation examples

```
target: {mode: diff, source: "MR !123"}, repo_root: ./services/payments
target: {mode: backfill, scope: ["src/payments/charge.py"]}, repo_root: .
```

More scenarios, including a production-bug finding, an untestable-without-fixture escalation, and a
degraded (`run_tests: false`) run: [examples.md](examples.md).

## What you get

New/modified test files matching the repo's own conventions, plus `UNIT_TEST_REPORT.md` — format spec:
[reference/report-format.md](reference/report-format.md).

## Install

```bash
cd software-builder
make install-unit-test-creator
```

## Related skills

- **test-writer** — the router that dispatches to this skill when the level ("unit tests") is named or
  classified; you can also invoke unit-test-creator directly
- **integration-test-creator** — the next skill when a target genuinely needs a real adjacent dependency
  this skill's mocking discipline says not to fabricate
- **pr-review** — reviews an existing MR, including its test coverage; unit-test-creator only writes new
  tests
- **loop-task-implementer** — implements production features/fixes; unit-test-creator hands
  production-bug findings to it rather than fixing them itself

Agent instructions: [SKILL.md](SKILL.md).
