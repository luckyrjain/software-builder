# Test quality checklist

Every test this skill writes must satisfy all of the following. Load this before
[workflow/generate-tests.md](../workflow/generate-tests.md).

## Required

| Rule | Why |
|------|-----|
| Asserts on real behavior — a return value, a raised error, a state change, a call made to a mock | A tautology (`assert True`, `expect(x).toBeDefined()` alone, `assertNotNull` on a value that's never null) passes forever and catches nothing |
| One behavior per test | A test asserting three unrelated things fails opaquely — the next reader can't tell which broke |
| Deterministic | No unseeded randomness, no real wall-clock dependency (`sleep`-and-hope), no real network call unless the target genuinely is an integration test the repo already runs that way |
| Isolated | No shared mutable state across tests, no dependence on execution order or a previous test's side effect |
| Descriptive name | The name states the scenario and expected outcome (`rejects_negative_amount`, not `test1` or `testCharge`) |
| Matches the repo's own naming/layout convention | From `detect-conventions` — never a second convention introduced alongside an established one |
| Covers at least: happy path, one edge case, one error case (when the code has an observable failure mode) | Per [generate-tests.md §2](../workflow/generate-tests.md#2-coverage-shape-per-target) |
| Reuses existing fixtures/mocks over inventing new ones | Duplicated setup logic drifts out of sync with the real one over time |

## Forbidden

| Anti-pattern | Why wrong |
|--------------|-----------|
| Asserting only that a function "didn't throw" when it has a real return contract | Misses the actual behavior under test |
| Mocking a dependency's behavior from a guess rather than its real, observed contract | Green test, wrong belief about what the code does — see [gate-policy.md §5](gate-policy.md#5-target-needs-infrastructure-this-session-cant-reach) |
| Weakening or deleting an existing assertion to make a suite pass | Hides a real regression — see [gate-policy.md §6](gate-policy.md#6-verification-surfaces-a-probable-production-bug) |
| `.skip` / `xfail` / `@Disabled` without a corresponding report line | Silently reduces coverage the caller believes still exists |
| Copy-pasting one test N times with only a literal changed | Prefer the framework's parametrize/table-test mechanism when the repo's own tests already use one; otherwise distinct, named tests |
| A test that only exercises the mock, not the code under test | Common when a mock is over-specified — assert on the production code's own output/behavior, not on "the mock was called" alone unless the interaction itself is the contract |
