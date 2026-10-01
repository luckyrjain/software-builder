# Change impact report — B6: cross-run repo-convention capture

**Coverage status: COMPLETE**

## Assessment target

Proposed state. Repo: `luckyrjain/software-builder`, main, head includes merged PR #316 (B5). Sources:
`docs/superpowers/specs/2026-09-30-b6-convention-capture-design.md` (revision 5, converged across 5
adversarial review rounds, 3 personas — the deepest-iterated ticket in this session alongside B2's own
10-round saga) and `docs/superpowers/specs/2026-09-30-b6-convention-capture-architecture-review.md`
(Approved with conditions, 6 conditions, all addressed).

## Criticality: High

Not code size (the final design is modest: two small functions, one new doc file, one new report script,
a handful of `reviewer.md` lines) but a genuinely new capability class this session hasn't touched before:
**this is the first ticket where the Reviewer role itself gains a capability that reaches outside the
current diff and the current task's own repository state** — every prior Reviewer capability (B3's
dual-worktree regression-gate, B4's diff-scoped scope-hint investigation) stayed within the task's own
repository/commit history; B6's `fetch_and_score` reaches into this repo's *unrelated, historical* PR
review-comment content. This sits directly adjacent to a rule from a prior ticket (B4's
`reviewer.md:58`, "may not... Call `host.scm.comment.*`") that this design must be a stated, narrow
exception to, not a silent contradiction of.

## Change classes

- `new-capability-declaration` (`fetch_and_score`'s PR review-comment read, scoped narrowly to the
  Reviewer role for the first time reaching outside the current diff)
- `new-validation-logic` (`score_text_pair`'s pure comparison function)
- `contract-change` (`reviewer.md`'s "may"/"may not" lists — an explicit, narrow carve-out interacting
  with B4's existing prohibition)
- `documentation-only` (the new `learned-conventions.md` file itself, initially empty)
- `report-generation` (the convention-scan trigger's own new script and report artifact — genuinely
  additive, touches no existing file at all)

## Impacted services / files

| Path | Nature of change | Risk |
|------|-------------------|------|
| **`skills/loop-task-implementer/workflow/reviewer.md`** | New "may" grant (`fetch_and_score` against a task's own cited PR numbers) and new "may not" companion rule (no manual fallback to raw PR content on failure) | **The one file needing the most careful diff review**: must read as an explicit, narrow *exception* to the existing `:58` prohibition ("may not... Call `host.scm.comment.*`") — B4's own rule — not an accidental widening of it. The design's own text is careful about this distinction (a scripted, bounded function call vs. an open-ended tool capability), but this distinction must survive into the actual prose edit, not just the design doc |
| **New: `docs/skill-framework/learned-conventions.md`** | Net-new, empty at Phase 1 (single running list, no Proposed/Accepted split) | Low — no existing consumer, no existing file to conflict with |
| **New: `score_text_pair` function** (location not yet pinned to a specific file by the design — likely a new small script module) | Pure, local, deterministic string comparison, zero I/O | Low — no network, no fetch, trivially unit-testable |
| **New: `fetch_and_score` function** (same module family) | The one function with real network/fetch exposure — PR review-comment reads, rate-limit/retry, `NEEDS_EVIDENCE` fail-closed | Moderate — this is where the design's own 5-round history concentrated almost all of its real bugs; implementation must match the converged spec exactly (corpus = review-comment text only, never title/body/diff; output = bare score, never the fetched text, on both success and failure paths) |
| **New: convention-scan trigger script + its report artifact** (`docs/superpowers/specs/<date>-b6-convention-scan-report.md`, generated, never auto-committed) | Read-only scan of this repo's all-PR history, `score_text_pair`-based dedup against `learned-conventions.md`'s existing entries, textual-contradiction check against `CONTRIBUTING.md`/implicated `SKILL.md` files | Low-moderate — no repository write of any kind; the report file itself follows this session's own established `docs/superpowers/specs/` convention, committed manually alongside any acted-on candidate, same as every other design doc this session produces |
| **Task-intake path** (no file change — a documented human procedure) | A human manually constructs a legacy `implementation_task` envelope from a report row | N/A (no code) — but genuinely unvalidated end-to-end (design's own Open Question 4); first real use should be treated as a dry run, not assumed correct on the first attempt |

**Confirmed untouched**: `orchestrator.md` (the convention-scan trigger is deliberately not a per-task
hook — confirmed via direct read of the design's own Rollout plan, which names only `reviewer.md` and the
new files, never `orchestrator.md`), `scripts/validate_loop_lifecycle.py`, `state-schema.yaml` — matching
this session's own established discipline of leaving these files alone absent a specific, justified need,
which this design never has.

## Impacted contracts

- `reviewer.md`'s "may"/"may not" lists — extended, not restructured; the closed finding-output schema
  (unchanged since B3/B4) is untouched — B6 adds zero new fields, reusing the evidence-prefix-convention
  pattern exactly.
- No `implementation_task`/`plan_execution_state` schema change — this design deliberately avoids touching
  either, per its own revision history (round 4's redesign explicitly removed the one mechanism that would
  have required schema changes).

## Impacted data

None — no durable composition artifact, no `plan_execution_state` field, no run-log event change. The
only new persisted data is `learned-conventions.md`'s own content, accumulated via ordinary, human-reviewed
PRs exactly like any other repository content.

## Impacted dependencies

None new beyond the GitHub API/CLI capability class this skill already depends on for PR reads elsewhere
(B4's own precedent).

## Impacted owners

Single owner (CODEOWNERS root wildcard). No CODEOWNERS change needed.

## Required tests

1. **`score_text_pair` unit tests**: trigram extraction, lowercase-folding, markdown-boilerplate-stripping,
   Jaccard-overlap correctness on known input pairs, including the exact degenerate short-string cases
   round 4's review specifically found problematic (2–4 word inputs) — confirming the design's own
   round-5 fix (comparing full principle sentences, not short labels) is what the implementation actually
   uses for the conflict-check call site, not a regression back to short-string comparison.
2. **`fetch_and_score` tests** (mocked network): correct PR review-comment fetch (never title/body/diff);
   rate-limit retry-then-`NEEDS_EVIDENCE` behavior; **explicit confirmation that a forced fetch failure
   never leaks the fetched text in any exception message or log line** — this is a real, previously-missed
   security property from round 4's own finding, and deserves its own dedicated test, not just incidental
   coverage.
3. **`reviewer.md` diff review, manual**: confirm the new "may"/"may not" text reads as an explicit,
   narrow exception to the existing `:58` prohibition, not a silent widening of it — this is the single
   most important manual check for this ticket, flagged explicitly because it's the one place a correct
   design could still be implemented incorrectly.
4. **Conflict-check integration test**: seed `learned-conventions.md` with a real entry, submit a
   candidate whose principle sentence is an independent paraphrase of the same convention, confirm it's
   recognized as already-captured (closes the round-3/round-4 "duplicates forever" bug class at the
   implementation level, not just the design level).
5. **Report-generation dry run** (matches the design's own Rollout Phase 5): a real invocation against
   this repo's actual PR history, producing a real report file, manually reviewed before treating the
   mechanism as trustworthy.

## Operational impacts

1. **First Reviewer-role capability reaching outside the current diff/task** — a genuinely new posture for
   this skill, disclosed and scoped narrowly (a single, scripted function call, never open-ended reading),
   but worth naming explicitly as a precedent-setting change for any future ticket that might want to widen
   Reviewer capabilities further.
2. **Task-intake remains a real, disclosed manual step** — this design deliberately does not automate
   getting a candidate into `loop-task-implementer`'s own task selection; the first few uses should be
   treated as calibration, not a proven pipeline.
3. **`learned-conventions.md`'s own growth is unbounded over the repo's lifetime**, but the design's own
   round-5 fix (pure local `score_text_pair` comparison, no network cost per existing entry) keeps this
   cheap even at hundreds of entries — a real, already-addressed scale consideration, not a new one this
   report needs to reopen.

## Review triggers

**None required.** This design underwent 5 rounds of dedicated adversarial multi-persona review (Security
Architect, SRE, Software Architect), each round independently re-verifying citations against live
repository files, converging with zero remaining `PROPOSED_BLOCKING` findings after a genuinely deep,
iterative process that found and fixed the same underlying bug class three separate times before landing
on the correct fix (splitting one imagined function into two genuinely distinct ones). A standard
`security-review` pass would not exceed what this process already delivered, particularly on the one
security-sensitive surface (the Reviewer's new external-fetch capability), which received dedicated,
repeated scrutiny across rounds 2 through 5.

## Material unknowns

1. The occurrence threshold (3/3) and similarity threshold (0.4) are both explicitly unvalidated against
   real data — the design's own honest, repeated disclosure, not a gap this report introduces.
2. The conflict-check's disclosed blind spot for unwritten institutional doctrine (this session's own
   write-authority doctrine and similar unwritten invariants) — mitigated by Reviewer judgment only for
   generically-suspicious cases, not eliminated for this specific residual.
3. The manual task-intake path is genuinely unexercised end-to-end — no real convention-scan candidate has
   ever been hand-converted into a task yet.

## Unknowns

None beyond the material unknowns above — repository read was available throughout, and the design
document (all 5 revisions) was read in full, along with direct verification of `reviewer.md`'s real
current prohibition text this design must interact with cleanly.

## Evidence refs

- `docs/superpowers/specs/2026-09-30-b6-convention-capture-architecture-review.md`
- `docs/superpowers/specs/2026-09-30-b6-convention-capture-design.md` (revision 5)
- Direct repository verification: `skills/loop-task-implementer/workflow/reviewer.md:58` (the existing
  `host.scm.comment.*` prohibition this design's new capability must narrowly except, not contradict);
  `scripts/registry/composition_contracts.yaml` (the 15-field `implementation_task` schema the manual
  task-intake path targets); confirmed no `orchestrator.md`/`state-schema.yaml`/
  `validate_loop_lifecycle.py` changes anywhere in the converged design.
