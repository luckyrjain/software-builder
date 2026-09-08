# Test quality deltas — unit

The full shared checklist (asserts on real behavior, one behavior per test, deterministic, isolated,
descriptive name, matches repo convention, reuses fixtures) lives in
[test-creation-principles.md §2](../../docs/skill-framework/shared/test-creation-principles.md#2-test-quality-rules)
and applies here unchanged. This file adds only what's specific to **unit** scope on top of it — load
this before [workflow/generate-tests.md](../workflow/generate-tests.md), it does not restate the shared
rules.

## Unit-specific additions

| Rule | Why |
|------|-----|
| Every external dependency is mocked or stubbed — network calls, a real database, filesystem I/O (unless the filesystem *is* the unit under test), wall-clock time, randomness | A unit test that reaches a real dependency is not isolated; it's an integration test wearing a unit test's file name — see [reference/skill-contract.md §2](skill-contract.md) |
| Scope is one function/class/module, not a call chain across several | Unit tests fail loud and specific; a test spanning several units re-creates integration-test territory without the seam control an integration test actually has |
| A mock's return value/behavior is built from the real dependency's *observed* contract (an existing fixture, an existing recorded response, the dependency's own documented interface) — never a guessed shape | Shared rule, restated here because it's the single most common way a unit test looks green while asserting nothing real |
| Coverage shape — happy path + at least one edge case + at least one error/invalid-input case (skip the error case only when the code genuinely has no observable failure mode) | Per [workflow/generate-tests.md §2](../workflow/generate-tests.md#2-coverage-shape-per-target) |

## Forbidden, unit-specific

| Anti-pattern | Why wrong |
|--------------|-----------|
| A "unit" test that opens a real socket, hits a real API, or reads/writes outside a temp fixture the test itself owns | No longer isolated or fast — reroute the target to **integration-test-creator** instead of quietly widening scope |
| Faking isolation by mocking so much of the module under test that nothing of the real code path executes | The test only exercises the mock, not the code under test — see the shared "forbidden everywhere" table |
| Treating "I couldn't figure out how to mock it" as equivalent to "this target needs a real dependency" | The former is this session's limitation and should be retried or asked about; only the latter is a genuine `UNTESTABLE_WITHOUT_FIXTURE` |

The shared "Forbidden everywhere" table (weakening assertions, `.skip`/`xfail` without a report line,
guessed mock behavior, mock-only assertions) applies here too — see
[test-creation-principles.md §2](../../docs/skill-framework/shared/test-creation-principles.md#2-test-quality-rules).
