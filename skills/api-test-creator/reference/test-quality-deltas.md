# Test quality deltas — API tests

Every rule in the shared
[test-creation-principles.md §2](../../docs/skill-framework/shared/test-creation-principles.md#2-test-quality-rules)
applies unchanged. This file adds only what's different for a black-box Postman/Newman API test — load this
before [workflow/generate-tests.md](../workflow/generate-tests.md); it does not restate the shared
checklist.

## Additional required rules

| Rule | Why |
|------|-----|
| A request's method/path/headers/body and its expected response trace to real, observed usage — the actual route-handler code, an OpenAPI/Swagger spec already in the repo, or `API_CATALOG.md` as corroborating evidence only | The shared "test-first evidence" principle's API-specific instance: a guessed shape is an assertion with nothing real behind it — see [gate-policy.md §5](gate-policy.md#5-target-has-no-real-observed-endpoint-to-derive-its-shape-from) |
| Assert on **status code AND response schema/fields**, not just "200 OK" | A status-only assertion passes even when the handler silently drops or renames a field a real caller depends on |
| Chain requests via Postman variables/environment (`pm.environment.set(...)` in the creating request's test script, `{{var}}` in the dependent request) | A hard-coded ID copied from a manual run breaks the moment the underlying data changes, and can't run twice in a row |
| Clean up any state the collection creates, when the API exposes a way to (a `DELETE` on the created resource, a teardown request in the same folder) | An API test suite that leaves orphaned records behind pollutes the environment it runs against and breaks idempotent re-runs |
| Reuse the collection's own base-URL variable (e.g. `{{baseUrl}}`) rather than a hard-coded host | A hard-coded host silently breaks the moment the suite runs against a different environment (local, staging, preview) |

## Additional forbidden

| Anti-pattern | Why wrong |
|--------------|-----------|
| Inventing a plausible-looking request/response body because no real route-handler code, spec, or catalog entry was found | This is exactly the case [gate-policy.md §5](gate-policy.md#5-target-has-no-real-observed-endpoint-to-derive-its-shape-from) exists to catch — tag `NEEDS_OBSERVED_ENDPOINT` instead |
| Widening a schema assertion or dropping the status-code check to make a failing run pass | Hides a real regression from every real caller of the endpoint — see [gate-policy.md §7](gate-policy.md#7-verification-surfaces-a-probable-production-bug) |
| A request whose test script only checks `pm.response.to.have.status(200)` and nothing else | Passes trivially and verifies nothing about the actual response contract |
| Hard-coding an ID, token, or timestamp captured from a one-off manual run instead of chaining it live | Breaks on the very next run once that data no longer exists |
| Writing an assertion for an endpoint this session has never actually run a request against | Fabrication — see [gate-policy.md §6](gate-policy.md#6-no-reachable-api-instance) |
