# test-writer

**A router, not a generator.** When a caller asks to "write tests" without saying what kind, test-writer
classifies the request into one of five levels and dispatches to the matching specialist skill:

| Level | Skill |
|-------|-------|
| Unit — isolated, fast, every external dependency mocked | [unit-test-creator](../unit-test-creator/) |
| Integration — the real seam to one real adjacent dependency | [integration-test-creator](../integration-test-creator/) |
| Contract — consumer-driven contract agreement (Pact-style) | [contract-test-creator](../contract-test-creator/) |
| E2E — full user journey through a real browser UI | [e2e-test-creator](../e2e-test-creator/) |
| API — black-box Postman/Newman request/response assertions against a real running API | [api-test-creator](../api-test-creator/) |

Mirrors the composition pattern of `who-owns-x-bot` and `release-readiness-checker`: test-writer has no
detection or generation logic of its own — it classifies, dispatches, and relays the dispatched skill's
own report verbatim.

**If you already know the level**, invoke that `*-test-creator` skill directly ("write unit tests for
X") — this router exists for the "just write tests" case where the level isn't stated yet.

## What it does

1. **Classifies** the request against [reference/level-classification.md](reference/level-classification.md)
   — the same trigger phrases [skill-routing.md](../docs/skill-framework/shared/skill-routing.md) uses to
   route callers directly. Asks once, listing the real candidates, whenever the request is genuinely
   ambiguous between levels or matches none — never guesses.
2. **Dispatches** to exactly one of the five skills, passing every input field through unchanged.
3. **Relays** that skill's report verbatim — no reformatting, no re-summarizing.

## When to use

"Write tests for MR !123", "add test coverage for `<file>`" — level not stated. Not for reviewing
existing test quality (**pr-review**) or implementing the production feature itself
(**loop-task-implementer**). Full routing table: [SKILL.md](SKILL.md#when-to-use-not-to-use).

## Invocation examples

```
request: "write tests for the payments module", repo_root: .
request: "test the payment flow", repo_root: .    # ambiguous — asks integration vs. e2e
```

More scenarios: [examples.md](examples.md).

## What you get

Whatever the dispatched skill produces — `UNIT_TEST_REPORT.md`, `INTEGRATION_TEST_REPORT.md`,
`CONTRACT_TEST_REPORT.md`, `E2E_TEST_REPORT.md`, or `API_TEST_REPORT.md` — relayed unchanged. Shared
report shape: [test-creation-principles.md §4](../docs/skill-framework/shared/test-creation-principles.md).

## Install

```bash
cd software-builder
make install-test-writer
```

Chains all five dispatch targets (`install-unit-test-creator`, `install-integration-test-creator`,
`install-contract-test-creator`, `install-e2e-test-creator`, `install-api-test-creator`) automatically —
the router has no detection or generation logic of its own and is useless without them.

## Related skills

- **unit-test-creator**, **integration-test-creator**, **contract-test-creator**, **e2e-test-creator**,
  **api-test-creator** — the five dispatch targets; each is fully usable standalone without this router
- **pr-review** — reviews existing test quality; test-writer only routes to *writing* new tests
- **loop-task-implementer** — implements production features/fixes; dispatched skills hand production-bug
  findings to it rather than fixing them themselves

Agent instructions: [SKILL.md](SKILL.md).
