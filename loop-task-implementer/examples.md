# Examples

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | User says | Resolves to | Notes |
|---|-----------|--------------|-------|
| 1 | "Use loop-task-implementer to complete the next task." | Orchestrator: discover policy → select task → dispatch Builder | Happy path |
| 2 | "Implement issue 42, review it deeply, fix findings, and open a PR." | Full loop: Builder → Lens A/B → adjudicate → portable evidence → lifecycle gate → PR/readiness | Single task, explicit source |
| 3 | "Work through these tasks one by one and stop when each is ready to merge." | Repeats the full loop per task; stops at `HUMAN_ACTION_REQUIRED` each time | Multi-task queue |
| 4 | "Take this PR through independent review and remediation." | Uses the existing branch/PR as the change under review; still rebuilds lifecycle state before readiness | PR already exists |
| 5 | "Resume the loop-task-implementer workflow for the current branch." | Orchestrator re-derives state from the branch/PR rather than trusting prior chat | Resume, not restart |
| 6 | "Run only reviewer Lens A on this change." | Single-lens Reviewer dispatch; increment Lens A `review_generation`, adjudicate, and normalize evidence, but do not claim full lifecycle readiness without Lens B | Scoped review |
| 7 | "Adjudicate the review findings instead of blindly fixing them." | Orchestrator runs adjudication explicitly before any remediation dispatch | Explicit adjudication |
| 8 | "Size my Kubernetes deployment for cost." | **Wrong skill** — route to **k8s-overprovisioning-datadog**, not loop-task-implementer | Wrong-skill row |

## Scenario: Single task, clean on first pass

**User:** "Implement issue 42 — add a rate limit to the login endpoint — and open a PR."

**Agent:**
1. Orchestrator discovers policy: default branch `main`, 1 required approval, CI required, autonomous merge **not** authorized.
2. Dispatches a fresh Builder session with the task text and acceptance criteria.
3. Independently verifies the resulting branch/PR/head and rebuilds the current shared `change_identity`, current requirements reference, and exact-head third-party branch-change check.
4. Dispatches Lens A in a fresh context. On return, increments Lens A `review_generation` to `1`, adjudicates the result, then creates valid defect-free portable `review_evidence` for the current identity.
5. Dispatches Lens B against the same current identity. On return, increments Lens B `review_generation` to `1`, adjudicates, and creates valid defect-free portable evidence.
6. Refreshes required approvals/threads/integration state, verifies authoritative CI is green for the exact current head, and refreshes the third-party check for that same head.
7. Resolves the actual skill root, selects a Python 3 interpreter, and on Unix/macOS runs `python3 "<skill_root>/scripts/validate_loop_lifecycle.py" --state "<state.json>"`; exit `0` establishes verified readiness.
8. Stops at verified readiness because autonomous merge is not authorized and reports the exact human action.

**Expected fragments:**

```
Policy: main (protected) · 1 required approval · CI required · autonomous_merge_authorized: false
Lens A: CLEAN · review_generation: 1 · evidence: FRESH
Lens B: CLEAN · review_generation: 1 · evidence: FRESH
Lifecycle gate: PASS — exit 0
Completion state: HUMAN_ACTION_REQUIRED — approve and merge PR #128 manually
```

## Scenario: One accepted Lens A finding, fixed and reverified

**User:** "Work through these tasks one by one and stop when each is ready to merge."

**Agent:**
1. Task 1 is implemented; Lens A generation `1` returns `FINDINGS` — one `PROPOSED_BLOCKING` finding (`AUTHZ-001`: missing authorization check on a new admin route).
2. Orchestrator adjudicates: evidence is concrete and an enforced repository rule is violated → `ACCEPTED`.
3. Dispatches Builder remediation with only the accepted finding.
4. Builder responds `FIXED` with a regression test. The new content changes `change_identity`, so Lens A generation-1 evidence is invalidated and any isolation exception is cleared.
5. Dispatches Lens B generation `1` against the remediated current identity; Lens B is CLEAN and portable evidence is normalized.
6. Reruns the invalidated Lens A against that same current identity; Lens A becomes generation `2` and returns CLEAN. Any degraded-isolation waiver would have to be newly authorized for generation `2`.
7. Refreshes current-head repository gates/CI and runs the lifecycle validator with the resolved skill-root Python 3 command. Only exit `0` permits verified readiness.

**Expected fragments:**

```
AUTHZ-001 [ACCEPTED] — missing authorization check on POST /admin/users (Lens A generation 1)
Builder response: FIXED — added @RequireRole(ADMIN) + regression test test_admin_route_requires_role
Lens B generation 1: CLEAN · Lens A generation 2: CLEAN · same current change_identity
Lifecycle gate: PASS — exit 0
```

## Scenario: Same-head degraded-isolation rerun needs a new waiver

**User:** "Rerun Lens A once more before I approve it."

**Agent:**
1. Lens A generation `1` was `NOT_ISOLATED` and an authorized human exception was recorded for generation `1` and the current identity.
2. The code is unchanged, but the requested reviewer rerun is still a new review result, so Lens A increments to generation `2` and replaces generation-1 evidence.
3. The Orchestrator clears the prior exception fields. If generation `2` is also `NOT_ISOLATED`, the generation-1 human exception is stale and cannot satisfy readiness.
4. Readiness remains blocked until a new authorized human exception is recorded for the same identity **and generation `2`**, or an isolated rerun succeeds.

**Expected fragments:**

```
Lens A: NOT_ISOLATED · review_generation: 2
Isolation exception: STALE — prior exception bound to review_generation 1
Lifecycle gate: BLOCKED — current generation requires fresh authorization
```

## Scenario: Contested finding escalates

**User:** "Run only reviewer Lens B on this change."

**Agent:**
1. Lens B returns a reviewer result, increments its `review_generation`, and proposes a blocking finding: a changed API response field is not backward compatible.
2. Builder rebuts with evidence: the field was already optional and unused by any consumer per a grep of one-hop callers.
3. Orchestrator classifies the rebuttal `NEEDS_EVIDENCE` — insufficient to fully reject.
4. Reviewer is asked for one evidence refinement; Builder is asked for one more reproduction.
5. Same finding is contested a second time with no new decisive evidence from either side.
6. Orchestrator escalates rather than picking a side. A single-lens run does not establish full lifecycle readiness.

**Expected fragments:**

```
CONTRACT-004 [CONTESTED, round 2] — response field `legacy_id` removed
Escalation: required_human_decision — confirm no external consumer depends on `legacy_id`
```

## Scenario: Degraded path — no CI visibility

**User:** "Use loop-task-implementer to implement this task." (host agent has no CI integration configured)

**Agent:**
1. Orchestrator's policy discovery finds no way to observe required-check status for the exact head commit (`reference/mcp-capabilities.md` — CI status capability absent).
2. Implementation and both review lenses may still run normally; each result gets its own `review_generation` and portable evidence.
3. At the lifecycle gate, authoritative current-head CI cannot be proven. The validator therefore cannot return lifecycle-success exit `0` for readiness.
4. The Orchestrator stops even if the user has broadly authorized autonomous merge; missing required CI visibility fails closed.

**Expected fragments:**

```
Degraded: no CI status source configured — cannot verify required checks at a1b2c3d
Lifecycle gate: BLOCKED — authoritative current-head CI unavailable
Completion state: HUMAN_ACTION_REQUIRED — verify CI manually before merging PR #131
```

## Scenario: Oversized change stops before lifecycle-clean review

**User:** "Take this PR through independent review and remediation — it's a big one, might need a deeper look."

**Agent:**
1. The Orchestrator measures the current diff at 55 files, above the configured 40-file hard stop, and the user has not explicitly authorized a larger review.
2. It does **not** claim both loop-task-implementer lenses are clean and does not run to verified readiness on a knowingly oversized partial review.
3. It stops and asks to split the task/change, or—when the existing MR specifically needs a deeper external review—hands the MR to **pr-review** without representing that handoff as lifecycle approval.

**Expected fragments:**

```
Circuit breaker: diff hard stop exceeded — 55 files > 40
Lifecycle state: NOT_READY — full loop review not completed
Handoff → pr-review: review MR !128 independently; do not treat this handoff as loop-task-implementer approval
```
