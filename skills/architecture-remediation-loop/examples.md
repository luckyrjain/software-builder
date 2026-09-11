# Examples — invocation patterns

Conventions: [examples-conventions](../../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|--------------------|----------|
| 1 | `review_scope: services/billing`, `repo_context: <repo>`, batch PRs merged between invocation 1 and 2 | Invocation 1: Inputs → Discover finds 4 candidates → Disposition (3 ACCEPT, 1 REJECT) → Remediate batches the 3 → Converge stops at `AWAITING_MERGE`. Invocation 2 (after merge): Converge confirms merge → Gate B clean → fresh Gate A clean → `converged: true` |
| 2 | Same scope, cycle 1 leaves 2 candidates `Speculative` and unresolved | Disposition grills them; if evidence resolves them, they leave the ledger; if not, they carry into cycle 2's ledger with their evidence limit recorded, never silently dropped |
| 3 | Gate B (production-readiness-review) finds one cross-candidate `HIGH` finding once cycle 1's batches are merge-confirmed | Converge opens a new ledger row (`source: holistic`), dispositions and remediates it in the same cycle, then re-runs Gate A fresh |
| 3b | Cycle 1's batch PR is still open when Converge runs | Merge checkpoint fails — `stopped_reason: AWAITING_MERGE`, Gate A/B never invoked; re-invoking after the merge resumes the same cycle |
| 3c | Cycle 2 rediscovers a candidate matching a merge-confirmed cycle-1 row (same root cause) | Not `DUPLICATE` — new row, `source: regression`, `regressed_from` set, dispositioned fresh |
| 4 | A candidate is a public API signature change | Classified large/high-risk in [pr-batching-policy.md](reference/pr-batching-policy.md) → dedicated batch, own PR |
| 5 | Three candidates are all naming/dead-code cleanup in the same package | Grouped into one batch, one PR, one coherent architectural story |
| 6 | `max_cycles: 3` reached, Gate A still finds 1 `Worth exploring` candidate | Converge reports `converged: false`, `stopped_reason: MAX_CYCLES_REACHED`, that row still open in the ledger |
| 7 | A candidate is contested twice by engineering-decision-discovery without decisive evidence | Circuit breaker trips — loop stops for that candidate, `converged: false`, contested row recorded with both grilling passes |
| 8 | A batch's loop-task-implementer invocation is `ESCALATED` twice in a row | Circuit breaker trips — that batch's candidates marked `BLOCKED`, loop stops rather than retrying a third time |
| 9 | Caller asks for "just review the architecture, don't fix anything" | **Wrong skill** → **codebase-architecture-review** directly (no implementation intent) |
| 10 | Caller says "implement ticket ABC-123" | **Wrong skill** → **loop-task-implementer** directly (one already-scoped task, not a discovery loop) |
| 11 | Caller asks "is PR !482 production ready?" | **Wrong skill** → **production-readiness-review** directly (one PR's own verdict, not a loop) |

---

### Scenario: First cycle, clean convergence (spans two invocations)

**Caller:** `review_scope: services/billing`, `repo_context: <repo, base branch>`

**Agent — invocation 1:**

1. Inputs — both required fields present, `max_cycles` defaults to 5
2. Discover — codebase-architecture-review retains 4 candidates (2 Strong, 1 Worth exploring, 1
   Speculative)
3. Disposition — engineering-decision-discovery resolves 3 to `ACCEPT`, 1 (the Speculative one) to
   `ALREADY_SATISFIED` with evidence
4. Remediate — the 3 accepted candidates batch into 2 PRs (1 dedicated for an interface change, 1 grouped
   for 2 cohesive cleanups); loop-task-implementer opens both, `HUMAN_ACTION_REQUIRED`
5. Converge — merge checkpoint finds both PRs still open → stops, `stopped_reason: AWAITING_MERGE`

**Expected fragment (invocation 1):**

```
converged: false
cycles_run: 1
stopped_reason: AWAITING_MERGE
merge_attempted: false
batches:
  - batch_id: b1
    candidate_ids: [c1]
    classification: dedicated
    pull_request_url: https://github.com/acme/backend/pull/501
    merged: false
    outcome: COMPLETED
  - batch_id: b2
    candidate_ids: [c2, c3]
    classification: grouped
    pull_request_url: https://github.com/acme/backend/pull/502
    merged: false
    outcome: COMPLETED
```

**Between invocations:** a human/caller merges PR #501 and #502.

**Agent — invocation 2 (same `review_scope`/`repo_context`):**

6. Converge — merge checkpoint confirms both PRs merged (`merge_confirmed: true` on both rows); Gate B
   (production-readiness-review) returns `READY`; a fresh codebase-architecture-review pass against the
   now-merged state retains zero candidates → Gate A passes
7. `architecture_remediation_report` — `converged: true`, `cycles_run: 1`, 2 PR links, full ledger

**Expected fragment (invocation 2):**

```
converged: true
cycles_run: 1
gate_a_status: PASS
gate_b_status: PASS
merge_attempted: false
candidates: { total: 4, by_disposition: { ACCEPT: 3, ALREADY_SATISFIED: 1 }, open: 0 }
batches:
  - batch_id: b1
    candidate_ids: [c1]
    classification: dedicated
    pull_request_url: https://github.com/acme/backend/pull/501
    merged: true
    outcome: COMPLETED
  - batch_id: b2
    candidate_ids: [c2, c3]
    classification: grouped
    pull_request_url: https://github.com/acme/backend/pull/502
    merged: true
    outcome: COMPLETED
```

---

### Scenario: Cross-skill — wrong entry point

**Caller:** "Just tell me the architecture friction in `payments/`, I'll decide what to do with it myself."

**Agent:** No implementation intent — routes to **codebase-architecture-review** directly, per its own
`SKILL.md`.
