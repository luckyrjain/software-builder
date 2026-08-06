# Examples

Conventions: [examples-conventions.md](../docs/skill-framework/shared/examples-conventions.md).

## Invocation

| # | User says | Resolves to | Notes |
|---|-----------|-------------|-------|
| 1 | "Write unit tests for MR !123" | unit-test-creator, diff mode | `target: {mode: diff, source: "MR !123"}` |
| 2 | "Backfill unit tests for `src/payments/charge.py`" | unit-test-creator, backfill mode | Single-file scope |
| 3 | "Add isolated test coverage for the whole `src/payments/` module" | unit-test-creator, backfill mode | Directory expands to every source file |
| 4 | "Write unit tests for my working-tree changes" | unit-test-creator, diff mode | `source: "working-tree"` |
| 5 | "Unit test this branch against main, mock the gateway client" | unit-test-creator, diff mode | `source: "branch:feature-x..main"` |
| 6 | "Use Jest for this, we're mid-migration off Mocha" | unit-test-creator, Detect conventions | `test_framework_hint: jest` resolves the ambiguity gate without asking |
| 7 | "Write a test for `charge.py` against the real staging database" | **integration-test-creator**, not unit-test-creator | Needs a real adjacent dependency, not a mock — see [gate-policy.md §5](reference/gate-policy.md#5-target-cant-be-isolated-from-a-real-dependency) |
| 8 | "Review the tests on MR !482 for quality" | **pr-review**, not unit-test-creator | Reviewing existing tests, not writing new ones |

## Scenario: diff mode, clean happy path

**User:** "Write unit tests for MR !123 in the payments service"

**Agent:**
1. Inputs — `target: {mode: diff, source: "MR !123"}`, `repo_root` resolved
2. Detect conventions — scans the repo

**Expected fragments:**

```
STATUS: DETECTED
FRAMEWORK: pytest
CONFIDENCE: HIGH
MARKER: pyproject.toml [tool.pytest.ini_options]
```

3. Select targets — `apply_discount` and `process_refund` changed with no test changes in the diff
4. Generate tests — writes `tests/test_charge.py`, `tests/test_refund.py`; the payment gateway client is
   mocked using the repo's existing `tests/fakes/gateway.py` fixture, no real network call
5. Verify & iterate — runs pytest on both new files

```
apply_discount: WRITTEN_PASSING
process_refund: WRITTEN_PASSING
```

6. Report — `UNIT_TEST_REPORT.md` written, next step: "Ready to open as an MR"

## Scenario: backfill mode with a coverage-gap prod bug found

**User:** "Backfill unit tests for `src/payments/refund.py`"

**Agent:**
1. Inputs → Detect conventions (pytest, HIGH) → Select targets (`process_refund`, `NEW`)
2. Generate tests — happy path + edge case + error case; gateway client mocked from the existing fixture
3. Verify & iterate — the happy-path test fails

**Expected fragments:**

```
process_refund: WRITTEN_FAILING_PROD_BUG
  Assertion: refund.status == "completed"
  Actual:    "pending"
```

4. Report — `## Findings` section names the exact assertion and expected/actual values, suggests
   **loop-task-implementer** to fix it or **pr-review** to flag it on the MR under review. The failing
   test is kept exactly as written — it is not weakened or skipped.

## Scenario: ambiguous framework, resolved by asking

**User:** "Add unit tests for `frontend/src/utils/format.ts`"

**Agent:**
1. Inputs → Detect conventions — both `jest.config.js` and `.mocharc.json` present at comparable
   confidence

**Expected fragments:**

```
STATUS: AMBIGUOUS
CANDIDATES: jest (HIGH, jest.config.js), mocha (HIGH, .mocharc.json)
```

2. Agent asks: "This repo has both Jest and Mocha configured — which one should I use?"
3. Caller answers "Jest" → Detect conventions resumes with `test_framework_hint: jest`, no further asking

## Scenario: degraded path — no execution capability

**User:** "Draft unit tests for `src/utils/slugify.py`, but I can't run anything in this session — just
write them" (`run_tests: false`)

**Agent:**
1. Inputs → Detect conventions → Select targets → Generate tests, same as the happy path
2. Verify & iterate — skipped, per [gate-policy.md](reference/gate-policy.md) §1 of
   [verify-and-iterate.md](workflow/verify-and-iterate.md)

**Expected fragments:**

```
slugify: UNVERIFIED — not executed this session
```

3. Report — every target explicitly `UNVERIFIED`, never described as passing; next step: "Run
   `pytest tests/test_slugify.py` before opening an MR."

## Scenario: cross-skill handoff — target can't be isolated

**User:** "Backfill unit tests for `src/payments/webhook.py`"

**Agent:**
1. Inputs → Detect conventions (pytest, HIGH) → Select targets (`verify_signature`, `NEW`)
2. Generate tests — `verify_signature` calls the live signing service directly to validate a webhook;
   the repo has no existing mock/stub for that service anywhere in its test suite
3. Generate tests gate fires — [gate-policy.md §5](reference/gate-policy.md#5-target-cant-be-isolated-from-a-real-dependency)

**Expected fragments:**

```
verify_signature: UNTESTABLE_WITHOUT_FIXTURE
  Reason: calls the live signing service directly; no existing mock convention in the repo
```

4. Report — `## Findings` names the target and reason, and hands off rather than fabricating mock
   behavior for a dependency this session has never actually observed:

```
**Handoff → integration-test-creator**
- Target: src/payments/webhook.py::verify_signature
- Repo: <repo_root>
- Reason: no existing mock convention for the signing service; needs a real dependency, not a guessed mock
- Ask: "Write an integration test for verify_signature against the real signing service"
```
