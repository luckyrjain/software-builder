# Convergence gates (normative)

Two independent gates must both pass, in the **same cycle**, against the **same pushed state**, before this
skill reports `converged: true`.

## Gate A — fresh codebase-architecture-review

A fresh run (not a re-check of old candidates) against `review_scope` must return:

- Zero retained `Strong` candidates.
- Zero retained `Worth exploring` candidates.
- Every retained `Speculative` candidate either resolved (`ALREADY_SATISFIED` / `REJECT` / `OUT_OF_SCOPE`,
  evidence recorded) or explicitly accepted as surviving with its evidence limit stated — never silently
  dropped.
- Zero candidates in the ledger with `disposition: null`.

codebase-architecture-review's own "**zero candidates** is valid and preferable to weak recommendations"
rule is inherited unchanged: a clean Gate A run with no findings at all is success, not a sign the review
was too shallow.

## Gate B — fresh production-readiness-review

A fresh run against the cumulative branch state must return `verdict: READY`, or `CONDITIONAL` with only
waivers the caller has explicitly accepted (never a waiver this skill invents on its own to force a green
verdict). Every `BLOCKER`/`HIGH`/`MEDIUM`/actionable finding is routed back through Disposition → Remediate
in the same cycle (see [workflow/converge.md](../workflow/converge.md)) before Gate A is re-checked.

## Anti-gaming

Never reach zero by:

- Reclassifying a real finding as `NOT_APPLICABLE`/`REJECT` without evidence.
- Narrowing `review_scope` mid-loop to dodge a hotspot.
- Skipping a `Speculative` candidate's grilling pass to avoid a contested disposition.
- Disabling or weakening a test to make loop-task-implementer's own review pass.
- Treating an unrelated stable-code refactor as required just to "use up" a cycle.

A valid terminal disposition requires evidence of a real problem (or its absence), not a scoring incentive.
Zero means a fresh, full-scope, evidence-based pass found nothing actionable — not that nothing was looked
for.

## Circuit breakers

See [SKILL.md § Circuit breakers](../SKILL.md#circuit-breakers) for the full list (`max_cycles`,
`max_candidates_per_cycle`, contested disposition, repeated batch escalation). Hitting one stops the loop
with `converged: false` and the current ledger state — never a fabricated `converged: true`.
