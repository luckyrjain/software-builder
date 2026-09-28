# Engineering Decision Record — A1: certified live-eval baseline for loop-task-implementer

**Scope:** Gap-backlog ticket A1 (`docs/superpowers/plans/2026-09-18-autonomous-engineer-gap-backlog.md:32`) —
"Certified live-eval baseline for `loop-task-implementer`: record 5-10 real tickets, track CI pass, review
rounds, tokens, time, merge outcome... Cases live under `evals/live/`, marked certified, run via the
existing harness; a results table exists; regression threshold documented." Flagged by the 2026-09-24
reanalysis as not executable as written — `evals/live/`'s harness is confirmed mock-tool-only and
structurally cannot produce real CI status, review rounds, or a merge outcome.

## Decision tree

| # | Question | Depends on | Status | Selected option |
|---|----------|------------|--------|------------------|
| 1 | Does A1 stay its own ticket, or fold into F3 (the same reanalysis doc's repo-wide, related-but-distinct fixture-staleness ticket)? | — | resolved | Keep A1 separate, scoped to `loop-task-implementer` |
| 2 | Given the harness constraint, what should A1's actual mechanism be? | 1 | resolved | Retroactively formalize this session's already-real runs — no new harness |
| 3 | Is 6 real runs (this session's actual count) an acceptable baseline size against the original 5-10 target? | 2 | resolved | 6 is enough — don't manufacture more tickets to hit a round number |
| 4 | What do "certified" and "regression threshold" mean, given neither has any existing definition anywhere in this repo? | 2 | resolved | "Certified" = owner sign-off on the results table; "regression threshold" = a binary gate (CI green + both review lenses clean before merge), not a numeric score |

## Resolved decisions (with rationale, as recommended and as chosen)

1. **A1 vs. F3 — kept separate.** F3's own stated direction (make golden-fixture staleness checking count
   never-refreshed fixtures; put a live-case minimum on analysis skills wired to an executor) addresses
   repo-wide fixture hygiene across all 50 skills. A1's real purpose — a track record for
   `loop-task-implementer` specifically — is what 8 other tickets (B1-B8, C7, D4) actually depend on. Folding
   into F3 risked leaving that dependency structurally unaddressed. User confirmed the recommendation.
2. **Mechanism — retroactive formalization, no new harness.** The mock-tool live-eval harness (confirmed by
   direct read of `docs/evals/LIVE-HARNESS.md` and `scripts/evals/live_run.py`) cannot execute real git/CI/
   GitHub operations by design — building a "real-work runner" would be new, unbudgeted infrastructure, and
   rewording down to mock-only cases would satisfy the letter of the ticket while abandoning its actual
   purpose. This session already produced 6 genuine end-to-end executions (real Builder/Reviewer isolation,
   real CI, real PRs, real merges) with zero marginal cost to capture. User confirmed the recommendation.
3. **Baseline size — 6, not 5-10.** The original range assumed tickets of roughly uniform, modest cost;
   in practice this session's tickets varied hugely (a 2-file doc-guarded-import fix vs. a 4-round,
   6-persona-review shared-registry-parse-path change). 6 spans that real variance — a build, a reversal, two
   core-executor changes, one high-criticality shared-code change, and a small follow-up. User confirmed the
   recommendation over commissioning more tickets to hit a round number.
4. **"Certified"/"regression threshold" — owner sign-off + binary gate.** Neither term had any existing
   schema, script, or documented meaning anywhere in this repo (confirmed by grep — the phrases exist only
   in A1's own original acceptance-criteria line). Inventing a numeric eval score for a fundamentally
   subjective, human/LLM-judged process would be manufactured precision. User confirmed the recommendation:
   "certified" is the owner personally reviewing and signing off on the results table; "regression threshold"
   is the same pass/fail bar every one of the 6 runs already cleared (CI green, both review lenses clean
   before merge) — restated as the standing bar for anything added to this baseline later, not a new metric.

## Unresolved decisions

None — all 4 frontier nodes resolved in this session.

## Rejected alternatives

- Folding A1 into F3 entirely (Node 1) — would leave B1-B8/C7/D4's specific dependency unaddressed.
- Building new real-work eval-runner infrastructure (Node 2) — real engineering effort with no immediate
  need, given the data already exists.
- Rewording A1 down to mock-tool-only cases (Node 2) — achievable but abandons the ticket's actual purpose.
- Running additional tickets before calling the baseline complete (Node 3) — no evidence 6 is
  unrepresentative; would delay closing a ticket that 8 others depend on for no clear benefit.
- Inventing a numeric regression-score threshold (Node 4) — no existing scoring infrastructure to build on,
  and the process being measured (adversarial multi-persona review, human merge authorization) isn't
  naturally numeric.

## Limitations

- The "baseline" is a retroactive compilation from one session's work, not a forward-looking automated
  measurement system — future tickets must be manually added to extend it, there is no CI job that grows
  this table automatically.
- 6 runs is a small sample from a single session/operator; it demonstrates the mechanism works, not a
  statistically robust performance characterization.
