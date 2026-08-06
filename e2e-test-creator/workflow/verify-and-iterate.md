---
workflow_version: 1.0
phase: verify_and_iterate
produces:
  - verify_result
consumes:
  - test_files_written
  - run_tests
---

# Verify & iterate

## 1. `run_tests: false` or no execution capability

Do not run anything. Every target in `test_files_written` is tagged `UNVERIFIED` in `verify_result` —
never claim a written test passes without having run it this session
([skill-contract.md](../reference/skill-contract.md)).

## 2. Run the new/changed specs against the reachable instance

Execute using the framework's own idiomatic command scoped to the new/changed spec files (not necessarily
the full suite, unless the framework has no narrower selection mechanism), pointed at the app instance
resolved in [generate-tests.md §1](generate-tests.md#1-no-reachable-app-instance-check-before-writing-a-single-assertion).
Record pass/fail per journey.

## 3. On failure — diagnose before touching anything

For each failing journey, determine which side is wrong:

- **Test bug** — a wrong expected value, a bad step sequence, a selector that doesn't match the repo's own
  convention, or a flaky/racy selector or timing issue. **Flaky-selector and timing issues count as test
  bugs, not automatic escalations** — fix the wait/selector to use the framework's own retry mechanism
  correctly, then re-run. Allowed up to **3 attempts** per journey; on a 3rd consecutive failure, stop and
  tag `NEEDS_HUMAN` rather than looping indefinitely.
- **Production bug** — the app genuinely does not do what the journey's own contract implies (the checkout
  button doesn't lead to a confirmation page, a form submits but the success state never renders). This is
  the gate in [gate-policy.md §6](../reference/gate-policy.md#6-verification-surfaces-a-probable-production-bug),
  same non-negotiable as the shared
  [test-creation-principles.md §5](../../docs/skill-framework/shared/test-creation-principles.md#5-escalation-on-a-surfaced-production-bug):
  **never** patch production code to force the test green, and never delete, weaken, or `.skip`/`.only`-
  around the assertion that caught it. Tag the journey `WRITTEN_FAILING_PROD_BUG`, keep the failing test
  exactly as written, and record the specific assertion/expected-vs-actual values for the report.

When genuinely unsure which side is wrong after one honest look, tag `NEEDS_HUMAN` rather than guessing —
guessing wrong in either direction is worse than asking.

## 4. Final tags

Every journey lands in `verify_result` as exactly one of:

| Tag | Meaning |
|-----|---------|
| `WRITTEN_PASSING` | Test written, run against a reachable instance, passes |
| `WRITTEN_FAILING_PROD_BUG` | Test written, run, fails — the app is wrong, not the test |
| `NEEDS_HUMAN` | 3 fix attempts exhausted, or genuinely ambiguous which side is wrong |
| `NEEDS_BROWSER_ENV` | Carried from Generate tests — no reachable app instance existed to write or run against |
| `UNVERIFIED` | `run_tests: false` or no execution capability |
| `SKIPPED_ALREADY_COVERED` / `SKIPPED_MAX_FILES` | Carried from Select targets — never reached Generate |

## 5. Deadline / token budget

If `deadline` or `session_token_budget` is reached mid-run, stop *starting* new journeys — an in-flight
one finishes its current attempt. Remaining journeys are tagged `SKIPPED_MAX_FILES`-style, explicitly
listed in the report as not-yet-attempted, not silently omitted.
