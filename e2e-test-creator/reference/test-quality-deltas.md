# Test quality — e2e deltas

The full checklist (asserts on real behavior, one behavior per test, deterministic, isolated,
descriptive name, matches the repo's own convention, reuses existing fixtures) is shared across all four
`*-test-creator` skills — see
[test-creation-principles.md §2](../../docs/skill-framework/shared/test-creation-principles.md#2-test-quality-rules).
This file states only what's **different** for a full-browser end-to-end test on top of that checklist.

## Required, on top of the shared checklist

| Rule | Why |
|------|-----|
| Assert only on user-visible outcomes — visible text, ARIA role/accessible name, URL, visibly rendered state | Internal DOM structure/class names aren't part of the page's real contract with a user, and change for reasons that have nothing to do with the journey breaking |
| Prefer the repo's own existing selector convention (role-based queries, `data-testid`, etc.); default to role/accessible-name selectors when none exists, and say so explicitly in the report | A second, unrelated selector convention introduced alongside an established one drifts the suite out of sync with itself |
| Never a hard-coded `sleep`/fixed wait (`time.sleep`, `cy.wait(<fixed ms>)`, `Thread.sleep`, `page.waitForTimeout`) | Fixed waits are either too short (flaky) or too long (slow) — the framework's own auto-wait/retry-assertion mechanism is both faster and correct |
| Requires a reachable running instance of the app to write or run against | An assertion on "what the page shows" without ever having seen the page render is a guess, not a test — see [gate-policy.md §5](gate-policy.md#5-no-reachable-app-instance) |

## Delta on escalation: a flaky selector is a test bug, not a default `NEEDS_HUMAN`

E2E tests are more prone to timing/selector flakiness than unit or integration tests, simply because a
real browser and a real render pipeline are involved. **A test that fails because of a bad selector or a
race condition against the framework's own auto-waiting is a test bug to fix, not an automatic escalation
to `NEEDS_HUMAN`** — fix the selector or wait condition and re-run, within the normal 3-attempt cap in
[verify-and-iterate.md §3](../workflow/verify-and-iterate.md#3-on-failure-diagnose-before-touching-anything).
Only escalate to `NEEDS_HUMAN` when the 3 attempts are exhausted, or when it's genuinely unclear whether
the flakiness traces to the test or to a real race condition in the app itself (in which case the app race
condition is the finding, not the test).

## Forbidden, on top of the shared list

| Anti-pattern | Why wrong |
|--------------|-----------|
| Asserting on a CSS class name, a component's internal state, or the DOM tree shape | Not part of the page's contract with a user; breaks on refactors that change nothing a user would notice |
| A fixed-duration wait anywhere in a generated spec | See the required-rules table above |
| Writing an assertion for a page/state this session has never actually observed rendering | Fabrication — see [gate-policy.md §5](gate-policy.md#5-no-reachable-app-instance) |
