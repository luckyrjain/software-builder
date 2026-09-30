# Change impact report — B4: external human review-comment loop for loop-task-implementer

**Coverage status: COMPLETE**

## Assessment target

Proposed state. Repo: `luckyrjain/software-builder`, main, head includes merged PR #314 (B3). Sources:
`docs/superpowers/specs/2026-09-30-b4-review-comment-loop-design.md` (revision 6, converged across 6
adversarial review rounds, 3 personas — Security Architect and Software Architect converged clean at
round 3; SRE continued alone through round 6 on a real, narrower plumbing-completeness thread) and
`docs/superpowers/specs/2026-09-30-b4-review-comment-loop-architecture-review.md` (Approved with
conditions, 6 conditions, all addressed).

## Criticality: High

Not code size (the touched surface is modest — 5 files plus new tests) but blast radius: this design
modifies `scripts/implementation_plan.py`'s `EXECUTION_STATE_FIELDS`, `cas_advance`,
`initial_plan_execution_state`, and `validate_plan_execution_state` — four functions that every
plan-based task in this skill depends on for its checkpoint lifecycle, not only tasks with external
comment activity. This is the first ticket in this session's history whose core plumbing work sits
entirely outside `loop-task-implementer`'s own directory, in shared infrastructure `scripts/`
functions with pre-existing, wired CI tests (`scripts/tests/test_plan_execution_state.py`) that any
regression here would trip immediately and repo-wide.

## Change classes

- `contract-change` (new `plan_execution_state` fields, extending a closed, code-enforced schema)
- `new-validation-logic` (two new `validate_plan_execution_state` type checks)
- `new-capability-declaration` (four new `host.scm.*` capabilities, a genuinely new class for this skill)
- `documentation-only` (SKILL.md, mcp-capabilities.md rerun-trigger/capability-matrix edits, reviewer.md
  prose-rule addition)
- `orchestrator-workflow-extension` (new unnumbered subsection, §6 package-enumeration amendment)

## Impacted services / files

| Path | Nature of change | Risk |
|------|-------------------|------|
| `scripts/implementation_plan.py` | `EXECUTION_STATE_FIELDS` +2 keys; `cas_advance` +2 kwargs + thread-id-aware merge for `comment_threads`; `initial_plan_execution_state` seeds both `{}`; `validate_plan_execution_state` +2 inline type checks | **Highest in this change** — shared, foundational, used by every plan-based task regardless of B4 relevance. The design's own revision history (rounds 3–6) shows this exact function set was under-scoped THREE separate times before reaching completeness (round 3 found 2 of 5 real touch points, round 4 found 2 more, round 5 found the 5th) — a real, demonstrated pattern of this specific surface being easy to under-scope. `git log --oneline -- scripts/implementation_plan.py` confirms B1's commit `3f065da` already established the exact 5-touch-point template (`EXECUTION_STATE_FIELDS`, `cas_advance` kwarg+merge, seed, schema entry, type check) this design's Phase 0 now mirrors 1:1 for two fields instead of one — the precedent is real and the design's final form matches it exactly, per the round-6 reviewer's own git-history verification, not merely asserted |
| `scripts/plan_state_store.py` | `cas_advance` signature extension only | Low — additive kwargs, no removal/behavior change to existing kwargs |
| `skills/loop-task-implementer/reference/state-schema.yaml` | +2 keys to the documented `plan_execution_state` block | Low in isolation, but **load-bearing**: `scripts/tests/test_plan_execution_state.py:235-241` hard-asserts this block's key set equals `EXECUTION_STATE_FIELDS` exactly — a real, already-wired CI test that fails deterministically if this file and the Python set drift out of sync |
| `skills/loop-task-implementer/SKILL.md` | Two separately-shaped rerun-trigger sentences amended (line 75 short slash-form, line 126 long prose form) | Low — pure documentation, but the design's own round-3/4 history shows this exact pair of edits was initially conflated as "one shared edit" and had to be corrected into two distinct, differently-worded amendments — worth a careful diff review at implementation time given that history |
| `skills/loop-task-implementer/workflow/orchestrator.md` | New unnumbered subsection between §16 and §17 (bounded final-check recheck + `autonomous_merge_authorized` suppression on cap-reached); §6 package enumeration +1 field | **This is the sixth change to this file this session** (after A5, A6, B1, B2, B3) — the design itself names this "this repo's own highest-blast-radius file." The design's own round-4 finding flagged a real renumbering hazard (~51 cross-references to §17 through §20 across four files) and revision 4 explicitly chose an unnumbered insertion to avoid it — this choice should be preserved exactly at implementation time, not "cleaned up" into a renumbered `## 17.` by an implementer unaware of why it was deliberately left unnumbered |
| `skills/loop-task-implementer/workflow/reviewer.md` | +1 prose rule in Read-only execution rights / Review boundary ("must never call `host.scm.comment.*`/`host.scm.actor.permission`, must not seek out the triggering comment") | Low-moderate — **confirmed via direct grep of the current file that the Blocking standard remains exactly 6 conditions** (verified: `awk`-counted 6 numbered items between `## Blocking standard` and `Do not mark as blocking`), matching this report's own required confirmation that no stray 7th condition survived from the design's own round-1 mistake-and-revert. The finding output YAML schema is untouched — no new field |
| `skills/loop-task-implementer/reference/mcp-capabilities.md` | +4 new capability rows (`host.scm.comment.read`, `host.scm.comment.reply`, `host.scm.review.request`, `host.scm.actor.permission`) | Low — additive rows in an existing table format, degraded-path column already conventional |

## Impacted contracts

- `plan_execution_state` v1 (informal, code-enforced via `EXECUTION_STATE_FIELDS`) — extended, not
  broken; existing consumers (any code reading `plan_execution_state` that doesn't yet know about
  `comment_threads`/`final_check_attempts`) are unaffected since both are additive, optional-shaped
  (`{}`-seeded) fields, not required-populated ones.
- `reviewer.md`'s finding output schema — **unchanged**, confirmed directly against the live file.
- `reviewer.md`'s Blocking standard — **unchanged at 6 conditions**, confirmed directly against the live
  file (see table above).
- New, informal `host.scm.*` capability contracts — genuinely new for this skill; no existing consumer to
  break, but see Required tests below for the real gap this introduces.

## Impacted data

`plan_execution_state.comment_threads`/`final_check_attempts` (new, durable via `plan_state_store.py`'s
CAS store, per-task). No change to any durable composition artifact (`bug_diagnosis_report`,
`implementation_task`, etc.) — B4 does not touch `skills.yaml`'s artifact schemas at all, unlike B3.

## Impacted dependencies

None — no new third-party package, no new external service dependency beyond the SCM host's own API
surface (already an implicit dependency via existing PR create/update capabilities).

## Impacted owners

Single owner (CODEOWNERS root wildcard already covers every touched path, consistent with every prior
ticket this session) — no CODEOWNERS change needed.

## Required tests

1. **Seed test mirroring `test_plan_execution_state.py:148-152`** — the single most load-bearing new
   test: asserts `initial_plan_execution_state` seeds both new fields as `{}` and the result validates
   clean. This is the exact test class whose *absence* would have let the design's round-5 gap
   (missing seed) ship silently.
2. **Schema-parity regression coverage** — confirm `test_plan_execution_state.py:235-241`'s existing
   assertion (`set(schema["plan_execution_state"]) == EXECUTION_STATE_FIELDS`) passes with both new keys
   present in both places; this test already exists and doesn't need new code, only correct field
   additions on both sides to keep passing.
3. **`validate_plan_execution_state` type-check unit tests** — a malformed `comment_threads` (wrong
   depth, non-Mapping per-thread entry) and malformed `final_check_attempts` (non-int value) must each
   fail validation explicitly, matching the existing `clarifications`-must-be-`Mapping` test's shape.
4. **`cas_advance` thread-id-aware merge test for `comment_threads`** — concurrent writes to different
   `thread_id`s under the same `task_id` must not clobber each other (this is the one new merge-semantics
   behavior that has no direct precedent in `clarifications`' own shallow-merge test, since
   `clarifications` is only one level deep).
5. **Actor/diff-scope admissibility gate tests** — in-scope-actor + diff-scoped comment produces a scope
   hint; out-of-scope-actor and out-of-diff-scope comments do not, and are recorded as non-blocking
   observations per the design's data-minimization rule (bare count only for out-of-scope-actor,
   thread-id for out-of-diff-scope, never a leaked identity in an emitted artifact).
6. **`final_check_attempts` cap-and-suppress test** — reaching cap 2 with pending in-scope/diff-scoped
   activity must suppress `autonomous_merge_authorized` for that run and fall through to the "stop at
   verified readiness" path, never a silent merge.
7. **`redacted_note` literal-constant test** — confirm the scope hint sent to a Reviewer package is
   byte-identical to the one fixed string on every occurrence, never per-thread-variable (a regression
   here would silently reopen the round-2 injection finding).
8. **`reviewer.md` new prohibition rule — no automated enforcement exists for this today**, and this
   report flags that explicitly rather than assuming test coverage exists: see Operational impacts below.

## Operational impacts

1. **The new `host.scm.comment.*`/`host.scm.actor.permission` capabilities are almost certainly not
   exercisable by this repo's existing test suite as real integration tests** — they require a live
   GitHub/GitLab PR with real comment threads and real collaborator-permission data. `mcp-capabilities.md`'s
   own convention (degraded path = "capability absent → skip, proceed as before") means the code path can
   and should be unit-tested with a mocked/fake capability provider, but genuine end-to-end coverage
   (does the real GitHub API shape actually match `{thread_id, comment_id, author, body, anchor,
   resolved, original_commit_sha, created_at, updated_at}`?) is a real, disclosed gap — this repo has no
   existing GitHub/GitLab MCP test fixture to model this on (`reference/mcp-capabilities.md`'s own text:
   "no Datadog/GitLab/Jira MCP dependency"). Flagging as a `material_unknown`, not blocking implementation,
   consistent with the design's own honest "Other/unknown" host row.
2. **`reviewer.md`'s new "must not call `host.scm.comment.*`" rule has no automated enforcement** — round
   3's Security Architect review found this explicitly and accepted it as a named residual (every other
   Reviewer restriction in this skill is also prose-only), but it's worth restating here as a real
   operational cost: violations of this rule, if they occur, are silent and undetectable by any existing
   mechanism. No fix is required before implementation per the design's own converged conclusion, but this
   report surfaces it as a live, accepted trade-off rather than letting it disappear between documents.
3. **`orchestrator.md`'s unnumbered-subsection insertion is a real diff-review risk** — an implementer or
   reviewer unfamiliar with round 4's renumbering-cascade finding could "fix" the unnumbered heading into
   a numbered one during code review, silently reintroducing the ~51-cross-reference hazard the design
   deliberately avoided. Worth an explicit PR-description note at implementation time.
4. Operational cost of the feature itself (repeated from the design, not re-derived): at most 2 extra
   full lens-pair Reviewer dispatches per task (the capped final-check recheck), scoped only to
   actor-in-scope, diff-scoped comment activity — a bounded, disclosed, trust-gated cost.

## Review triggers

**None required.** Consistent with B2's and B3's own precedent in this session: this design underwent 6
rounds of dedicated adversarial multi-persona review (Security Architect, SRE, Software Architect),
independently re-verifying every citation against live repository files across every round, and converged
with zero remaining PROPOSED_BLOCKING findings from all three personas. A standard `security-review` or
`api-design-review` pass would not exceed what this process already delivered — the injection-boundary
question in particular (this ticket's single most security-sensitive surface) was pressure-tested across
3 dedicated rounds by the Security Architect persona alone, with direct code execution/verification each
time, not assertion.

## Material unknowns

1. Real end-to-end test coverage against a live GitHub/GitLab PR is not achievable in this repo's current
   test suite — unit/mock coverage is achievable and required (see Required tests), but the exact shape
   of `host.scm.comment.read`'s real API response is unverified against an actual host until this ships
   and is exercised live. Carried forward from the design's own Open question 2 (GitHub's
   resolvable-thread vs. non-resolvable-comment distinction) and Open question 1 (`original_commit_sha`
   content-comparison refinement deferred to a follow-up).
2. Per-cycle ingestion volume cap for a collaborator/CODEOWNERS set much larger than this repo's actual
   scale — the design explicitly defers this (Open question 3), judged acceptable for this repo's real
   scale, not a gap in the design's own reasoning.

## Unknowns

None beyond the material unknowns above — repository read was available throughout, and both source
documents were read in full.

## Evidence refs

- `docs/superpowers/specs/2026-09-30-b4-review-comment-loop-architecture-review.md`
- `docs/superpowers/specs/2026-09-30-b4-review-comment-loop-design.md` (revision 6)
- Direct repository verification: `scripts/implementation_plan.py` (`EXECUTION_STATE_FIELDS`,
  `cas_advance`, `initial_plan_execution_state`, `validate_plan_execution_state`),
  `scripts/plan_state_store.py`, `scripts/tests/test_plan_execution_state.py`,
  `skills/loop-task-implementer/workflow/reviewer.md` (Blocking standard, confirmed 6 conditions via
  direct `awk` count), `skills/loop-task-implementer/scripts/validate_loop_lifecycle.py` (confirmed
  present, confirmed untouched by this design), `git log --oneline -- scripts/implementation_plan.py`
  (confirmed commit `3f065da`'s `clarifications` precedent as the real template this design's Phase 0
  mirrors).
