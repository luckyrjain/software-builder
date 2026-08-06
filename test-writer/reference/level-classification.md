# Level classification

Keyword heuristics used by [workflow/classify.md](../workflow/classify.md). Mirrors the same trigger
phrases [skill-routing.md](../../docs/skill-framework/shared/skill-routing.md) uses to route callers
directly to each skill — this table exists so the router's classification can't drift from the canonical
routing table.

## Keyword table

| Level | Trigger phrases | Skill |
|-------|------------------|-------|
| Unit | "unit test", "mock", "isolated test", "fast test", function/class-level, TDD | unit-test-creator |
| Integration | "integration test", "real database", "testcontainers", "docker-compose test", "seam between", against a real dependency | integration-test-creator |
| Contract | "contract test", "Pact", "consumer-driven", "provider verification", "pact broker" | contract-test-creator |
| E2E | "e2e", "end-to-end", "browser test", "user journey", "click-through", "Playwright", "Cypress", "Selenium" | e2e-test-creator |
| API | "API test", "Postman", "Newman", "black-box API test", "request/response assertion", "REST endpoint test" | api-test-creator |

## Ambiguous combinations (ask, don't guess)

| Request pattern | Why it's ambiguous |
|-------------------|----------------------|
| "test the payment flow" | Could be integration (the payment-processing seam) or e2e (the full checkout journey) |
| "test the API" | Could be unit (a single handler, mocked), integration (against a real DB), contract (does the response shape match what a consumer expects), or api (a black-box Postman/Newman request/response suite) |
| "make sure this doesn't break anything" | No level signal at all — ask directly |
| A request naming two levels ("unit and integration tests for X") | Two genuine targets, not one ambiguous one — ask whether the caller wants both dispatched (two separate invocations) or one specific level now |

## Unambiguous defaults (do NOT ask)

| Request pattern | Resolves to |
|-------------------|---------------|
| A bare function/class name with no dependency/UI language | unit — the narrowest, most common default when nothing else is signaled |
| "add coverage for `<file>`" with no other qualifier, and the file is a pure/leaf module (no DB/HTTP/UI calls visible in a quick read) | unit |

These are the only two default-without-asking cases — everything else in the keyword table or the
ambiguous-combinations table above requires either an unambiguous keyword match or a live question. Never
extend this "unambiguous defaults" list to cover a case just because asking feels like friction — a wrong
default here produces the wrong *kind* of test, not a cosmetic error.
