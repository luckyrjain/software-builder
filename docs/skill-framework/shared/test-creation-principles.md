# Test creation principles (shared)

**Normative.** Shared principles for **unit-test-creator**, **integration-test-creator**,
**contract-test-creator**, **e2e-test-creator**, and **api-test-creator**, plus the **test-writer**
router that dispatches to them. Each skill's own `reference/skill-contract.md` links here and states
only its level-specific deltas — do not duplicate these rules inline per skill.

The canonical phase ordering is [test-creator-common-workflow.md](test-creator-common-workflow.md),
and every write follows [test-creator-write-safety.md](test-creator-write-safety.md). Those documents
own cross-level behavior; this file owns quality and reporting principles.

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
`NEEDS_INTEGRATION_ENV`, `NEEDS_OBSERVED_INTERACTION`, `NEEDS_BROWSER_ENV`) — never a differently-named status for a
concept this section already names.

**Write authority boundary:** every skill in this family writes or modifies test files (and, for
api-test-creator, the Postman collection/environment file) in the working tree — nothing more. Every
such batch is preflighted by the shared write guard; a dirty overlap is a fail-closed `BLOCKED` result,
not permission to overwrite.
None of them commits, pushes, or opens a pull/merge request itself. The report's `## Next step`
line may say "Ready to open as an MR" — that is a suggestion for the caller (human or host agent)
to act on, never something this skill does on its own.

## 5. Escalation on a surfaced production bug

Never modify production code to force a failing test green — that's a refactor-limit violation (§3), not
a fix. Report the finding with the exact assertion/expected/actual, and hand off to
**loop-task-implementer** (fix it) or **pr-review** (flag it on the MR under review) — full matrix:
[cross-skill-escalation.md](cross-skill-escalation.md).

## 6. Incremental backfill state (optional)

Backfill mode's `max_files_per_run` cap (§4 of the shared report skeleton — `SKIPPED_MAX_FILES`) bounds
one run, but a large repo needs many runs to fully backfill. Each of the five skills may persist a small
state file so repeated backfill runs make forward progress instead of re-discovering and re-ordering the
same targets from scratch — this is **optional enrichment, never required**, mirroring
[domain-comprehension-integration.md](domain-comprehension-integration.md)'s "read if present, no-op if
absent" shape, except this file is one the skill itself writes rather than one it only reads.

### File and shape

One file per skill per repo, written to `output_dir`: `UNIT_TEST_COVERAGE_STATE.yaml`,
`INTEGRATION_TEST_COVERAGE_STATE.yaml`, `CONTRACT_TEST_COVERAGE_STATE.yaml`, `E2E_TEST_COVERAGE_STATE.yaml`,
`API_TEST_COVERAGE_STATE.yaml`.

```yaml
schema_version: 1
level: unit                       # unit | integration | contract | e2e | api
repo_root: <path>
last_run: <UTC timestamp>
targets:
  - target: "src/payments/charge.py::apply_discount"   # the same identifier verify-and-iterate reports
    status: WRITTEN_PASSING                             # final status from the shared vocabulary (§4)
    content_hash: "<sha256 of the target's source region>"
    test_file: tests/test_charge.py
    last_attempted: <UTC timestamp>
    attempts: 1                                          # only meaningful for NEEDS_HUMAN entries
pending_backlog:                   # targets discovered but not yet attempted — carried to the next run
  - "src/payments/legacy/old_gateway.py"
```

### Read at Select targets

When the state file exists: a target is skipped — `SKIPPED_ALREADY_COVERED`, noted as "per state file"
(distinct from the diff-mode already-covered check, same status) — **only when both** its recorded
`status` is `WRITTEN_PASSING` **and** its `content_hash` still matches the current source. Every other
recorded status (`NEEDS_HUMAN`, `WRITTEN_FAILING_PROD_BUG`, any level-specific `NEEDS_*` gate,
`UNVERIFIED`) means the target was never actually resolved to a real passing test — it was **not**
covered, whatever the state file says about it, so it is never skipped on hash-match alone. Treat it
exactly like a `pending_backlog` entry (see below) regardless of whether it happens to already be listed
there. A target whose hash has **changed** since `last_attempted` is treated as new outright — the state
entry is stale, not authoritative; re-attempt it. `pending_backlog` entries (and any non-`WRITTEN_PASSING`
entries per the rule above) are prioritized ahead of newly discovered targets when building this run's
ordering (after any [domain-comprehension prioritization](domain-comprehension-integration.md), before
the `max_files_per_run` cap) — a caller running backfill repeatedly on the same large scope works through
the backlog in bounded chunks instead of restarting at the same front of the list every time, and a target
stuck on `NEEDS_HUMAN` keeps resurfacing instead of silently vanishing from view.

### Write after Verify & iterate

Upsert an entry for every target this run actually attempted (any terminal status from §4, including
`UNVERIFIED`). Add to `pending_backlog` (dedup against existing entries): every target newly tagged
`SKIPPED_MAX_FILES` this run, **and** every attempted target whose final status is anything other than
`WRITTEN_PASSING` — per the read-side rule above, an unresolved target must stay visible to the next run,
not just recorded and forgotten. Remove a target from `pending_backlog` once it reaches `WRITTEN_PASSING`
with a matching hash. Report §Next step states the backlog size when non-empty: "N targets remain in
`pending_backlog` — re-run to continue."

### Rules

- **Optional, never a gate.** No state file → every target discovered fresh, exactly as documented
  elsewhere in `select-targets.md` — not a degraded mode, not a note in the report.
- **Unreadable or malformed state file → ignore it and start fresh.** Log one line noting the file was
  unreadable; never hard-fail a run over a corrupt cache.
- **Hash, not mtime.** Checkouts, CI clones, and rebases all produce unreliable mtimes; a content hash is
  the only staleness signal that survives them.
- **Never authoritative over code evidence.** Same precedence rule as
  [domain-comprehension-integration.md §3](domain-comprehension-integration.md#3-precedence-code-evidence-always-wins) —
  the state file accelerates *ordering*, it never substitutes for actually reading the target when it's
  this run's turn to be attempted.

## 7. Framework

Routing: [skill-routing.md](skill-routing.md) · prompt injection
[prompt-injection.md](prompt-injection.md) · smoke-test conventions
[smoke-test-conventions.md](smoke-test-conventions.md).
