# Level classification

Keyword heuristics used by [workflow/classify.md](../workflow/classify.md). Mirrors the canonical
[test skill routing](../../docs/skill-framework/shared/skill-routing.md) while allowing several clearly
complementary surfaces to coexist in one `test_plan`.

## Keyword table

| Level | Trigger phrases | Skill |
|-------|------------------|-------|
| Unit | "unit test", "mock", "isolated test", "fast test", function/class-level, TDD | unit-test-creator |
| Integration | "integration test", "real database", "testcontainers", "docker-compose test", "seam between", real dependency | integration-test-creator |
| Contract | "contract test", "Pact", "consumer-driven", "provider verification", "pact broker" | contract-test-creator |
| API | "API test", "Postman", "Newman", "black-box API test", "request/response assertion", "REST endpoint test" | api-test-creator |
| E2E | "e2e", "end-to-end", "browser test", "user journey", "click-through", "Playwright", "Cypress", "Selenium" | e2e-test-creator |

## Complementary combinations — plan all named surfaces

| Request pattern | Plan |
|-----------------|------|
| "unit tests for rules and integration tests for the DB seam" | unit + integration |
| "Pact contract tests plus Postman API tests" | contract + api |
| "API tests and browser checkout journey" | api + e2e |

The signals refer to distinct surfaces and therefore belong in one ordered, de-duplicated plan.

## Ambiguous combinations — ask once

| Request pattern | Why ambiguous |
|-----------------|---------------|
| "test the payment flow" | Could mean the integration seam or the browser journey |
| "test the API" | Could mean handler unit, integration, contract, or black-box API testing |
| "make sure this doesn't break anything" | No testing-level signal |

Do not dispatch every candidate just because several are plausible. **Ambiguity is not breadth.**

## No source-inspection default

The router does not read implementation code to decide whether a file is "pure", detect dependencies,
or infer a test framework. A caller-provided function/class target can resolve to unit only when the
request itself clearly describes isolated/function-level testing; otherwise ask once. Framework and
repository detection belong to the selected specialist.
