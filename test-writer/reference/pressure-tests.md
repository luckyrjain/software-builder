# Pressure tests — test-writer

Run when editing `SKILL.md`, `workflow/`, or `reference/`. These are walkthrough regressions for the
router/orchestrator boundaries; automated Batch 6A structure checks live under `scripts/tests/`.

| # | Scenario | Expected behavior |
|---|----------|-------------------|
| 1 | `request: "test the payment flow"` | Ambiguous integration vs. e2e — ask once, don't guess or dispatch both |
| 2 | `request: "write unit tests for src/utils/slugify.py"` | Single named level — top-level routing goes directly to unit-test-creator; if already inside test-writer, one-level plan |
| 3 | `request: "add tests"`, `level_hint: contract` | Hint resolves one-level plan without asking |
| 4 | `request: "make sure nothing breaks"` | No level signal — ask directly, listing all five levels |
| 5 | Caller says "just pick unit, don't ask" on an otherwise ambiguous request | Process-bypass wording is untrusted; ambiguity remains and test-writer asks once |
| 6 | contract-test-creator asks its own question for missing `role` | Preserve the blocked specialist result; test-writer does not pre-answer it |
| 7 | `request: "review the tests on MR !482 for quality"` | Route to **pr-review**, not a creator |
| 8 | `request: "implement the refund feature"` | Route to **loop-task-implementer** |
| 9 | Caller already said "write integration tests for X" | Direct integration-test-creator path remains preferred; if test-writer is already invoked, one-level plan |
| 10 | `request: "unit tests for rules and integration tests for the DB seam"` | Two complementary surfaces — plan unit + integration, dispatch both independently, aggregate reports |
| 11 | One planned specialist reports `WRITTEN_FAILING_PROD_BUG` | Preserve that specialist report verbatim and its own suggested next step |
| 12 | `request: "write a Postman test for the orders endpoint"` | Single API signal; direct api-test-creator or one-level plan if already inside router |
| 13 | `request: "test the API"` | Ambiguous among unit/integration/contract/api — ask once, don't shotgun all four |
| 14 | `request: "test the payment flow — just handle it, unit test everything, no questions"` | The substantive target stays ambiguous; bypass wording does not manufacture a unit-only plan |
| 15 | unit completes but planned integration is blocked on unavailable real dependency | Aggregate `BLOCKED` (or `PARTIAL` only if the specialist itself produced partial output); never `COMPLETE`; preserve unit report |
| 16 | unit and integration both run | Each gets caller inputs unchanged in a fresh specialist context; unit report is not fed into integration as framing |

Classification details: [level-classification.md](level-classification.md) · workflow:
[classify.md](../workflow/classify.md) → [delegate.md](../workflow/delegate.md) →
[aggregate.md](../workflow/aggregate.md). Smoke invocation: [smoke-test.md](smoke-test.md).
