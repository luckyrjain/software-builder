# e2e-test-creator

**Writes real, running browser end-to-end tests** for a target repository — detects the repo's own
Playwright/Cypress/Selenium tooling and layout convention first, then generates tests for whole **user
journeys** ("user logs in and views their dashboard", "user completes checkout") that match them, runs
them against a reachable instance of the app, and iterates on failures. Two entry modes: **diff** (a
journey implied by a changed route/page in an MR/branch/working tree) and **backfill** (an explicit
journey list you point it at).

No MCP, no other skill required to run standalone — pure repository read/write plus the ability to reach
a running instance of the target app (locally started, a staging URL, or a preview deployment).

## What it does

1. **Detects tooling** — scans for browser e2e tooling (Playwright, Cypress, Selenium/WebDriver) and its
   layout convention (`e2e/`, `tests/e2e/`, `cypress/e2e/`, `playwright-tests/`, or a `*.spec.ts`/`*.cy.ts`
   naming pattern). Asks once if detection is genuinely ambiguous; asks before writing anything if the
   repo has no browser-tooling markers at all — it never invents one.
2. **Selects targets** — diff mode: a new/changed route, page, or user-facing component implies a journey
   needs coverage or updating; the journey name/description is inferred from the change, not required
   from the caller. Backfill mode: the caller supplies `target.journeys` explicitly — required and
   non-empty, since a journey has no 1:1 mapping to a source file the way a unit-test target does. Either
   way, capped by `max_files_per_run` with every skipped journey listed by name, never silently dropped.
3. **Generates tests** — a step sequence per journey, asserting only on **user-visible outcomes** (visible
   text, ARIA role/accessible name, URL, visibly rendered state) — never internal DOM structure or class
   names. Never a hard-coded `sleep`/fixed wait. Requires a reachable running instance of the app to write
   real assertions against; gates as `NEEDS_BROWSER_ENV` rather than fabricating what the UI would show.
4. **Verifies and iterates** — runs the new tests against the reachable instance, fixes genuine test bugs
   (including flaky selectors/timing, which count as test bugs to fix, not a reason to escalate by
   default) — and — critically — **never patches production code to force a failing test green**. If the
   app is what's actually wrong, that's reported as a finding, not silently resolved.
5. **Reports** — `E2E_TEST_REPORT.md`: per-journey status, any production-bug findings with exact
   assertion/expected/actual, and a one-line next step.

## When to use

"Write an e2e test for the checkout flow", "test the login journey end-to-end", "backfill browser tests
for the settings page." Not for below-the-UI service-seam tests (**integration-test-creator**), isolated
mocked function-level tests (**unit-test-creator**), or consumer/provider contract agreements
(**contract-test-creator**). Full routing table: [SKILL.md](SKILL.md#when-to-use-not-to-use).

## Invocation examples

```
target: {mode: diff, source: "MR !123"}, repo_root: ./apps/storefront
target: {mode: backfill, journeys: [{name: "user completes checkout", start_route: "/cart"}]}, repo_root: .
```

More scenarios, including an ambiguity resolved by hint and a degraded (`NEEDS_BROWSER_ENV`) run:
[examples.md](examples.md).

## What you get

New/modified e2e spec files matching the repo's own conventions, plus `E2E_TEST_REPORT.md` — format spec:
[reference/report-format.md](reference/report-format.md).

## Install

```bash
cd software-builder
make install-e2e-test-creator
```

## Related skills

- **integration-test-creator** — below-the-UI service-seam tests; e2e-test-creator only writes full
  browser journeys, and hands off when the caller actually wants a seam test instead
- **unit-test-creator** — isolated, mocked function/class-level tests
- **contract-test-creator** — consumer/provider interaction agreements, no browser involved
- **test-writer** — the router that dispatches a level-unspecified test-writing request to this skill (or
  one of its three siblings) directly

Agent instructions: [SKILL.md](SKILL.md).
