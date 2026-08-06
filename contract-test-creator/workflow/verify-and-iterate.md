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
never claim a written test or a written pact file passes/verifies without having run it this session
([skill-contract.md §7](../reference/skill-contract.md)).

## 2. Run the new/changed tests

Execute using the Pact library's own idiomatic command scoped to the new/changed test files. For a
`consumer` target this produces or updates a local pact file (and publishes it, if `broker_configured:
yes`). For a `provider` target this runs the verifier against the real running provider. Record pass/fail
per target.

## 3. On failure — diagnose before touching anything

For each failing target, determine which side is wrong:

- **Test bug** (wrong matcher, bad mock-provider setup, a typo in the assertion) — fix the test, re-run.
  Allowed up to **3 attempts** per target; on a 3rd consecutive failure, stop and tag `NEEDS_HUMAN` rather
  than looping indefinitely.
- **Production bug** — this is the gate in
  [gate-policy.md §6](../reference/gate-policy.md#6-verification-surfaces-a-probable-production-bug), and
  it has a contract-specific shape:
  - For a `consumer` target: the consumer's own handling of a real provider response doesn't do what its
    contract/docstring/existing callers imply.
  - For a `provider` target: **a provider verification failure against a real, already-existing pact file
    usually means the provider broke a real consumer's expectation.** This is the case that matters most
    in this skill — never patch the provider code silently, and never edit the pact file (widen a
    matcher, delete the failing interaction) to make the verification pass. Both hide a real regression
    from every consumer relying on that interaction.

  Either way: tag the target `WRITTEN_FAILING_PROD_BUG`, keep the failing test and the pact file exactly
  as they are (they're correct — the code is what's wrong), and record the specific
  interaction/expected-vs-actual values for the report.

When genuinely unsure which side is wrong after one honest look, tag `NEEDS_HUMAN` rather than guessing —
guessing wrong in either direction is worse than asking.

## 4. Final tags

Every target lands in `verify_result` as exactly one of:

| Tag | Meaning |
|-----|---------|
| `WRITTEN_PASSING` | Test written, run, passes (consumer: pact produced/updated and matches; provider: verification against every in-scope pact passes) |
| `WRITTEN_FAILING_PROD_BUG` | Test written, run, fails — the code is wrong, not the test or the pact file |
| `NEEDS_HUMAN` | 3 fix attempts exhausted, or genuinely ambiguous which side is wrong |
| `NEEDS_OBSERVED_INTERACTION` | Carried from Generate tests — never had a real usage to derive its shape from, never run |
| `UNVERIFIED` | `run_tests: false` or no execution capability |
| `SKIPPED_ALREADY_COVERED` / `SKIPPED_MAX_FILES` | Carried from Select targets — never reached Generate |

## 5. Deadline / token budget

If `deadline` or `session_token_budget` is reached mid-run, stop *starting* new targets — an in-flight
one finishes its current attempt. Remaining targets are tagged `SKIPPED_MAX_FILES`-style, explicitly
listed in the report as not-yet-attempted, not silently omitted.
