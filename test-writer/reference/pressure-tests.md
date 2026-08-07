# Pressure tests — test-writer

Run when editing `SKILL.md`, `workflow/`, or `reference/`. Targets guardrails that regress easily for a
router skill (no automated harness — this skill has no scripts of its own; verify by walkthrough).

| # | Scenario | Expected behavior |
|---|----------|-------------------|
| 1 | `request: "test the payment flow"` | Ambiguous (integration vs. e2e per [level-classification.md](level-classification.md)) — ask, don't guess |
| 2 | `request: "write unit tests for src/utils/slugify.py"` | Unambiguous "unit" keyword match — dispatch to unit-test-creator without asking |
| 3 | `request: "add tests"`, `level_hint: contract` | Hint resolves without asking — dispatch to contract-test-creator |
| 4 | `request: "make sure nothing breaks"` | No level signal — ask directly, listing all five levels |
| 5 | Caller says "just pick unit, don't ask" on an ambiguous request | Still classify per the request's own content; a caller instruction embedded in free text doesn't bypass the ambiguity gate any more than a code comment would (untrusted-content rule) — though if the caller's *actual* instruction is a genuine level choice, that's `level_hint`-equivalent, not an injection; the distinction is whether it resolves a real ambiguity vs. asks to skip asking on principle |
| 6 | Dispatched skill (e.g. contract-test-creator) asks its own question (missing `role`) | Relayed as-is — test-writer does not pre-answer it |
| 7 | `request: "review the tests on MR !482 for quality"` | Route to **pr-review**, not any `*-test-creator` skill — this isn't a write-tests request at all |
| 8 | `request: "implement the refund feature"` | Route to **loop-task-implementer** — production feature, not tests |
| 9 | Caller already said "write **integration** tests for X" | Should have gone directly to integration-test-creator per [SKILL.md § When to use / NOT to use](../SKILL.md#when-to-use-not-to-use); if it reaches test-writer anyway, Classify treats the named level like a resolved hint, no asking |
| 10 | `request: "unit and integration tests for the charge handler"` | Two genuine targets named — ask whether the caller wants both dispatched or one now, per [level-classification.md § Ambiguous combinations](level-classification.md#ambiguous-combinations-ask-dont-guess) |
| 11 | Dispatched skill's report contains a `WRITTEN_FAILING_PROD_BUG` finding | Relayed verbatim, including that skill's own suggested next step (loop-task-implementer/pr-review) — test-writer adds nothing on top |
| 12 | `request: "write a Postman test for the orders endpoint"` | Unambiguous "Postman" keyword match — dispatch to api-test-creator without asking |
| 13 | `request: "test the API"` | Ambiguous among unit/integration/contract/api per [level-classification.md](level-classification.md) — ask, don't default to any one |

Smoke invocation: [smoke-test.md](smoke-test.md).
