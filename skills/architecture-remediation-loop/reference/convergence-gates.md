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

A fresh run, only after this cycle's merge checkpoint clears (see
[workflow/converge.md § 1](../workflow/converge.md)) so the target is a real, single, merge-confirmed
`source_revision` — never an undefined multi-PR "cumulative" state — must return `verdict: READY`, or
`CONDITIONAL` with only waivers the caller has explicitly accepted (never a waiver this skill invents on
its own to force a green verdict). Every `BLOCKER`/`HIGH`/`MEDIUM`/actionable finding is routed back
through Disposition → Remediate in the same cycle before Gate A is re-checked.

`verdict: UNKNOWN` on any required dimension is **not** a pass and is not treated as equivalent to a
blocking finding either — production-readiness-review's own fail-closed contract means `UNKNOWN` reflects
an evidence gap, not a fixable candidate. Record which dimension is `UNKNOWN` against this cycle; if the
same dimension is still `UNKNOWN` on the next cycle's Gate B, the stall breaker below trips rather than
looping indefinitely on an unresolvable gap.

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

## Circuit breakers and pause states

See [SKILL.md § Circuit breakers](../SKILL.md#circuit-breakers) for the full list (`max_cycles`,
`max_candidates_per_cycle`, contested disposition, repeated batch escalation, no-material-progress). Hitting
one stops the loop with `converged: false` and the current ledger state — never a fabricated
`converged: true`. `stopped_reason` values:

| `stopped_reason` | Meaning | Resumable by re-invoking? |
|-------------------|---------|------------------------------|
| `AWAITING_MERGE` | This cycle's accepted batches have PRs open but not yet merged (§ Gate B) | Yes — re-check is idempotent, re-derived from each PR's own status |
| `NO_MATERIAL_PROGRESS` | Same finding or same Gate B dimension unresolved across two consecutive cycles | No — needs human/caller investigation first |
| `MAX_CYCLES_REACHED` | `max_cycles` exhausted with either gate still non-zero | Yes, with a raised `max_cycles` if genuinely justified |
| `MAX_CANDIDATES_REACHED` | `max_candidates_per_cycle` exhausted while candidates remain | Yes, next cycle picks up the deferral |
| `CONTESTED_DISPOSITION` | A candidate's disposition was contested twice without decisive evidence | No — needs human/caller investigation first |
| `REPEATED_BATCH_ESCALATION` | The same batch escalated from loop-task-implementer twice | No — needs human/caller investigation first |
| `SCOPE_EXCEEDS_AUTHORIZATION` | Required work exceeds what `repo_context` authorizes | No — needs re-authorization |

`AWAITING_MERGE` is the one pause state this skill expects to hit routinely for an unattended, non-merging
loop — same status as loop-task-implementer's own `HUMAN_ACTION_REQUIRED`, just scoped to a whole cycle
instead of one task. It deliberately has **no wait-budget circuit breaker**: like `HUMAN_ACTION_REQUIRED`,
it is bounded by real-world human action, not by this skill's own budgets, and re-invoking while still
unmerged is cheap — the merge check is re-derived fresh from each PR's own status every time, so repeated
re-invocation neither accumulates cost nor risks acting on stale state. A caller who wants their own
wait-budget policy enforces it at the invocation layer (e.g. a scheduler deciding how often to re-invoke),
the same way backlog-runner's `deadline` is a *caller* config value, not something loop-task-implementer
itself tracks.
