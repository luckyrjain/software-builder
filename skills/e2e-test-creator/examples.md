# Examples

Conventions: [examples-conventions.md](../docs/skill-framework/shared/examples-conventions.md).

## Invocation

| # | User says | Resolves to | Notes |
|---|-----------|-------------|-------|
| 1 | "Write an e2e test for the checkout flow in MR !123" | e2e-test-creator, diff mode | `target: {mode: diff, source: "MR !123"}` — journey inferred from the changed checkout page |
| 2 | "Backfill an e2e test for the login journey, starting at `/login`" | e2e-test-creator, backfill mode | `target: {mode: backfill, journeys: [{name: "user logs in", start_route: "/login"}]}` |
| 3 | "Add browser test coverage for the whole checkout experience" | e2e-test-creator, backfill mode | Caller must still name the journey(s) explicitly — see [gate-policy.md §1](reference/gate-policy.md#1-missing-or-malformed-target-reporoot) |
| 4 | "Test my working-tree changes end-to-end in a real browser" | e2e-test-creator, diff mode | `source: "working-tree"` |
| 5 | "Use Cypress for this, we're mid-migration off Playwright" | e2e-test-creator, Detect conventions | `test_framework_hint: cypress` resolves the ambiguity gate without asking |
| 6 | "Write a unit test for `formatCurrency`" | **unit-test-creator**, not e2e-test-creator | Function-level, isolated — no browser involved |
| 7 | "Write an integration test hitting the real payments DB" | **integration-test-creator**, not e2e-test-creator | Below-the-UI service seam, not a full browser journey |
| 8 | "Review the e2e suite on MR !482 for quality" | **pr-review**, not e2e-test-creator | Reviewing existing tests, not writing new ones |

## Scenario: diff mode, journey inferred from a changed page

**User:** "Write an e2e test for MR !123 — it adds the new checkout confirmation page"

**Agent:**
1. Inputs — `target: {mode: diff, source: "MR !123"}`, `repo_root` resolved
2. Detect conventions — scans the repo

**Expected fragments:**

```
STATUS: DETECTED
FRAMEWORK: playwright
CONFIDENCE: HIGH
MARKER: playwright.config.ts
LAYOUT: e2e/ (*.spec.ts)
```

3. Select targets — the diff adds `checkout/confirm.tsx` with no matching spec change; infers the journey
   "user completes checkout" without the caller having to name it
4. Generate tests — a reachable staging URL was supplied; writes `e2e/checkout.spec.ts` asserting the
   page shows an "Order confirmed" heading and the URL is `/checkout/confirm`, using role-based selectors
   (the repo's own existing convention)
5. Verify & iterate — runs Playwright against the staging URL

```
user completes checkout: WRITTEN_PASSING
```

6. Report — `E2E_TEST_REPORT.md` written, next step: "Ready to open as an MR"

## Scenario: backfill mode, explicit journey, production bug found

**User:** "Backfill an e2e test for the login journey" — `target.journeys: [{name: "user logs in and
views their dashboard", start_route: "/login"}]`

**Agent:**
1. Inputs → Detect conventions (Cypress, HIGH) → Select targets (journey `NEW`)
2. Generate tests — step sequence: visit `/login`, fill credentials, submit, expect the dashboard's
   visible heading; using the repo's own `data-testid` selector convention
3. Verify & iterate — the test fails

**Expected fragments:**

```
user logs in and views their dashboard: WRITTEN_FAILING_PROD_BUG
  Assertion: URL is "/dashboard" and heading "Welcome back" is visible
  Actual:    URL stays "/login", no error message shown
```

4. Report — `## Findings` names the exact assertion and expected/actual values, suggests
   **loop-task-implementer** to fix it or **pr-review** to flag it on the MR under review. The failing
   test is kept exactly as written — it is not weakened or skipped.

## Scenario: Playwright vs. Cypress ambiguity, resolved by hint

**User:** "Add an e2e test for the settings page save flow" (repo has both `playwright.config.ts` and
`cypress.config.js`)

**Agent:**
1. Inputs → Detect conventions — both configs present at comparable confidence

**Expected fragments:**

```
STATUS: AMBIGUOUS
CANDIDATES: playwright (HIGH, playwright.config.ts), cypress (HIGH, cypress.config.js)
```

2. Agent asks: "This repo has both Playwright and Cypress configured — which one should I use?"
3. Caller answers "Playwright — Cypress is being retired" → Detect conventions resumes with
   `test_framework_hint: playwright`, no further asking

## Scenario: degraded path — no reachable app instance

**User:** "Write an e2e test for the search results page" (no local dev server running, no staging URL
supplied, no preview deployment link)

**Agent:**
1. Inputs → Detect conventions → Select targets, same as the happy path
2. Generate tests — checks for a reachable instance per
   [gate-policy.md §5](reference/gate-policy.md#5-no-reachable-app-instance); none exists

**Expected fragments:**

```
user searches and views results: NEEDS_BROWSER_ENV — no reachable app instance this session
```

3. Report — the journey is explicitly `NEEDS_BROWSER_ENV`, never described as passing or as a guess at
   what the search page would show; next step: "Supply a local start command, staging URL, or preview
   deployment, then re-run."

## Scenario: cross-skill handoff

**User (after e2e-test-creator's report):** "Fix the login bug you found"

**Agent:** Hands off to **loop-task-implementer** with the finding from `## Findings` (assertion,
expected/actual, journey name, test file:line) as the task description — e2e-test-creator itself never
edits production code.

**Expected fragments:**

```
**Handoff → loop-task-implementer**
- Finding: successful credentials submit but the app never navigates to /dashboard
- Test: e2e/login.spec.ts::"user logs in and views their dashboard" (currently failing, by design)
- Ask: "Fix the login success handler so e2e/login.spec.ts passes"
```
