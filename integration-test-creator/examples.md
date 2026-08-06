# Examples

Conventions: [examples-conventions.md](../docs/skill-framework/shared/examples-conventions.md).

## Invocation

| # | User says | Resolves to | Notes |
|---|-----------|-------------|-------|
| 1 | "Write an integration test for MR !123's changes against the real Postgres" | integration-test-creator, diff mode | `target: {mode: diff, source: "MR !123"}` |
| 2 | "Backfill an integration test for `src/payments/repository.py`" | integration-test-creator, backfill mode | Single-file scope |
| 3 | "Add integration coverage for the whole `src/orders/` module against the real queue" | integration-test-creator, backfill mode | Directory expands to every seam-bearing source file |
| 4 | "Test my working-tree changes against a real testcontainers DB" | integration-test-creator, diff mode | `source: "working-tree"` |
| 5 | "Use testcontainers for this, we're mid-migration off docker-compose" | integration-test-creator, Detect conventions | Reported `ORCHESTRATION` reflects both; no separate orchestration hint needed — the script reports both mechanisms if present, priority order resolves it |
| 6 | "Write tests for `pure_discount_calculator()` — it just does math, no I/O" | **unit-test-creator**, not integration-test-creator | No real adjacent dependency — a mocked unit test is the right level |
| 7 | "Write a Pact contract test for checkout calling the payments API" | **contract-test-creator**, not integration-test-creator | A consumer/provider interaction agreement, not a live-dependency test |
| 8 | "Write an end-to-end test that clicks through checkout in the browser" | **e2e-test-creator**, not integration-test-creator | Full UI journey, not just the service seam |

## Scenario: diff mode, clean happy path with testcontainers

**User:** "Write an integration test for MR !123 in the payments service — it touches the DB layer"

**Agent:**
1. Inputs — `target: {mode: diff, source: "MR !123"}`, `repo_root` resolved
2. Detect conventions — scans the repo

**Expected fragments:**

```
STATUS: DETECTED
FRAMEWORK: pytest
CONFIDENCE: HIGH
MARKER: pyproject.toml [tool.pytest.ini_options]
ORCHESTRATION: testcontainers
ORCHESTRATION_CONFIDENCE: HIGH
ORCHESTRATION_MARKER: pyproject.toml (testcontainers)
CONVENTION: tests/integration/ directory
```

3. Select targets — `save_charge` (talks to Postgres) changed with no integration test change in the diff
4. Generate tests — writes `tests/integration/test_charge_repository.py`, spinning up a real Postgres via
   the repo's existing testcontainers fixture
5. Verify & iterate — starts the container, runs pytest against the real database, tears the container
   down

```
save_charge: WRITTEN_PASSING
```

6. Report — `INTEGRATION_TEST_REPORT.md` written, next step: "Ready to open as an MR"

## Scenario: backfill mode with a real-dependency prod bug found

**User:** "Backfill an integration test for `src/payments/refund.py` against the real DB"

**Agent:**
1. Inputs → Detect conventions (pytest, HIGH; `ORCHESTRATION: testcontainers`, HIGH) → Select targets
   (`process_refund`, `NEW`)
2. Generate tests — happy path + edge case (constraint conflict) + error case, all against a real
   testcontainers Postgres
3. Verify & iterate — the happy-path test fails after re-reading the row from the real database

**Expected fragments:**

```
process_refund: WRITTEN_FAILING_PROD_BUG
  Assertion: refund.status == "completed" (re-read from Postgres)
  Actual:    "pending"
```

4. Report — `## Findings` section names the exact assertion and expected/actual values, suggests
   **loop-task-implementer** to fix it or **pr-review** to flag it on the MR under review. The failing
   test is kept exactly as written, run against the real dependency — it is not weakened, skipped, or
   quietly switched to a mock.

## Scenario: ambiguous base runner, resolved by asking

**User:** "Add an integration test for `frontend/src/api/ordersClient.ts` against the real API"

**Agent:**
1. Inputs → Detect conventions — both `jest.config.js` and `.mocharc.json` present at comparable
   confidence

**Expected fragments:**

```
STATUS: AMBIGUOUS
CANDIDATES: jest (HIGH, jest.config.js), mocha (HIGH, .mocharc.json)
ORCHESTRATION: docker-compose
ORCHESTRATION_CONFIDENCE: HIGH
ORCHESTRATION_MARKER: docker-compose.test.yml
```

2. Agent asks: "This repo has both Jest and Mocha configured — which one should I use?"
3. Caller answers "Jest" → Detect conventions resumes with `test_framework_hint: jest`, no further
   asking; the already-reported `ORCHESTRATION: docker-compose` carries through unchanged

## Scenario: degraded path — no orchestration mechanism available (`NEEDS_INTEGRATION_ENV`)

**User:** "Backfill an integration test for `src/orders/create.py` — it publishes to the queue"

**Agent:**
1. Inputs → Detect conventions:

```
STATUS: DETECTED
FRAMEWORK: pytest
CONFIDENCE: HIGH
MARKER: pytest.ini
ORCHESTRATION: none
ORCHESTRATION_CONFIDENCE: NONE
ORCHESTRATION_MARKER: none
CONVENTION: tests/integration/ directory
```

2. Select targets → Generate tests — the test is written correctly against the real queue client's real
   interface; it is **not** rewritten against a mocked queue
3. Verify & iterate — no testcontainers dependency, no docker-compose file, and no reachable Docker
   daemon this session

**Expected fragments:**

```
create_order: NEEDS_INTEGRATION_ENV
  Missing: no orchestration mechanism detected, no Docker daemon reachable this session
```

4. Report — every affected target explicitly `NEEDS_INTEGRATION_ENV`, never described as passing and
   never silently switched to a mocked assertion; next step: "Add a `docker-compose.test.yml` for the
   queue, or re-run with Docker available, before opening an MR."

## Scenario: cross-skill handoff

**User (after seeing the target list):** "Actually `pure_discount_calculator()` in that same module
doesn't touch the DB at all — can you still test it here?"

**Agent:** Hands off to **unit-test-creator** for that specific target — it has no real adjacent
dependency, so mocking is the correct (and only sensible) approach, which is exactly what
unit-test-creator does and this skill deliberately does not.

**Expected fragments:**

```
**Handoff → unit-test-creator**
- Target: src/payments/discount.py::pure_discount_calculator
- Repo: <repo_root>
- Reason: no real adjacent dependency — a mocked unit test is the right level, not an integration test
- Ask: "Write a unit test for pure_discount_calculator in src/payments/discount.py"
```
