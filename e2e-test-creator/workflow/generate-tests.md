---
workflow_version: 1.1
phase: generate_tests
produces:
  - test_files_written
consumes:
  - target_list
  - test_framework
  - selector_convention
---

# Generate tests

Follow the shared [test-creator common workflow](../../docs/skill-framework/shared/test-creator-common-workflow.md)
and run the [test-creator write-safety contract](../../docs/skill-framework/shared/test-creator-write-safety.md)
before any spec, report, or coverage-state write. The E2E-specific rules below are deltas only.

For every `NEW` journey in `target_list`, write a test that satisfies the shared
[test-creation-principles.md §2](../../docs/skill-framework/shared/test-creation-principles.md#2-test-quality-rules)
checklist plus this skill's own deltas in
[reference/test-quality-deltas.md](../reference/test-quality-deltas.md) — this phase does not restate
either, it enforces them.

## 1. No reachable app instance — check before writing a single assertion

A meaningful e2e assertion has to be grounded in what the app actually renders — its visible text, its
ARIA roles, its URL after navigation. Writing one against a guess of what the UI "probably" shows is
exactly the fabrication [test-creation-principles.md §1](../../docs/skill-framework/shared/test-creation-principles.md#1-test-first-evidence)
forbids. Before generating steps/assertions for any journey, confirm this session can actually reach a
running instance of the app (locally started, a staging URL, or a preview deployment). If none is
reachable, do not proceed — tag every remaining `NEW` journey `NEEDS_BROWSER_ENV` and stop this phase for
them (see [gate-policy.md §5](../reference/gate-policy.md#5-no-reachable-app-instance)).

## 2. One journey, one focused spec

Write tests into the layout `detect-conventions` established — the directory convention the script
reported, or the framework's own idiomatic default. Never collect unrelated journeys into one catch-all
spec file; never rename or relocate an existing spec file to make room.

## 3. Step sequence and coverage shape

Per journey, write the step sequence a real user would take (navigate, fill, click, submit, …) ending in
an assertion on the journey's actual outcome — the "happy path" through the flow. Add a second spec for a
realistic failure/edge branch of the same journey only when the journey has an observable one worth
covering (e.g. "checkout with an expired card is rejected with a visible error") — skip when the journey
genuinely has none, rather than inventing filler.

## 4. Selector convention — user-visible outcomes only

Assert only on what a user actually sees: visible text, ARIA role/accessible name, the resulting URL, or
visibly rendered state. Never assert on internal DOM structure, CSS class names, or implementation details
that are not part of the page's real contract with a user.

Locate elements using the selector convention `detect-conventions` found already established in the
repo's own specs (role-based queries, `data-testid` attributes, or another pattern). When the repo has no
established convention, default to role/accessible-name-based selectors — the most resilient default
across Playwright, Cypress, and Selenium — and state that explicitly in the report as a default, not an
observed convention.

## 5. No hard-coded waits

Never a fixed-duration wait (`time.sleep`, `cy.wait(<fixed ms>)`, `Thread.sleep`, a bare `page.waitForTimeout`).
Use the framework's own auto-waiting/retry-assertion mechanism — Playwright's auto-waiting on actionability
and `expect(...).toBeVisible()`-style assertions, Cypress's built-in retry-ability, or an explicit
`WebDriverWait` with a real condition for Selenium.

## 6. Never touch production code here

This phase writes and edits e2e spec files only. If writing a test surfaces what looks like a production
bug, do not "fix" it inline to make the test pass — carry it forward to
[verify-and-iterate.md](verify-and-iterate.md), which is where that finding gets surfaced rather than
silently resolved.
