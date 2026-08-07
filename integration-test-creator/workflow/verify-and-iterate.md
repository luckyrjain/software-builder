---
workflow_version: 1.0
phase: verify_and_iterate
produces:
  - verify_result
consumes:
  - test_files_written
  - run_tests
  - orchestration
---

# Verify & iterate

## 1. `run_tests: false` or no execution capability

Do not run anything. Every target in `test_files_written` is tagged `UNVERIFIED` in `verify_result` —
never claim a written test passes without having run it this session
([skill-contract.md](../reference/skill-contract.md)).

## 2. `NEEDS_INTEGRATION_ENV` — no way to stand up the real dependency

If `orchestration` is `none` and this session cannot otherwise reach a real instance of the dependency
(no reachable Docker daemon for testcontainers/docker-compose, no embedded convention already in the
repo), do not run the target and do not fall back to mocking the dependency to get *something* green.
Tag it `NEEDS_INTEGRATION_ENV` — distinct from `UNVERIFIED` (which means "not run for a session-scope
reason unrelated to infra availability") — per
[gate-policy.md §5](../reference/gate-policy.md#5-zero-orchestration-mechanism-detected).

## 3. Stand up the real dependency and run

When `orchestration` is `testcontainers` or `docker-compose`, start it via the repo's own convention (the
existing testcontainers module/fixture, or `docker-compose -f <file> up` for the compose file
`detect-conventions` found) before running the new/changed integration tests. When `orchestration` is
`embedded`, no separate startup step is needed — the embedded instance starts with the test process
itself, per the repo's own convention. Execute using the framework's own idiomatic command scoped to the
new/changed test files (not necessarily the full suite, unless the framework has no narrower selection
mechanism). Record pass/fail per target. Tear down any container/compose stack this phase started, per the
repo's own convention (e.g. testcontainers' own lifecycle, `docker-compose down`) — never leave it running
past the end of this phase.

## 4. On failure — diagnose before touching anything

For each failing target, determine which side is wrong:

- **Test bug** (wrong expected value, bad fixture/seed data, a typo in the assertion, a container not yet
  ready — use the orchestration tool's own readiness-wait, never a blind `sleep`) — fix the test, re-run.
  Allowed up to **3 attempts** per target; on a 3rd consecutive failure, stop and tag `NEEDS_HUMAN` rather
  than looping indefinitely.
- **Production bug** (the code under test genuinely does not do what its own contract/docstring/existing
  callers imply against the real dependency) — this is the gate in shared
  [test-creation-principles.md §5](../../docs/skill-framework/shared/test-creation-principles.md#5-escalation-on-a-surfaced-production-bug).
  **Never** patch production code to force the test green, and never delete, weaken, or `.skip`/`xfail`
  the assertion that caught it. Tag the target `WRITTEN_FAILING_PROD_BUG`, keep the failing test exactly
  as written (it's correct — the code is what's wrong), and record the specific assertion/expected-vs-
  actual values for the report.

When genuinely unsure which side is wrong after one honest look, tag `NEEDS_HUMAN` rather than guessing —
guessing wrong in either direction is worse than asking.

## 5. Final tags

Every target lands in `verify_result` as exactly one of:

| Tag | Meaning |
|-----|---------|
| `WRITTEN_PASSING` | Test written, run against the real dependency, passes |
| `WRITTEN_FAILING_PROD_BUG` | Test written, run, fails — the code is wrong, not the test |
| `NEEDS_HUMAN` | 3 fix attempts exhausted, or genuinely ambiguous which side is wrong |
| `NEEDS_INTEGRATION_ENV` | Written, correct, but this session has no way to stand up the real dependency |
| `UNVERIFIED` | `run_tests: false` or no execution capability, for a reason unrelated to orchestration availability |
| `SKIPPED_ALREADY_COVERED` / `SKIPPED_MAX_FILES` | Carried from Select targets — never reached Generate |

## 6. Deadline / token budget

If `deadline` or `session_token_budget` is reached mid-run, stop *starting* new targets — an in-flight
one finishes its current attempt (including tearing down any container it started). Remaining targets are
tagged `SKIPPED_MAX_FILES`-style, explicitly listed in the report as not-yet-attempted, not silently
omitted.
