# test-writer

**Writes real, running tests** for a target repository — detects the repo's own test framework and
conventions first, then generates tests that match them, runs them, and iterates on failures. Two entry
modes: **diff** (test what just changed in an MR/branch/working tree) and **backfill** (test an existing
coverage gap you point it at).

No MCP, no other skill required to run standalone — pure repository read/write plus the ability to
execute the target repo's own test command (optional; see `run_tests` below).

## What it does

1. **Detects conventions** — scans for a test framework (pytest, Jest/Vitest/Mocha, Go `testing`, JUnit
   via Maven/Gradle, RSpec/Minitest, xUnit/NUnit/MSTest, `cargo test`), its layout, and existing fixture/
   mock helpers. Asks once if detection is genuinely ambiguous; asks before writing anything if the repo
   has no framework markers at all — it never invents one.
2. **Selects targets** — diff mode: changed functions/files without matching test changes already in the
   diff. Backfill mode: the files/directories you scope it to. Either way, capped by
   `max_files_per_run` with every skipped target listed by name, never silently dropped.
3. **Generates tests** — happy path, an edge case, and an error case per target, matching the repo's
   existing naming/layout and reusing its existing fixtures/mocks. No tautological assertions.
4. **Verifies and iterates** — runs the new tests, fixes genuine test bugs, and — critically — **never
   patches production code to force a failing test green**. If the code is what's actually wrong, that's
   reported as a finding, not silently resolved.
5. **Reports** — `TEST_WRITER_REPORT.md`: per-target status, any production-bug findings with exact
   assertion/expected/actual, and a one-line next step.

## When to use

"Write tests for MR !123", "backfill tests for `src/payments/`", "add test coverage for this branch."
Not for reviewing someone else's existing test quality (**pr-review**) or implementing the production
feature itself (**loop-task-implementer**). Full routing table: [SKILL.md](SKILL.md#when-to-use-not-to-use).

## Invocation examples

```
target: {mode: diff, source: "MR !123"}, repo_root: ./services/payments
target: {mode: backfill, scope: ["src/payments/charge.py"]}, repo_root: .
```

More scenarios, including a production-bug finding and a degraded (`run_tests: false`) run:
[examples.md](examples.md).

## What you get

New/modified test files matching the repo's own conventions, plus `TEST_WRITER_REPORT.md` — format spec:
[reference/report-format.md](reference/report-format.md).

## Install

```bash
cd software-builder
make install-test-writer
```

## Related skills

- **pr-review** — reviews an existing MR, including its test coverage; test-writer only writes new tests
- **loop-task-implementer** — implements production features/fixes; test-writer hands production-bug
  findings to it rather than fixing them itself
- **mysql-to-postgres-sql** — the closest structural sibling: a non-MCP, scan-then-write code skill with
  its own detection script and pytest-backed self-test

Agent instructions: [SKILL.md](SKILL.md).
