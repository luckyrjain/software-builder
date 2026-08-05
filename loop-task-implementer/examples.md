# Examples

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | User says | Resolves to | Notes |
|---|-----------|--------------|-------|
| 1 | "Use loop-task-implementer to complete the next task." | Orchestrator: discover policy → select task → dispatch Builder | Happy path |
| 2 | "Implement issue 42, review it deeply, fix findings, and open a PR." | Full loop: Builder → Lens A/B → adjudicate → remediate → PR | Single task, explicit source |
| 3 | "Work through these tasks one by one and stop when each is ready to merge." | Repeats the full loop per task; stops at `HUMAN_ACTION_REQUIRED` each time | Multi-task queue |
| 4 | "Take this PR through independent review and remediation." | Skips Builder dispatch — uses existing branch/PR as the diff under review | PR already exists |
| 5 | "Resume the loop-task-implementer workflow for the current branch." | Orchestrator re-derives state from the branch/PR rather than trusting prior chat | Resume, not restart |
| 6 | "Run only reviewer Lens A on this change." | Single-lens Reviewer dispatch, no adjudication loop unless findings appear | Scoped review |
| 7 | "Adjudicate the review findings instead of blindly fixing them." | Orchestrator runs adjudication explicitly before any remediation dispatch | Explicit adjudication |
| 8 | "Size my Kubernetes deployment for cost." | **Wrong skill** — route to **k8s-overprovisioning-datadog**, not loop-task-implementer | Wrong-skill row |

## Scenario: Single task, clean on first pass

**User:** "Implement issue 42 — add a rate limit to the login endpoint — and open a PR."

**Agent:**
1. Orchestrator discovers policy: default branch `main`, 1 required approval, CI required, autonomous merge **not** authorized.
2. Dispatches a fresh Builder session with the task text and acceptance criteria.
3. Independently verifies the resulting branch/PR/head commit.
4. Dispatches Lens A and Lens B in separate fresh sessions against the same diff.
5. Both return `CLEAN` — no accepted findings.
6. Verifies CI is green for the exact head commit.
7. Stops at verified readiness (autonomous merge not authorized) and reports the human action.

**Expected fragments:**

```
Policy: main (protected) · 1 required approval · CI required · autonomous_merge_authorized: false
```

```
Lens A (Safety and State): CLEAN — reviewed a1b2c3d
Lens B (Contracts and Operations): CLEAN — reviewed a1b2c3d
Completion state: HUMAN_ACTION_REQUIRED — approve and merge PR #128 manually
```

## Scenario: One accepted finding, fixed and reverified

**User:** "Work through these tasks one by one and stop when each is ready to merge."

**Agent:**
1. Task 1 implemented; Lens A returns `FINDINGS` — one `PROPOSED_BLOCKING` finding (`AUTHZ-001`:
   missing authorization check on a new admin route).
2. Orchestrator adjudicates: evidence is concrete, an enforced repository rule is violated →
   `ACCEPTED`.
3. Dispatches Builder remediation with only the accepted finding.
4. Builder responds `FIXED` with a regression test; new head commit recorded.
5. Both lenses rerun against the new fingerprint — both `CLEAN`.
6. Task marked ready; Orchestrator selects the next eligible task.

**Expected fragments:**

```
AUTHZ-001 [ACCEPTED] — missing authorization check on POST /admin/users (Lens A)
Builder response: FIXED — added @RequireRole(ADMIN) + regression test test_admin_route_requires_role
Re-review at b4c5d6e: Lens A CLEAN · Lens B CLEAN
```

## Scenario: Contested finding escalates

**User:** "Run only reviewer Lens B on this change."

**Agent:**
1. Lens B proposes a blocking finding: a changed API response field is not backward compatible.
2. Builder rebuts with evidence: the field was already optional and unused by any consumer per a
   grep of one-hop callers.
3. Orchestrator classifies the rebuttal `NEEDS_EVIDENCE` — insufficient to fully reject.
4. Reviewer is asked for one evidence refinement; Builder is asked for one more reproduction.
5. Same finding is contested a second time with no new decisive evidence from either side.
6. Orchestrator escalates rather than picking a side.

**Expected fragments:**

```
CONTRACT-004 [CONTESTED, round 2] — response field `legacy_id` removed
Escalation: required_human_decision — confirm no external consumer depends on `legacy_id`
```

## Scenario: Degraded path — no CI visibility

**User:** "Use loop-task-implementer to implement this task." (host agent has no CI integration configured)

**Agent:**
1. Orchestrator's policy discovery finds no way to observe required-check status for the exact head
   commit (`reference/mcp-capabilities.md` — CI status capability absent).
2. Implementation and both review lenses still run normally — CI visibility only gates the final
   merge decision, not implementation or review.
3. At the completion gate, the Orchestrator stops even if the user has broadly authorized
   autonomous merge, because "authoritative required checks are green" cannot be verified.

**Expected fragments:**

```
Degraded: no CI status source configured — cannot verify required checks at a1b2c3d
Completion state: HUMAN_ACTION_REQUIRED — verify CI manually before merging PR #131
```

## Scenario: Cross-skill handoff to pr-review

**User:** "Take this PR through independent review and remediation — it's a big one, might need a deeper look."

**Agent:**
1. Both lenses run and return `CLEAN`, but the diff is unusually large (55 files) and touches a
   payments service the Builder is not confident it fully understands.
2. Rather than rubber-stamping, the Orchestrator recommends handing the same MR to **pr-review** for
   its deeper domain-aware checklist before merge.

**Expected fragments:**

```
**Handoff → pr-review**
- Service: payments-api
- Evidence: MR !128, both loop-task-implementer lenses CLEAN, 55 files changed
- Ask: "Review MR !128 for task TASK-42 — large diff, want the deeper pr-review checklist before merge"
```
