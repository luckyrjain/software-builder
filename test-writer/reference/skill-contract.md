# Skill contract — non-negotiable

Load immediately after [SKILL.md](../SKILL.md). These rules override convenience shortcuts.

## Contract

1. **Scope** — write or modify test files only. Never modify production/application code to make a
   failing test pass; a failure that traces to production code is a finding to report and hand off, not
   something to silently patch (see [gate-policy.md §6](gate-policy.md#6-verification-surfaces-a-probable-production-bug)).
2. **Detect before writing** — always run [workflow/detect-conventions.md](../workflow/detect-conventions.md)
   first. Never introduce a second test framework alongside one the repo already uses, and never invent a
   framework for a repo with none, without asking.
3. **Real assertions only** — every test must satisfy
   [reference/test-quality-checklist.md](test-quality-checklist.md); no tautological or always-pass tests.
4. **Gate, don't guess** — HARD STOP / ask per [reference/gate-policy.md](gate-policy.md) rather than
   guessing a framework, fabricating a mock for infra that isn't reachable, or inventing test data that
   contradicts the code's real contract.
5. **Verify before claiming** — never report a test as passing without having run it in this session.
   When `run_tests: false` or no execution capability exists, mark every target `UNVERIFIED` explicitly.
6. **No silent caps** — `max_files_per_run` or `deadline` overflow is always listed in the report by
   name, never dropped quietly.
7. **Never hide a failure** — no `.skip` / `xfail` / `@Disabled` / deleted assertion to force a suite
   green without flagging it in `TEST_WRITER_REPORT.md`.
8. **Deliverable** — emit [TEST_WRITER_REPORT.md](report-format.md) every run, even for a single-file
   backfill with one target.
9. **Lazy-load** — only the reference file(s) named for the current phase in
   [lazy-load-index.md](lazy-load-index.md); do not bulk-read all of `reference/`.

Routing: [skill-routing.md](../../docs/skill-framework/shared/skill-routing.md).
