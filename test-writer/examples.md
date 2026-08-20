# Examples

Conventions: [examples-conventions.md](../docs/skill-framework/shared/examples-conventions.md).

## Invocation

| # | User says | Resolves to | Notes |
|---|-----------|-------------|-------|
| 1 | "Write tests for MR !123" | test-writer classifies/plans | Level not stated |
| 2 | "Add unit tests for `src/utils/slugify.py`" | **unit-test-creator** directly | Single level named — skip router |
| 3 | "Write an integration test against the real payments DB" | **integration-test-creator** directly | Single level named |
| 4 | "Write a Pact contract test for the billing consumer" | **contract-test-creator** directly | Single level named |
| 5 | "Write an e2e test for the checkout journey" | **e2e-test-creator** directly | Single level named |
| 6 | "Write a Postman/API test for `POST /api/orders`" | **api-test-creator** directly | Single level named |
| 7 | "Unit tests for pricing rules and integration tests for the DB seam" | test-writer plans unit + integration | Complementary surfaces |
| 8 | "Test the payment flow" | test-writer asks | Ambiguous integration vs. e2e; ambiguity is not breadth |
| 9 | "Review the tests on MR !482 for quality" | **pr-review** | Existing-test review, not creation |
| 10 | "Implement the refund feature" | **loop-task-implementer** | Production implementation |

## Scenario: complementary multi-level plan

**User:** "Write unit tests for the pricing rules and integration tests for the repository/DB seam."

**Agent:**
1. Inputs — resolves request and `repo_root`.
2. Classify — two explicit, complementary surfaces; creates an ordered, de-duplicated plan.

```yaml
test_plan:
  levels: [unit, integration]
  signal_source:
    unit: explicit_request
    integration: explicit_request
```

3. Delegate — invokes **unit-test-creator** and **integration-test-creator** in fresh specialist contexts,
   passing ordinary caller fields unchanged. For each child, test-writer independently advances the
   framework-owned `execution_context` from the same parent per runtime recursion protection. The unit
   report is not injected into the integration prompt.
4. Aggregate — preserves both reports verbatim under `level_reports` and reports internal `COMPLETE` only
   if both specialists return canonical `SUCCESS`; the emitted runtime `skill_result.status` is `SUCCESS`.

## Scenario: ambiguous request, ask once

**User:** "Test the payment flow."

**Agent:** Classify sees alternative interpretations of the same surface rather than complementary work.

```text
This could mean an integration test of the payment-processing seam against a real dependency or an e2e
browser journey through checkout. Which surface do you want?
```

No specialist dispatch occurs until the caller resolves the ambiguity.

## Scenario: level_hint resolves a one-level plan

**User:** "Add test coverage for the billing API", `level_hint: contract`

**Agent:**
1. Inputs → Classify — `level_hint: contract` creates a one-level plan with
   `signal_source.contract: level_hint`.
2. Delegate — dispatches **contract-test-creator** with ordinary caller inputs unchanged and a child
   `execution_context` advanced from the parent.
3. If contract-test-creator requires `role: consumer | provider`, that specialist asks; test-writer does
   not pre-answer the gate.
4. Aggregate reflects the specialist's actual status without rewriting its report.

## Scenario: recursion guard blocks one planned child

The parent context permits unit but rejects an integration handoff because the recursion guard would
revisit a visited skill or exceed the allowed depth.

**Agent:** test-writer does not dispatch the rejected child. It records integration as `BLOCKED`, keeps any
completed unit report, and lets Aggregate include integration in `unfinished_levels`. Sibling contexts are
derived independently, so a unit dispatch never increments integration's starting depth.

## Scenario: incomplete planned level blocks completion

**User:** "Add unit and integration coverage for the charge handler."

Unit generation completes, but integration-test-creator cannot reach the required real dependency.

```yaml
test_plan:
  levels: [unit, integration]
  signal_source:
    unit: explicit_request
    integration: explicit_request
orchestration_status: BLOCKED
unfinished_levels: [integration]
level_reports:
  unit:
    dispatch_status: COMPLETE
    report: <verbatim UNIT_TEST_REPORT.md>
  integration:
    dispatch_status: BLOCKED
    report: <verbatim specialist blocked report>
```

The completed unit report is preserved; test-writer must not report overall `COMPLETE`.

## Scenario: specialist failure propagates

Unit returns canonical `SUCCESS`, but integration-test-creator attempts execution and returns canonical
`FAILED`.

```yaml
orchestration_status: FAILED
level_reports:
  unit:
    dispatch_status: COMPLETE
    report: <verbatim UNIT_TEST_REPORT.md>
  integration:
    dispatch_status: FAILED
    report: <verbatim specialist failed report>
```

The canonical test-writer `skill_result.status` is `FAILED`; failure is not collapsed to `BLOCKED` or
`PARTIAL`.

## Scenario: specialist escalation propagates

If a planned specialist returns canonical `ESCALATED` and no planned level is failed or blocked,
test-writer records `dispatch_status: ESCALATED`, aggregates `ESCALATED`, and preserves the specialist's
recommended next owner/handoff verbatim.

## Scenario: no clear level

**User:** "Just make sure this doesn't break."

Classify has no caller-visible level signal and asks once. It does not inspect code to decide that unit is
the easiest default.

## Scenario: production-bug handoff

If a specialist report contains a production-bug finding, test-writer preserves that report and its own
suggested next skill unchanged. It does not reinterpret the finding or silently fix production code.
