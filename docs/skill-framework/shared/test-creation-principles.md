# Test creation principles (shared)

**Normative.** Shared principles for **unit-test-creator**, **integration-test-creator**,
**contract-test-creator**, and **e2e-test-creator**, plus the **test-writer** router that dispatches to
them. Each skill's own `reference/skill-contract.md` links here and states only its level-specific
deltas — do not duplicate these rules inline per skill.

**Reference bar:** `unit-test-creator/reference/skill-contract.md` (shortest, cleanest delta example).

## 1. Test-first evidence

- Never claim a test passes without having run it this session. `run_tests: false`, or no execution
  capability, means every target is explicitly `UNVERIFIED` in the report — never described as passing.
- Every assertion must be grounded in real, observed behavior — a real return value, a real raised
  error, a real response, a real UI state — never a guessed or "plausible" value.
- A mock/stub/fixture is only as trustworthy as the real behavior it's built from. Build it from an
  existing, already-established convention in the repo (an existing fixture, an existing recorded
  interaction, an existing consumer contract) — never invent believed-plausible behavior for a dependency
  this session has never actually observed.

## 2. Test-quality rules

| Rule | Why |
|------|-----|
| Asserts on real behavior — a return value, a raised error, a state change, an observed interaction | A tautology (`assert True`, an assertion that can't fail) passes forever and catches nothing |
| One behavior per test | A test asserting several unrelated things fails opaquely |
| Deterministic | No unseeded randomness, no real wall-clock dependency, no flaky timing — use the framework's own retry/wait mechanism where one exists |
| Isolated | No shared mutable state across tests, no dependence on execution order or another test's side effect |
| Descriptive name | States the scenario and expected outcome, not `test1` |
| Matches the repo's own naming/layout/tooling convention | Detected first, per each skill's own `reference/framework-detection.md` — never a second convention introduced alongside an established one |
| Reuses existing fixtures/mocks/test utilities over inventing new ones | Duplicated setup drifts out of sync with the real one over time |

### Forbidden everywhere

| Anti-pattern | Why wrong |
|--------------|-----------|
| Weakening or deleting an existing assertion to make a suite pass | Hides a real regression — see §3 and §5 |
| `.skip` / `xfail` / `@Disabled` (or level equivalent) without a corresponding report line | Silently reduces coverage the caller believes still exists |
| Mocking a dependency's behavior from a guess rather than its real, observed contract | Green test, wrong belief about what the system does |
| A test that only exercises the mock, not the code/seam under test | Common when a mock is over-specified — assert on real output/behavior, not "the mock was called," unless the interaction itself is the contract |

Each skill's own `reference/test-quality-deltas.md` (or equivalent) adds only what's different for its
level — e.g. integration tests must **not** mock the seam under test; e2e tests must assert on
user-visible outcomes, never internal DOM/state details.

## 3. Refactor limits

- **Default: zero production-code changes.** Every skill in this family writes or modifies test files
  only.
- A **testability refactor** — extracting a pure function, introducing a seam/interface, injecting a
  dependency — is allowed only when all three hold: (a) it is the only way to make the target reachable
  under test, (b) it provably does not change observable behavior (any existing tests still pass
  unmodified), and (c) it is called out explicitly, by name and diff, in the report's own `## Findings`
  section — never a silent drive-by change bundled into a test file's own diff.
- **Never**: a refactor that changes a public signature/API without updating every caller in the same
  change; a refactor that changes behavior to make a wrong test pass; or a refactor that routes around a
  genuine bug instead of reporting it (§5).
- When it's unclear whether a change is a safe testability refactor or a behavior change, treat it as a
  behavior change — ask, don't guess.

## 4. Reporting format (shared skeleton)

Each skill emits its own file (`UNIT_TEST_REPORT.md`, `INTEGRATION_TEST_REPORT.md`,
`CONTRACT_TEST_REPORT.md`, `E2E_TEST_REPORT.md`) — normative per-skill spec lives in that skill's own
`reference/report-format.md` — but every one follows this shared shape:

```markdown
# <Level> Test Report

Mode: diff | backfill
Target: <source, or scope>
Repo: <repo_root>
Framework/tooling: <detected> (<confidence>)
Generated: <UTC timestamp>

## Summary
| Status | Count |
|--------|-------|
...

## Targets
| Target | Status | Test file | Notes |
|--------|--------|-----------|-------|
...

## Findings
Only present when non-empty — covers both a surfaced production bug (§5) and any testability refactor
applied (§3). Each entry says which.

## Skipped
Only present when non-empty — every skipped target listed by name, never a bare count.

## Next step
One line.
```

Shared status vocabulary — used identically everywhere the concept applies, never renamed per skill:
`WRITTEN_PASSING`, `UNVERIFIED`, `NEEDS_HUMAN`, `SKIPPED_ALREADY_COVERED`, `SKIPPED_MAX_FILES`. Each
skill's own `reference/report-format.md` may add level-specific statuses on top (e.g.
`NEEDS_INTEGRATION_ENV`, `NEEDS_PACT_ROLE`, `NEEDS_BROWSER_ENV`) — never a differently-named status for a
concept this section already names.

## 5. Escalation on a surfaced production bug

Never modify production code to force a failing test green — that's a refactor-limit violation (§3), not
a fix. Report the finding with the exact assertion/expected/actual, and hand off to
**loop-task-implementer** (fix it) or **pr-review** (flag it on the MR under review) — full matrix:
[cross-skill-escalation.md](cross-skill-escalation.md).

## 6. Framework

Routing: [skill-routing.md](skill-routing.md) · prompt injection
[prompt-injection.md](prompt-injection.md) · smoke-test conventions
[smoke-test-conventions.md](smoke-test-conventions.md).
