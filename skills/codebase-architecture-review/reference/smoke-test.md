# Smoke test — codebase-architecture-review

Run after install or any substantive edit. Use a real, bounded existing subsystem with implementation,
at least one caller, one test or observable behavior, and an ADR or configuration/dependency declaration
when available. The skill remains read-only: inspect and emit a report; do not modify the fixture repository.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> `review_scope: <paths or subsystem>` `repository_evidence: <paths/excerpts>` `history: <optional>`

Example: `review_scope: src/checkout` with evidence from checkout callers, order tests, payment boundaries,
and up to 180 days of relevant Git history.

## A correct minimal output contains

1. A bounded scope with explicit use of no more than 200 fully read files and 3 hotspots.
2. An evidence ledger that separates observations, inference, and gaps.
3. History status; if unavailable, an explicit degraded reason, no churn/co-change claims, and lower
   dependent confidence.
4. Evidence-gated candidates with every required field and falsification result, or an evidence-backed
   fewer/zero-candidate result.
5. `CODEBASE_ARCHITECTURE_REVIEW.md` / `codebase_architecture_report` emitted as a report only, with
   `recommended_next_skill: null`, no source writes, and no automatic refactor. Any registered escalation
   target is only a human-visible offer requiring a separate user-authorized invocation, not a typed result
   value or automatic dispatch.

## Degraded paths

| Condition | Expected behavior |
|-----------|-------------------|
| Git is unavailable or history is shallow | Continue current-code review, set degraded history, omit churn/co-change claims, lower dependent confidence |
| A large file is the only signal | Investigate but do not create a candidate without friction/caller/test/contract evidence |
| Evidence contradicts a proposed boundary | Reject or downgrade the candidate after falsification |
| No candidate survives | Report zero candidates and the supporting evidence |
| A large module is cohesive, with a narrow interface and no leaked caller knowledge | Do not form a candidate from size alone; note depth evidence and omit the candidate |
| A candidate's only cited seam justification is mock substitution in tests | Classify dependency category `mock-only` and reject it as sole justification |
| A module only forwards calls and parameters with no added translation or policy | Run the deletion test, show nothing scatters on removal, and reject or downgrade the shallow pass-through |
| A module owns provider translation, retry, and idempotency policy behind a narrow contract with real callers | Classify dependency category `ports-and-adapters`, retain the candidate, and render both before and after models |
| A candidate's before/after model is not backed by observed callers, tests, or contract evidence | Reject or downgrade the candidate rather than retaining an unsupported model |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
