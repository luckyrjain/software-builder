---
inclusion: manual
---

For generating or backfilling full user-journey browser end-to-end tests for a target repository (login,
checkout, a click-through flow, using Playwright, Cypress, or Selenium/WebDriver — either for what changed
in an MR/branch/diff, or to backfill coverage for an explicit journey), read `e2e-test-creator/SKILL.md`.
Tests target **journeys**, not files or functions. A below-the-UI service-seam test routes to
`integration-test-creator/SKILL.md` instead; an isolated, mocked function-level test routes to
`unit-test-creator/SKILL.md` instead.

Phase index: `e2e-test-creator/reference/phase-index.md`. Reference loads:
`e2e-test-creator/reference/lazy-load-index.md`.
Detects the target repo's own browser tooling/layout/selector conventions before writing anything — never
introduces a second framework or fabricates one for a repo with none, without asking. Asserts only on
user-visible outcomes (never internal DOM/state), never a hard-coded wait, and requires a reachable
running instance of the app — gates as `NEEDS_BROWSER_ENV` rather than fabricating what the UI would show.
Never modifies production code to force a failing test green.
