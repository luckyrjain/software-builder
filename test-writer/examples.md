# Examples

Conventions: [examples-conventions.md](../docs/skill-framework/shared/examples-conventions.md).

## Invocation

| # | User says | Resolves to | Notes |
|---|-----------|-------------|-------|
| 1 | "Write tests for MR !123" | test-writer, diff mode | `target: {mode: diff, source: "MR !123"}` |
| 2 | "Backfill tests for `src/payments/charge.py`" | test-writer, backfill mode | Single-file scope |
| 3 | "Add test coverage for the whole `src/payments/` module" | test-writer, backfill mode | Directory expands to every source file |
| 4 | "Write tests for my working-tree changes" | test-writer, diff mode | `source: "working-tree"` |
| 5 | "Test this branch against main" | test-writer, diff mode | `source: "branch:feature-x..main"` |
| 6 | "Use Jest for this, we're mid-migration off Mocha" | test-writer, Detect conventions | `test_framework_hint: jest` resolves the ambiguity gate without asking |
| 7 | "Review the tests on MR !482 for quality" | **pr-review**, not test-writer | Reviewing existing tests, not writing new ones |
| 8 | "Implement the refund feature" | **loop-task-implementer**, not test-writer | Production feature implementation, not test generation |

## Scenario: diff mode, clean happy path

**User:** "Write tests for MR !123 in the payments service"

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
4. Generate tests — writes `tests/test_charge.py`, `tests/test_refund.py`
5. Verify & iterate — runs pytest on both new files

```
apply_discount: WRITTEN_PASSING
process_refund: WRITTEN_PASSING
```

6. Report — `TEST_WRITER_REPORT.md` written, next step: "Ready to open as an MR"

## Scenario: backfill mode with a coverage-gap prod bug found

**User:** "Backfill tests for `src/payments/refund.py`"

**Agent:**
1. Inputs → Detect conventions (pytest, HIGH) → Select targets (`process_refund`, `NEW`)
2. Generate tests — happy path + edge case + error case
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

**User:** "Add tests for `frontend/src/utils/format.ts`"

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

**User:** "Draft tests for `src/utils/slugify.py`, but I can't run anything in this session — just write
them" (`run_tests: false`)

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

## Scenario: cross-skill handoff

**User (after test-writer's report):** "Fix the refund bug you found"

**Agent:** Hands off to **loop-task-implementer** with the finding from `## Findings` (assertion,
expected/actual, file:line) as the task description — test-writer itself never edits production code.

**Expected fragments:**

```
**Handoff → loop-task-implementer**
- Finding: process_refund leaves refund.status "pending" after a successful gateway call
- Test: tests/test_refund.py::test_process_refund_marks_completed (currently failing, by design)
- Ask: "Fix process_refund so tests/test_refund.py passes"
```
