# api-test-creator

**Writes real, running black-box API test suites** (Postman collections, run via Newman) — detects the
repo's own Postman/Newman tooling and canonical collection file first, then writes request/assertion pairs
for changed or backfilled endpoints, runs them against a real reachable API instance, and iterates on
failures. Two entry modes: **diff** (test endpoints implied by changed route/handler definitions) and
**backfill** (an explicit endpoint list, or a file/directory that expands to the endpoints it defines).

No MCP, no other skill required to run standalone — pure repository read/write plus the ability to reach a
running API instance and execute `newman` (optional; see `run_tests` below).

## What it does

1. **Detects conventions** — scans for `*.postman_collection.json` file(s) and a `newman` dependency. With
   2+ collection files, resolves which one is canonical via a caller hint, a `main`/`primary` naming
   convention, or a CI reference — asking only when none of those narrows it to one. Asks before writing
   anything if the repo has no Postman/Newman tooling at all — it never invents a collection unasked.
2. **Selects targets** — diff mode: endpoints implied by changed route/handler definitions without a
   matching collection-request change already in the diff. Backfill mode: the endpoint descriptors or
   files/directories you scope it to (expanded to the endpoints they define). Either way, capped by
   `max_files_per_run` with every skipped target listed by name, never silently dropped.
3. **Generates tests** — every request's method/path/headers/body and its expected response (status code,
   schema/fields, headers) traces to real, observed usage — the actual route-handler code, an OpenAPI/
   Swagger spec already in the repo, or `API_CATALOG.md` as corroborating evidence only — never a guess.
   Requests are chained via Postman variables/environment when a flow requires it (e.g. create-then-fetch).
4. **Verifies and iterates** — runs the collection via `newman`, fixes genuine test bugs, and — critically —
   **never patches production code or loosens a `pm.test()` assertion** to force a failing run green. A
   verification failure against a real running API is reported as a finding, not silently resolved.
5. **Reports** — `API_TEST_REPORT.md`: per-target status, any production-bug findings with the exact
   expected/actual, and a one-line next step.

## Requires a reachable running API instance

A meaningful assertion can only be written and run against a real API — locally started, staging, or a
preview deployment. Without one, affected targets are gated `NEEDS_API_ENV` rather than fabricating what a
response would look like. See
[reference/gate-policy.md §6](reference/gate-policy.md#6-no-reachable-api-instance).

## When to use

"Write a Postman/Newman test for `POST /api/orders`", "backfill black-box API tests for the orders
service." Not for an in-process/mocked unit test (**unit-test-creator**), a real-dependency-seam test via
testcontainers (**integration-test-creator**), a consumer-driven Pact contract (**contract-test-creator**),
or a browser UI journey (**e2e-test-creator**). Full routing table:
[SKILL.md](SKILL.md#when-to-use-not-to-use).

## Invocation examples

```
target: {mode: diff, source: "MR !123"}, repo_root: ./services/orders-api
target: {mode: backfill, scope: ["POST /api/orders", "GET /api/orders/:id"]}, repo_root: .
```

More scenarios, including an ambiguous-collection resolution and a degraded (`NEEDS_API_ENV`) run:
[examples.md](examples.md).

## What you get

New/modified Postman collection request(s) (plus environment variables for any chained flow) matching the
repo's own conventions, plus `API_TEST_REPORT.md` — format spec:
[reference/report-format.md](reference/report-format.md).

## Install

```bash
cd software-builder
make install-api-test-creator
```

## Related skills

- **unit-test-creator** — isolated, fully-mocked, in-process tests; api-test-creator only writes real
  black-box HTTP requests against a running instance, never a mock
- **integration-test-creator** — a real-dependency-seam test (e.g. via testcontainers); api-test-creator
  tests the API's own HTTP surface, not what's behind it
- **contract-test-creator** — a consumer-driven Pact interface agreement; api-test-creator asserts on the
  API's actual live behavior, not an interface contract
- **e2e-test-creator** — a full browser UI journey; api-test-creator issues raw HTTP requests, never drives
  a browser
- **test-writer** — the thin router that dispatches a level-unspecified test-writing request to this skill
  (or one of its four siblings) when the caller names "API"/"Postman"/"black-box" explicitly
- **loop-task-implementer** — implements production features/fixes; api-test-creator hands production-bug
  findings to it rather than fixing them itself

Agent instructions: [SKILL.md](SKILL.md).
