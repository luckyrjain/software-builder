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
([skill-contract.md §6](../reference/skill-contract.md)).

## 2. Run the new/changed tests

Execute using the framework's own idiomatic command scoped to the new/changed test files (not
necessarily the full suite, unless the framework has no narrower selection mechanism). Record pass/fail
per target.

## 3. On failure — diagnose before touching anything

For each failing target, determine which side is wrong:

- **Test bug** (wrong expected value, bad fixture setup, a typo in the assertion, a mock that doesn't
  match the real dependency's observed contract) — fix the test, re-run. Allowed up to **3 attempts** per
  target; on a 3rd consecutive failure, stop and tag `NEEDS_HUMAN` rather than looping indefinitely.
- **Production bug** (the code under test genuinely does not do what its own contract/docstring/existing
  callers imply) — this is the gate in
  [gate-policy.md §6](../reference/gate-policy.md#6-verification-surfaces-a-probable-production-bug).
  **Never** patch production code to force the test green, and never delete, weaken, or `.skip`/`xfail`
  the assertion that caught it. Tag the target `WRITTEN_FAILING_PROD_BUG`, keep the failing test exactly
  as written (it's correct — the code is what's wrong), and record the specific assertion/expected-vs-
  actual values for the report.

When genuinely unsure which side is wrong after one honest look, tag `NEEDS_HUMAN` rather than guessing —
guessing wrong in either direction is worse than asking.

## 4. Final tags

Every target lands in `verify_result` as exactly one of:

| Tag | Meaning |
|-----|---------|
| `WRITTEN_PASSING` | Test written, run, passes |
| `WRITTEN_FAILING_PROD_BUG` | Test written, run, fails — the code is wrong, not the test |
| `NEEDS_HUMAN` | 3 fix attempts exhausted, or genuinely ambiguous which side is wrong |
| `UNTESTABLE_WITHOUT_FIXTURE` | Carried from Generate tests — never run |
| `UNVERIFIED` | `run_tests: false` or no execution capability |
| `SKIPPED_ALREADY_COVERED` / `SKIPPED_MAX_FILES` | Carried from Select targets — never reached Generate |

## 5. Deadline / token budget

If `deadline` or `session_token_budget` is reached mid-run, stop *starting* new targets — an in-flight
one finishes its current attempt. Remaining targets are tagged `SKIPPED_MAX_FILES`-style, explicitly
listed in the report as not-yet-attempted, not silently omitted.
