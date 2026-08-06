# Precedence (when stop/invalidation conditions overlap)

`orchestrator.md` defines several independent conditions that each say "stop," "pause," or "block
completion" — circuit breakers (§3, §9, §10, §11, §15), base-update invalidation (§14), third-party
branch-change invalidation (§5, §16), the `NOT_ISOLATED` lens block (§7, §17), unresolved
security-sensitive `NEEDS_EVIDENCE` (§9, §17), and the completion gates themselves (§17). Each section
was written for the case where it fires alone. This file says what to do when more than one is true at
the same dispatch, adjudication, or gate check — load it whenever that happens.

## Why a ranking, not just "handle each"

Some of these conditions describe the **content under review being untrustworthy** (the head commit
moved out from under you, or the safety verdict on it was never actually independent). Others describe
**the process being too expensive or stuck to continue** (a budget or retry counter exceeded). A
resource-exhaustion stop is meaningless applied to content that has already been superseded or was
never validly reviewed — you would be escalating about, or completing against, a fingerprint that no
longer has an authoritative meaning. Trustworthiness of the current state must therefore be resolved
before cost/loop conditions are acted on, and both must be resolved before the completion gates (§17)
are evaluated at all, since §17 is an aggregate check that re-reads the outcome of every condition
below it.

## Rank table (highest wins)

| Rank | Condition | Orchestrator section | Why it outranks lower ranks |
|------|-----------|----------------------|------------------------------|
| **1** | Unrecognized/third-party branch change | §5, §16 | Every lower-ranked condition is evaluated "for the current fingerprint" (§7, §10, §14, §17). If the head moved without attribution, that fingerprint is void — nothing computed against it (a budget counter, an isolation status, a completion gate) is a meaningful answer until the change is classified. §16 runs this check **before** every dispatch, adjudication, CI check, and final action — textually the first gate at every decision point. |
| **2** | Security-sensitive isolation/evidence invalidation (`NOT_ISOLATED` lens; unresolved `NEEDS_EVIDENCE` on auth/authz/secrets/trust-boundary) | §7, §9 (NEEDS_EVIDENCE resolution), enforced at §17 | The fingerprint itself is fine (no unrecognized change — rank 1 is clear); what's untrustworthy or incomplete is the safety **verdict** about it. §17 treats both as equivalent to an open `ACCEPTED` finding regardless of what the lens or adjudication otherwise reported — they cannot be routed around by a budget escalation, and no amount of remaining circuit-breaker budget substitutes for the missing independent review. |
| **3** | Base-branch-update invalidation (§14) / CI-caused invalidation (§15) | §14, §15 | A legitimate, first-party content change (base-branch integration, or a CI-diagnosed PR defect), not an unrecognized actor (rank 1) and not a gap in the review process itself (rank 2). Handled by the ordinary "invalidate both lens approvals, rerun both lenses" loop rather than a pause-and-escalate. It still outranks rank 4 because the dirty-review and remediation counters (§10, §11) are scoped per fingerprint/per finding — there is nothing meaningful for a circuit breaker to count against until the lenses have rerun on the now-valid fingerprint. |
| **4** | Circuit breakers / budget & size guards (§3, contested-twice in §9, `dirty_review_count` max in §10, escalate list in §11, CI-poll budget in §15) | §3, §9, §10, §11, §15 | These stop the workflow because continuing is too expensive or looping, not because the current state can't be trusted. They must still be evaluated and reported (see Composition below) even when a higher-ranked condition also fired, but they never preempt a correctness invalidation — there is no value in spending recorded budget adjudicating a stale or unverified fingerprint. |
| **5** | Completion gates (§17), in aggregate | §17 | Not an independent competing condition — it is the final AND across ranks 1-4 plus the last-mile checks (authoritative checks green, approvals present, threads resolved, autonomous merge authorized). §17 explicitly re-checks "no circuit breaker is active" and both lenses' `isolation_status`, so it can only be reached, and can only pass, once ranks 1-4 are already clear for the current fingerprint. |

Lower ranks never override higher ranks: a clean §17 evaluation is not possible while a rank 1-4
condition is still open, and resolving a rank 4 circuit breaker does not retroactively clear a rank 1-3
invalidation that was true at the same time.

## Composition: most conditions record together, one condition acts first

These are not mutually exclusive alternatives — the §19 escalation report has separate fields for
`accepted_findings`, `contested_findings`, `needs_evidence_findings`, `lens_isolation`,
`third_party_changes`, and `budget_consumed` in the same payload specifically because more than one of
these can be true at once and all of them belong in one report, not a series of separate escalations.

When several conditions are true at the same dispatch/adjudication/gate check:

1. Take the **rank 1 action** first (§16: pause, record actor and new commits, recompute diff,
   invalidate prior lens approvals, decide whether the change belongs to the task) before evaluating or
   acting on anything ranked lower — a lower-ranked condition evaluated against the stale fingerprint may
   no longer even apply once the change is classified (e.g., an "implementation alternates between prior
   fingerprints" circuit breaker, §11, can dissolve once the alternation is attributed to a third-party
   push rather than the Builder).
2. Re-evaluate ranks 2-4 against the reclassified fingerprint. Record every condition still true in the
   same §19 report — `escalation_reason` names the **highest-ranked** condition still open as the root
   cause; the rest are listed as contributing context in the same report (`needs_evidence_findings`,
   `budget_consumed`, etc.) rather than triggering separate escalations.
3. Do not evaluate §17 completion gates until ranks 1-4 are clear (or explicitly escalated with a
   recorded human decision, per §9 NEEDS_EVIDENCE resolution and §11).

## Common conflicts

| Simultaneous conditions | Resolution |
|---|---|
| Third-party push detected (§16) while `dirty_review_count` is already at the §3 maximum | Pause and reclassify the push first (rank 1). Only after the diff is reclassified, re-check whether the dirty-review count still applies to the reclassified fingerprint — invalidated approvals from the push do not themselves add to `dirty_review_count` (§10: a review is dirty only when a blocking finding is *accepted*), but if the breaker is still exceeded, escalate with both the third-party change and the budget state in one §19 report. |
| Lens A `NOT_ISOLATED` on a security-sensitive diff (§7) while an unrelated finding has hit its `contested` limit (§9) | Both are recorded. Resolving the contested-finding escalation (rank 4) does not unblock completion — §17 still blocks on `isolation_status` (rank 2) until a genuinely isolated primitive re-runs Lens A or a human explicitly accepts the degraded review. |
| A base-branch update requires both lenses to rerun (§14) while the dispatched rerun session exceeds its response-wait budget (§3, §15) | The session-wait circuit breaker (rank 4) fires and is escalated on its own facts. The base-update rerun obligation (rank 3) does not disappear — once the stuck session is resolved (new session, human intervention), both lenses must still rerun against the updated base before §17 is re-evaluated. |
| Unresolved `NEEDS_EVIDENCE` on a trust-boundary finding (§9) while the review-size hard stop is exceeded (§3) | Escalate both in one report. `escalation_reason` names the `NEEDS_EVIDENCE` gap (rank 2) as root cause, since it independently blocks §17 regardless of how the size question is resolved; the size/split decision (rank 4) is recorded as contributing context requiring its own human call. |

## When uncertain

If it is unclear whether two conditions are truly simultaneous (e.g., a push might have landed just
before or just after a circuit breaker was recorded), treat them as simultaneous and apply rank 1's
pause-and-reclassify action first — re-reading the current head (§16) is cheap and never wrong to do
before continuing, whereas skipping it risks acting on a fingerprint that has already moved.
