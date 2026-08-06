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

## 1. No reachable API instance — check before running anything

Running the collection requires a real, reachable API instance — locally started, staging, or a preview
deployment. Before running, confirm this session can actually reach one. If none is reachable, do not run
— tag every target in `test_files_written` `NEEDS_API_ENV` in `verify_result` and name what would resolve
it (a local start command, a staging URL, or a preview deployment), rather than fabricating what a response
would look like ([gate-policy.md §6](../reference/gate-policy.md#6-no-reachable-api-instance)).

## 2. `run_tests: false`

Do not run anything. Every target in `test_files_written` is tagged `UNVERIFIED` in `verify_result` —
never claim a written request passes without having run it this session
([skill-contract.md](../reference/skill-contract.md)).

## 3. Run the new/changed requests via newman

Execute `newman run <collection_path>` (with `-e <environment_file>` when Detect conventions resolved one),
scoped to the new/changed requests via a Postman folder filter when the tool supports it, otherwise the
full collection. Record pass/fail per target.

## 4. On failure — diagnose before touching anything

For each failing target, determine which side is wrong:

- **Test bug** (wrong URL, a stale chained variable, a typo in the assertion, a header name mismatch) —
  fix the request/assertion, re-run. Allowed up to **3 attempts** per target; on a 3rd consecutive failure,
  stop and tag `NEEDS_HUMAN` rather than looping indefinitely.
- **Production bug** — this is the gate in
  [gate-policy.md §7](../reference/gate-policy.md#7-verification-surfaces-a-probable-production-bug): the
  API genuinely returns the wrong status code, an incomplete/incorrect response schema, or a missing
  header relative to what the route-handler source (or spec) says it should. Never patch production code
  to force the assertion green, and never loosen the assertion (widen the schema check, drop the status
  check) to make a failing run pass — that hides a real regression from every real caller of the endpoint.
  Tag the target `WRITTEN_FAILING_PROD_BUG`, keep the failing request and assertion exactly as they are,
  and record the specific expected-vs-actual values for the report.

When genuinely unsure which side is wrong after one honest look, tag `NEEDS_HUMAN` rather than guessing —
guessing wrong in either direction is worse than asking.

## 5. Final tags

Every target lands in `verify_result` as exactly one of:

| Tag | Meaning |
|-----|---------|
| `WRITTEN_PASSING` | Request written, run via newman, passes |
| `WRITTEN_FAILING_PROD_BUG` | Request written, run, fails — the API is wrong, not the test |
| `NEEDS_HUMAN` | 3 fix attempts exhausted, or genuinely ambiguous which side is wrong |
| `NEEDS_OBSERVED_ENDPOINT` | Carried from Generate tests — never had a real observed shape to derive its request/response from, never run |
| `NEEDS_API_ENV` | No reachable running API instance existed this session to run against |
| `UNVERIFIED` | `run_tests: false` |
| `SKIPPED_ALREADY_COVERED` / `SKIPPED_MAX_FILES` | Carried from Select targets — never reached Generate |

## 6. Deadline / token budget

If `deadline` or `session_token_budget` is reached mid-run, stop *starting* new targets — an in-flight one
finishes its current attempt. Remaining targets are tagged `SKIPPED_MAX_FILES`-style, explicitly listed in
the report as not-yet-attempted, not silently omitted.
