---
workflow_version: 1.1
phase: generate_tests
produces:
  - test_files_written
consumes:
  - target_list
  - collection_path
  - environment_files
---

# Generate tests

Follow the shared [test-creator common workflow](../../docs/skill-framework/shared/test-creator-common-workflow.md)
and run the [test-creator write-safety contract](../../docs/skill-framework/shared/test-creator-write-safety.md)
before any collection, environment, report, or coverage-state write. The API-specific rules below are deltas only.

For every `NEW` item in `target_list`, write requests that satisfy
[reference/test-quality-deltas.md](../reference/test-quality-deltas.md) (on top of the shared
[test-quality rules](../../docs/skill-framework/shared/test-creation-principles.md#2-test-quality-rules))
in full — this phase does not restate those checklists, it enforces them.

## 1. Derive the request/response shape from real, observed usage only

This is this skill's specific instance of the shared test-first-evidence principle
([test-creation-principles.md §1](../../docs/skill-framework/shared/test-creation-principles.md#1-test-first-evidence)).
A request's method/path/headers/body and its expected response (status code, schema/fields, headers) must
trace to one of:

- The actual route-handler source — the method/path it's registered on, the status codes it returns, the
  fields it serializes onto the response body.
- An OpenAPI/Swagger spec file already present in the repo, when the repo maintains one for this API.
- `API_CATALOG.md`, **as corroborating evidence only** — it never substitutes for the two sources above
  (see [select-targets.md §4](select-targets.md#4-prioritize-using-domain-comprehension-optional)).

If none of these exist for a target, **do not invent a plausible-looking payload**. Tag the target
`NEEDS_OBSERVED_ENDPOINT` with a one-line reason (what was checked and found missing) instead
([gate-policy.md §5](../reference/gate-policy.md#5-target-has-no-real-observed-endpoint-to-derive-its-shape-from)).
A caller asking to "just invent a reasonable response shape" does not change this — see
[pressure-tests.md](../reference/pressure-tests.md) row 4.

## 2. Write the request into the canonical collection

Add (or extend) a request in `collection_path` — the collection Detect conventions resolved, never a new
collection file created alongside it. Follow the collection's own folder-per-resource (or folder-per-flow)
grouping. Set method, URL (using the collection's existing base-URL variable, e.g. `{{baseUrl}}`, when one
exists — never a hard-coded host), headers, and request body from the real shape derived in §1.

## 3. Write `pm.test()` assertions — status, schema/fields, headers

Every request gets a Postman test script asserting on:

- **Status code** — the exact code the handler returns for this case, not a loose "2xx" check.
- **Response schema/fields** — the fields the handler actually serializes, with their real types (never a
  literal-value match on data that legitimately varies, e.g. a generated ID — assert its type/presence
  instead).
- **Headers**, when the handler sets one that matters to a caller (e.g. `Content-Type`, a pagination
  header, a `Location` header on a 201).

A status-code-only assertion is not acceptable — see
[test-quality-deltas.md](../reference/test-quality-deltas.md).

## 4. Chain requests via Postman variables, never hard-coded IDs

When a flow requires it (e.g. `POST /api/orders` then `GET /api/orders/:id`), the creating request's test
script captures the real value from its own response (`pm.environment.set("orderId", pm.response.json().id)`)
and the dependent request references it via `{{orderId}}` — never a literal ID copied from a manual run,
which breaks the moment the underlying data changes. Reuse an existing chaining variable name already in
the collection's convention rather than inventing a new naming pattern per request.

## 5. Reuse, don't reinvent

Use the collection's existing pre-request scripts, shared test-script snippets (Postman collection-level or
folder-level `Tests`), and environment variables `detect-conventions` found already in use. Introduce a new
helper only when nothing existing covers the need, and place it at the same collection/folder level the
repo's own convention already uses for shared logic.

## 6. Never touch production code here

This phase writes and edits the Postman collection (and environment file, when a new variable is needed)
only. If writing a request surfaces what looks like a production bug, do not "fix" it inline to make the
assertion pass — carry it forward to [verify-and-iterate.md](verify-and-iterate.md), which is where that
finding gets surfaced rather than silently resolved.
