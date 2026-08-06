---
inclusion: manual
---

For generating or backfilling automated tests for a target repository (write tests for an MR/branch/
diff, or backfill coverage for a file/module), read `test-writer/SKILL.md`. Reviewing an existing MR's
test quality routes to `pr-review/SKILL.md` instead; implementing the production feature itself routes to
`loop-task-implementer/SKILL.md` instead.

Phase index: `test-writer/reference/phase-index.md`. Reference loads:
`test-writer/reference/lazy-load-index.md`.
Detects the target repo's own test framework/conventions before writing anything — never introduces a
second framework or fabricates one for a repo with none, without asking. Never modifies production code
to force a failing test green.
