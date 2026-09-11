# Examples — invocation patterns

Conventions: [examples-conventions](../../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|--------------------|----------|
| 1 | `review_scope: services/billing`, `repo_context: <repo>` | Inputs → Discover finds 4 candidates → Disposition (3 ACCEPT, 1 REJECT) → Remediate batches the 3 → Converge: Gate B clean, fresh Gate A clean → `converged: true` |
| 2 | Same scope, cycle 1 leaves 2 candidates `Speculative` and unresolved | Disposition grills them; if evidence resolves them, they leave the ledger; if not, they carry into cycle 2's ledger with their evidence limit recorded, never silently dropped |
| 3 | Gate B (production-readiness-review) finds one cross-candidate `HIGH` finding after cycle 1's batches merge-ready | Converge opens a new ledger row (`source: holistic`), dispositions and remediates it in the same cycle, then re-runs Gate A fresh |
| 4 | A candidate is a public API signature change | Classified large/high-risk in [pr-batching-policy.md](reference/pr-batching-policy.md) → dedicated batch, own PR |
| 5 | Three candidates are all naming/dead-code cleanup in the same package | Grouped into one batch, one PR, one coherent architectural story |
| 6 | `max_cycles: 3` reached, Gate A still finds 1 `Worth exploring` candidate | Converge reports `converged: false`, `stopped_reason: MAX_CYCLES_REACHED`, that row still open in the ledger |
| 7 | A candidate is contested twice by engineering-decision-discovery without decisive evidence | Circuit breaker trips — loop stops for that candidate, `converged: false`, contested row recorded with both grilling passes |
| 8 | A batch's loop-task-implementer invocation is `ESCALATED` twice in a row | Circuit breaker trips — that batch's candidates marked `BLOCKED`, loop stops rather than retrying a third time |
| 9 | Caller asks for "just review the architecture, don't fix anything" | **Wrong skill** → **codebase-architecture-review** directly (no implementation intent) |
| 10 | Caller says "implement ticket ABC-123" | **Wrong skill** → **loop-task-implementer** directly (one already-scoped task, not a discovery loop) |
| 11 | Caller asks "is PR !482 production ready?" | **Wrong skill** → **production-readiness-review** directly (one PR's own verdict, not a loop) |

---

### Scenario: First cycle, clean convergence

**Caller:** `review_scope: services/billing`, `repo_context: <repo, base branch>`

**Agent:**

1. Inputs — both required fields present, `max_cycles` defaults to 5
2. Discover — codebase-architecture-review retains 4 candidates (2 Strong, 1 Worth exploring, 1
   Speculative)
3. Disposition — engineering-decision-discovery resolves 3 to `ACCEPT`, 1 (the Speculative one) to
   `ALREADY_SATISFIED` with evidence
4. Remediate — the 3 accepted candidates batch into 2 PRs (1 dedicated for an interface change, 1 grouped
   for 2 cohesive cleanups); loop-task-implementer opens both, `HUMAN_ACTION_REQUIRED`
5. Converge — production-readiness-review returns `READY`; a fresh codebase-architecture-review pass
   against the new state retains zero candidates
6. `architecture_remediation_report` — `converged: true`, `cycles_run: 1`, 2 PR links, full ledger

**Expected fragment:**

```
converged: true
cycles_run: 1
gate_a_status: PASS
gate_b_status: PASS
candidates: { total: 4, by_disposition: { ACCEPT: 3, ALREADY_SATISFIED: 1 }, open: 0 }
batches:
  - batch_id: b1
    candidate_ids: [c1]
    classification: dedicated
    pull_request_url: https://github.com/acme/backend/pull/501
    outcome: COMPLETED
  - batch_id: b2
    candidate_ids: [c2, c3]
    classification: grouped
    pull_request_url: https://github.com/acme/backend/pull/502
    outcome: COMPLETED
```

---

### Scenario: Cross-skill — wrong entry point

**Caller:** "Just tell me the architecture friction in `payments/`, I'll decide what to do with it myself."

**Agent:** No implementation intent — routes to **codebase-architecture-review** directly, per its own
`SKILL.md`.
