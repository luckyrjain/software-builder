# Examples

Conventions: [examples-conventions.md](../docs/skill-framework/shared/examples-conventions.md).

## Invocation

| # | User says | Resolves to | Notes |
|---|-----------|-------------|-------|
| 1 | "Write a Postman/Newman test for the new `POST /api/orders` endpoint" | api-test-creator, diff mode | `target: {mode: diff, source: "working-tree"}` |
| 2 | "Backfill black-box API tests for `POST /api/orders` and `GET /api/orders/:id`" | api-test-creator, backfill mode | `target: {mode: backfill, scope: ["POST /api/orders", "GET /api/orders/:id"]}` |
| 3 | "We have two collection files, use `postman/payments.postman_collection.json`" | api-test-creator, Detect conventions | `test_framework_hint: postman/payments.postman_collection.json` resolves the ambiguity gate without asking |
| 4 | "Backfill API tests for everything under `services/orders-api/src/routes/`" | api-test-creator, backfill mode | Directory scope expands to every endpoint it defines |
| 5 | "Draft the requests, we can't reach staging from this session" | api-test-creator, `run_tests: false` | Requests written and reported `UNVERIFIED`, not run |
| 6 | "Mock the orders service entirely and unit test the client's retry logic" | **unit-test-creator**, not api-test-creator | Isolated in-process test, not a black-box HTTP call |
| 7 | "Write a testcontainers-backed integration test against a real Postgres" | **integration-test-creator**, not api-test-creator | Real-dependency-seam test, not a black-box HTTP call |
| 8 | "Write an e2e test that clicks through placing an order in the browser" | **e2e-test-creator**, not api-test-creator | Browser UI journey, not raw HTTP requests |

## Scenario: diff mode, new endpoint, clean happy path

**User:** "Write a Postman/Newman test for the new `POST /api/orders` endpoint on `orders-api`"

**Agent:**
1. Inputs — `target: {mode: diff, source: "working-tree"}`, `repo_root` resolved
2. Detect conventions — scans the repo

**Expected fragments:**

```
STATUS: DETECTED
FRAMEWORK: postman
CONFIDENCE: HIGH
MARKER: postman/orders-api.postman_collection.json (only collection file found)
COLLECTION_COUNT: 1
NEWMAN: yes
```

3. Select targets — `POST /api/orders` route registered in the diff with no matching collection-request
   change
4. Generate tests — shape derived from `src/routes/orders.ts:18`; adds `Orders > Create order` to
   `postman/orders-api.postman_collection.json` asserting `201`, response body `id`/`total_cents` fields,
   and `Location` header
5. Verify & iterate — runs `newman run postman/orders-api.postman_collection.json`

```
POST /api/orders: WRITTEN_PASSING
```

6. Report — `API_TEST_REPORT.md` written, next step: "Ready to open as an MR"

## Scenario: backfill mode, explicit endpoint list

**User:** "Backfill black-box API tests for `GET /api/orders/:id` and `DELETE /api/orders/:id`"

**Agent:**
1. Inputs — `target: {mode: backfill, scope: ["GET /api/orders/:id", "DELETE /api/orders/:id"]}`
2. Detect conventions — collection resolved, `CONFIDENCE: HIGH`
3. Select targets — both endpoints tagged `NEW` (neither has an existing collection request)
4. Generate tests — `GET` shape derived from `src/routes/orders.ts:24`; `DELETE` shape derived from
   `src/routes/orders.ts:31` (returns `204`, no body). The `DELETE` request chains off the `GET` request's
   captured `{{orderId}}` variable rather than a hard-coded id.
5. Verify & iterate — both pass

```
GET /api/orders/:id: WRITTEN_PASSING
DELETE /api/orders/:id: WRITTEN_PASSING
```

6. Report — next step: "Ready to open as an MR"

## Scenario: ambiguous collection, resolved by hint

**User:** "Backfill an API test for `GET /api/refunds/:id` — we have two collection files, use the payments
one"

**Agent:**
1. Inputs — `target: {mode: backfill, scope: ["GET /api/refunds/:id"]}`, `test_framework_hint:
   postman/payments.postman_collection.json`
2. Detect conventions — two `*.postman_collection.json` files exist, neither named `main`/`primary`, but
   the hint names one of the printed `CANDIDATES`

**Expected fragments:**

```
STATUS: DETECTED
FRAMEWORK: postman
CONFIDENCE: HIGH
MARKER: postman/payments.postman_collection.json (selected via --hint)
COLLECTION_COUNT: 2
```

3. Select targets → Generate tests — request added to `postman/payments.postman_collection.json`, not the
   sibling `postman/orders.postman_collection.json`
4. Verify & iterate — passes

```
GET /api/refunds/:id: WRITTEN_PASSING
```

5. Report — `Collection: postman/payments.postman_collection.json (HIGH)` shown in the header

## Scenario: degraded path — no reachable API instance

**User:** "Write API tests for `POST /api/orders`" — but this session has no local start command, no
staging URL, and no preview deployment for `orders-api`

**Agent:**
1. Inputs → Detect conventions → Select targets → Generate tests, same as the happy path (a real
   route-handler match exists, so the request/response shape is real, not fabricated)
2. Verify & iterate — no reachable API instance to run against

**Expected fragments:**

```
POST /api/orders: NEEDS_API_ENV — no reachable running API instance this session; resolve with a local
  start command, a staging URL, or a preview deployment
```

3. Report — the target is listed `NEEDS_API_ENV` under `## Blocked — NEEDS_API_ENV`, never described as
   passing; next step: "1 target blocked — supply a reachable API instance"

## Scenario: cross-skill handoff

**User (after api-test-creator's report):** "Fix the 500 you found on `GET /api/orders/:id`"

**Agent:** Hands off to **loop-task-implementer** with the finding from `## Findings` (endpoint, expected/
actual, request name) as the task description — api-test-creator itself never edits production code or
loosens the assertion to route around the break.

**Expected fragments:**

```
**Handoff → loop-task-implementer**
- Finding: GET /api/orders/:id returns 500 for a valid id instead of 200 with the order body
- Request: postman/orders-api.postman_collection.json → "Orders > Get order by id" (currently failing, by design)
- Ask: "Fix orders-api so 'Orders > Get order by id' passes against a real orders/:id lookup"
```
