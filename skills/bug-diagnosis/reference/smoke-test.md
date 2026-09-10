# Smoke test — bug-diagnosis

Run after install or any substantive edit. Use a real repository with at least one reproducible issue
— a failing test, a reported error, or a measurable performance regression. The skill remains
read-only: inspect and emit a report; do not modify source, tests, configuration, or any other
repository state.

Conventions: [smoke-test-conventions](../../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> `symptom: <a real failing test or bug description>` `repro_hint: <optional steps or command>`

Example: `symptom: test_payment_retry fails intermittently with AssertionError: expected 3 retries,
got 2` against a repository where that test, or an equivalent reproducible failure, actually exists.

## A correct minimal output contains

1. A HARD STOP if `symptom` is absent.
2. A `repro_status` of `confirmed` with cited evidence, or `unconfirmed` with a stated reason.
3. At least one hypothesis with an active falsification attempt and its result (rejected/survived).
4. A stated root cause with a confidence band and cited evidence, or "Unresolved" with the reason.
5. `BUG_DIAGNOSIS_REPORT.md` / `bug_diagnosis_report` emitted as a report only — no repository write,
   no fix applied, no commit, no PR, and no automatic downstream invocation.

## Degraded paths

| Condition | Expected behavior |
|-----------|---------------------|
| No `symptom` named | HARD STOP — ask for the observed wrong behavior, failing test, or regression |
| No `repro_hint` given | Repro phase derives one from the symptom and code/tests, or reports unconfirmed with a reason |
| Repro cannot be confirmed from available evidence | `repro_status: unconfirmed`; hypotheses formed from it are labeled accordingly |
| No hypothesis survives falsification | `root_cause` states "Unresolved"; never a guessed "least bad" candidate |
| Evidence reveals a live production incident with an active time window | Offer `incident-rca`; do not continue this diagnosis |
| Caller asks the skill to just fix the bug | Reject; report-only; emit the diagnosis, never write source, tests, or configuration |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
