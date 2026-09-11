# Smoke test — expected minimal output

Run after install or any edit to this skill. Use a repository with codebase-architecture-review,
engineering-decision-discovery, module-design, loop-task-implementer, and production-readiness-review all
already working individually first — confirm each via its own `reference/smoke-test.md`.

Conventions: [smoke-test-conventions](../../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> `review_scope: <a small bounded subdirectory known to have at least one real friction point>`,
> `repo_context: <repo, base branch, repository instructions>`, `max_cycles: 2`,
> `max_candidates_per_cycle: 3`

## Expected first output

Inputs resolved and announced, then Discover invoking codebase-architecture-review before anything else
runs — no candidate is grilled, designed, or implemented before it exists in the ledger with evidence.

## A correct minimal output contains

1. **At least one ledger row with a terminal disposition** reached via engineering-decision-discovery, not
   assumed from the architecture report's confidence label alone.
2. **`autonomous_merge_authorized` never `true`** in any loop-task-implementer invocation — verify by
   inspecting the invocation, not just the summary.
3. **A fresh codebase-architecture-review re-run** after the first cycle's batches complete, not a re-check
   of the same candidate list.
4. **`architecture_remediation_report` produced** with `converged`, `cycles_run`, and per-batch PR links (or
   `converged: false` with `stopped_reason: MAX_CYCLES_REACHED` at `max_cycles: 2`).

## Pass criteria

- No PR is ever merged by this skill.
- No candidate reaches Remediate without a terminal `ACCEPT`/`ACCEPT_WITH_MODIFICATION` disposition.
- A large/high-risk candidate never lands in a grouped batch (§ [pr-batching-policy.md](pr-batching-policy.md)).
- `max_candidates_per_cycle` is enforced even when codebase-architecture-review retains more.

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| codebase-architecture-review retains zero candidates on cycle 1 | Gate A is already clean; Converge still runs Gate B once before reporting `converged: true` |
| A candidate is contested twice by engineering-decision-discovery without decisive evidence | Circuit breaker trips — loop stops, `converged: false`, contested row left open in the report |
| loop-task-implementer escalates the same batch twice | Circuit breaker trips — that batch's candidates marked `BLOCKED`, loop stops for review |
| `max_cycles` reached with Gate B still non-zero | Report emitted with `converged: false`, `stopped_reason: MAX_CYCLES_REACHED`, current ledger state intact |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
