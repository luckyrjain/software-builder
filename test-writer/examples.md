# Examples

Conventions: [examples-conventions.md](../docs/skill-framework/shared/examples-conventions.md).

## Invocation

| # | User says | Resolves to | Notes |
|---|-----------|-------------|-------|
| 1 | "Write tests for MR !123" | test-writer classifies → dispatches | Level not stated |
| 2 | "Add unit tests for `src/utils/slugify.py`" | **unit-test-creator** directly | Level named — skip the router |
| 3 | "Write an integration test against the real payments DB" | **integration-test-creator** directly | Level named |
| 4 | "Write a Pact contract test for the billing consumer" | **contract-test-creator** directly | Level named |
| 5 | "Write an e2e test for the checkout journey" | **e2e-test-creator** directly | Level named |
| 6 | "Write a Postman/API test for `POST /api/orders`" | **api-test-creator** directly | Level named |
| 7 | "Test the payment flow" (no level stated) | test-writer, Classify asks | Ambiguous — integration vs. e2e |
| 8 | "Review the tests on MR !482 for quality" | **pr-review**, not test-writer | Reviewing existing tests, not writing new ones |
| 9 | "Implement the refund feature" | **loop-task-implementer**, not test-writer | Production feature, not tests |

## Scenario: unambiguous classification, straight dispatch

**User:** "Write unit tests for the new `apply_discount` function" (level not explicitly named, but the
keyword "unit" is present)

**Agent:**
1. Inputs — `request`, `repo_root` resolved
2. Classify — "unit" keyword match, unambiguous

**Expected fragments:**

```
level: unit → dispatching to unit-test-creator
```

3. Delegate — invokes **unit-test-creator** with `repo_root` unchanged; relays its
   `UNIT_TEST_REPORT.md` verbatim, including its own `apply_discount: WRITTEN_PASSING` status line.

## Scenario: ambiguous request, ask once

**User:** "Test the payment flow end to end... well, make sure the pieces talk to each other correctly"

**Agent:**
1. Inputs → Classify — matches both "integration" (pieces talk to each other) and "e2e" (end to end)
   language

**Expected fragments:**

```
This could mean an integration test (the payment-processing seam against a real dependency) or an e2e
test (the full checkout journey through the UI) — which do you want?
```

2. Caller answers "integration" → Delegate dispatches to **integration-test-creator**, no further asking

## Scenario: level_hint resolves without asking

**User:** "Add test coverage for the billing API", `level_hint: contract`

**Agent:**
1. Inputs → Classify — `level_hint: contract` resolves directly, no question asked
2. Delegate — dispatches to **contract-test-creator**, which then asks its own required question
   (`role: consumer | provider`) since that wasn't supplied — relayed as-is, test-writer doesn't
   pre-answer it.

**Expected fragments:**

```
level: contract (from level_hint) → dispatching to contract-test-creator
```

```
contract-test-creator: is this the consumer side or the provider side of the interaction?
```

## Scenario: degraded path — no clear level at all

**User:** "Just make sure this doesn't break"

**Agent:** Classify finds zero keyword matches.

**Expected fragments:**

```
Which kind of test do you want — unit (isolated, mocked), integration (a real dependency), contract
(Pact-style consumer/provider agreement), e2e (browser user journey), or api (black-box Postman/Newman
request/response suite)?
```

No dispatch happens until the caller answers.

## Scenario: cross-skill handoff (relayed from the dispatched skill)

**User (after test-writer's relayed report shows a production-bug finding):** "Fix the bug it found"

**Agent:** The finding and its suggested next skill came from the dispatched skill's own report
unchanged — test-writer hands off exactly as that skill's report already said (typically
**loop-task-implementer**), adding nothing of its own.
