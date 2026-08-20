# test-writer

**A router/orchestrator, not a generator.** When a caller asks to write tests without one already-resolved
specialist, test-writer classifies the request into one or more complementary test levels and dispatches
the existing specialist skills:

| Level | Skill |
|-------|-------|
| Unit — isolated, fast, every external dependency mocked | [unit-test-creator](../unit-test-creator/) |
| Integration — the real seam to one real adjacent dependency | [integration-test-creator](../integration-test-creator/) |
| Contract — consumer-driven contract agreement (Pact-style) | [contract-test-creator](../contract-test-creator/) |
| API — black-box Postman/Newman request/response assertions against a real running API | [api-test-creator](../api-test-creator/) |
| E2E — full user journey through a real browser UI | [e2e-test-creator](../e2e-test-creator/) |

It has no detection or generation logic of its own. It builds an ordered, de-duplicated `test_plan`,
dispatches each planned specialist in a fresh context with caller inputs unchanged, preserves every
specialist report verbatim, and derives only orchestration completion state around those reports.

**Single-level compatibility:** if the caller already names one level, invoke that `*-test-creator`
directly. **Multi-level breadth:** if the caller explicitly asks for complementary surfaces such as unit
+ integration or API + e2e, use test-writer to coordinate them. Multiple possible interpretations of the
same behavior are ambiguity, not breadth; ask once instead of dispatching every candidate.

## What it does

1. **Classifies** caller intent using [reference/level-classification.md](reference/level-classification.md)
   without inspecting implementation code to manufacture a level.
2. **Plans** one or more complementary levels in stable, de-duplicated order. Real ambiguity asks once.
3. **Dispatches** every planned specialist independently with caller inputs unchanged; one specialist's
   report is never hidden framing for another.
4. **Aggregates** `level_reports` without rewriting them. Any partial, blocked, failed, escalated, missing,
   or unanswered planned level prevents overall `COMPLETE`; specialist terminal outcomes remain distinct.

## When to use

Use for generic or multi-level test-writing requests such as "write tests for MR !123" or "add unit and
integration coverage for this change". Do not use for reviewing existing test quality (**pr-review**) or
implementing the production feature itself (**loop-task-implementer**). A top-level request naming one
level should go directly to its specialist.

## Invocation examples

```text
request: "unit tests for pricing rules and integration tests for the DB seam", repo_root: .
request: "test the payment flow", repo_root: .    # ambiguous — asks integration vs. e2e
```

More scenarios: [examples.md](examples.md).

## What you get

An ordered `test_plan`, one verbatim specialist report per planned level, and internal orchestration status
`COMPLETE`, `PARTIAL`, `BLOCKED`, `FAILED`, or `ESCALATED`. In the canonical runtime envelope,
`COMPLETE` maps to `SUCCESS`; the other statuses remain unchanged. Specialist reports remain authoritative
for their own test surface. Shared report rules:
[test-creation-principles.md §4](../docs/skill-framework/shared/test-creation-principles.md#4-reporting-format-shared-skeleton).

## Install

```bash
cd software-builder
make install-test-writer
```

Installation chains all five specialist skills automatically. test-writer itself still contains no test
generation/detection implementation.

## Related skills

- **unit-test-creator**, **integration-test-creator**, **contract-test-creator**, **api-test-creator**,
  **e2e-test-creator** — independently authoritative test specialists
- **pr-review** — reviews existing test quality
- **loop-task-implementer** — implements production features/fixes and handles production-bug handoffs

Agent instructions: [SKILL.md](SKILL.md).
