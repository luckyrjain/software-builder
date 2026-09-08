# Examples

Conventions: [examples-conventions.md](../docs/skill-framework/shared/examples-conventions.md).

## Invocation

| # | User says | Resolves to | Notes |
|---|-----------|-------------|-------|
| 1 | "Write a Pact contract test for `orders-consumer` calling `orders-provider`'s `GET /orders/:id`" | contract-test-creator, `role: consumer`, diff mode | `target: {mode: diff, source: "working-tree", role: consumer}` |
| 2 | "Verify `orders-provider` still satisfies its consumer pacts" | contract-test-creator, `role: provider`, backfill mode | `target: {mode: backfill, scope: ["services/orders-provider/"], role: provider}` |
| 3 | "Backfill a contract test for the new `refunds` endpoint the consumer just started calling" | contract-test-creator, `role: consumer`, backfill mode | Single-interaction scope |
| 4 | "Write contract tests for MR !210" (no role stated) | contract-test-creator, **role-ambiguous** | HARD STOP — ask "consumer or provider?" before Detect conventions; file paths in the MR are not a reliable signal |
| 5 | "Publish the updated consumer pact and re-verify against the broker" | contract-test-creator, `role: consumer` then a separate `role: provider` run | Two runs, one per role — never inferred to cover both from one invocation |
| 6 | "Use pact-python for this, we're mid-migration off a homegrown contract check" | contract-test-creator, Detect conventions | `test_framework_hint: pact-python` resolves the ambiguity gate without asking |
| 7 | "Write an integration test that actually hits the real provider over HTTP" | **integration-test-creator**, not contract-test-creator | A live call, not an interface agreement |
| 8 | "Mock the provider entirely and unit test the client's retry logic" | **unit-test-creator**, not contract-test-creator | Isolated unit test, not a consumer-driven contract |

## Scenario: consumer role, clean happy path

**User:** "Write a Pact contract test for `orders-consumer`'s new call to `GET /orders/:id` on
`orders-provider`" (`role: consumer`)

**Agent:**
1. Inputs — `target: {mode: diff, source: "working-tree", role: consumer}`, `repo_root` resolved
2. Detect conventions — scans the consumer's directory

**Expected fragments:**

```
STATUS: DETECTED
FRAMEWORK: pact-js
CONFIDENCE: HIGH
MARKER: package.json dependency + pacts/ directory
BROKER: no
```

3. Select targets — `ordersClient.getOrder()` changed with no pact test change in the diff
4. Generate tests — shape derived from `src/clients/ordersClient.ts:42`; writes
   `test/pact/orders.pact.test.ts`, produces `pacts/orders-consumer-orders-provider.json`
5. Verify & iterate — runs the pact test

```
getOrder: WRITTEN_PASSING
```

6. Report — `CONTRACT_TEST_REPORT.md` written, `Role: consumer`, next step: "Ready to open as an MR"

## Scenario: provider role, verification catches a real break

**User:** "Verify `orders-provider` still satisfies its consumer pacts" (`role: provider`)

**Agent:**
1. Inputs → Detect conventions (pact-python, HIGH, `BROKER: no`) → Select targets (every route with an
   existing consumer pact, `NEW`)
2. Generate tests — one provider verification test replaying every pact file in `pacts/`
3. Verify & iterate — the verification fails on one interaction

**Expected fragments:**

```
verify_orders_provider: WRITTEN_FAILING_PROD_BUG
  Interaction: GET /orders/:id — consumer expects "total_cents" (integer)
  Actual:      field renamed to "totalCents" on the provider
```

4. Report — `## Findings` section names the exact interaction and expected/actual field, suggests
   **loop-task-implementer** to fix it or **pr-review** to flag it on the MR under review. The pact file
   is kept exactly as written — it is not loosened or the failing interaction deleted.

## Scenario: broker-based provider verification

**User:** "Re-verify `orders-provider` against every pact published to our broker" (`role: provider`)

**Agent:**
1. Inputs → Detect conventions — `BROKER: yes` (CI config references `PACT_BROKER_BASE_URL`)

**Expected fragments:**

```
STATUS: DETECTED
FRAMEWORK: pact-jvm
CONFIDENCE: MEDIUM
BROKER: yes
```

2. Select targets → Generate tests — the verification test fetches pacts from the broker (matching the
   repo's own CI invocation pattern) rather than reading a local `pacts/` directory
3. Verify & iterate — all fetched interactions pass

```
verify_orders_provider: WRITTEN_PASSING
```

4. Report — `Broker: yes` shown in the header; next step: "Ready to open as an MR"

## Scenario: degraded path — no real usage to derive an interaction from

**User:** "Write a consumer pact test for the new `refunds` client method" — but the method was just
stubbed out, never actually called anywhere yet, and there's no OpenAPI spec for the provider (`role:
consumer`)

**Agent:**
1. Inputs → Detect conventions → Select targets, same as the happy path
2. Generate tests — no call site, no existing client usage, no schema file for this interaction

**Expected fragments:**

```
create_refund: NEEDS_OBSERVED_INTERACTION — no real call site, client usage, or schema found for
  POST /refunds; refusing to invent a request/response shape
```

3. Report — the target is listed as `NEEDS_OBSERVED_INTERACTION` with the one-line reason, never written
   as if it were a real test; next step: "Wire up a real call to `POST /refunds` (or add its OpenAPI
   schema) before contract-test-creator can generate this interaction."

## Scenario: cross-skill handoff

**User (after contract-test-creator's provider-role report):** "Fix the `totalCents` rename you found"

**Agent:** Hands off to **loop-task-implementer** with the finding from `## Findings` (interaction,
expected/actual, test file:line) as the task description — contract-test-creator itself never edits
production code or loosens the pact file to route around the break.

**Expected fragments:**

```
**Handoff → loop-task-implementer**
- Finding: orders-provider renamed "total_cents" to "totalCents", breaking orders-consumer's pact
- Test: test/pact/verify.pact.test.ts (currently failing, by design)
- Pact file: pacts/orders-consumer-orders-provider.json (left unmodified)
- Ask: "Fix orders-provider so test/pact/verify.pact.test.ts passes against the existing pact file"
```
