# Two-Skill Port — Approved Requirements

## Goal

Close the two genuine gaps found in a follow-up mattpocock-skills gap analysis (run after the
five-skill batch — `docs/superpowers/specs/2026-09-09-five-skill-port-design.md`,
PR #231/#232/#233/#234/#239/#241 — landed) by adding two new report-only, ambient skills to
Software Builder, each adapted from a mutating mattpocock-skills original into this repo's
non-mutating doctrine. Same scaffolding template, registry-wiring locations, and eval/lint
conventions as every prior port — the design decisions captured below are the per-skill ones
(name, deliverable, scope boundary, escalation targets, inputs, routing anchor).

Each is independent of the other and gets its own implementation branch, PR, and 3-round review
cycle (max → high → high effort), per the established convention.

## Source comparison

| mattpocock skill | What it does today |
|---|---|
| `engineering/resolving-merge-conflicts` | Resolves an in-progress git merge/rebase conflict directly: reads commit/PR/issue history for both sides' intent, edits every conflicted file to resolve each hunk, runs the project's typecheck/test/format checks, stages, and commits (or continues the rebase). Never aborts. |
| `productivity/to-questionnaire` | Interviews the user only about the *send* (recipient, what's needed back), then drafts a discovery-questionnaire Markdown document and writes it to `to-questionnaire-<slug>.md` in the current directory. |

Software Builder already supplies, and each port inherits unchanged: the canonical `skill_result`
envelope, `action_gates`, `definition_of_done`/`blocked_conditions` framework
(`docs/skill-framework/shared/runtime-contract.md`); OBSERVED/INFERRED/UNKNOWN/CONFLICTED evidence
vocabulary (`docs/skill-framework/shared/confidence-bands.md`); prompt-injection and
safe-rendered-output rules; the offered-never-automatic cross-skill escalation convention; six-host
packaging; eval-gated admission (five dimensions); the registry-wiring locations below.

## Repository gap baseline

Checked against `origin/main` at `fccd8a5` on 2026-09-11 (post the five-skill batch + PR #242's
merge in flight). Confirmed absent, not merely undocumented — full inventory comparison covered
all 35 mattpocock-skills across its 5 top-level categories (`engineering`, `productivity`,
`in-progress`, `misc`, `deprecated`), not just `engineering/`.

| Gap | Nearest existing skill | Why it doesn't already cover this |
|---|---|---|
| In-progress git merge/rebase conflict resolution | *(none)* | Grep across `skills.yaml` and every skill's own scope finds no skill that inspects or reasons about conflict markers; `pr-review`/`loop-task-implementer` operate on already-clean diffs |
| Turning an unanswerable decision into a questionnaire for someone else | `engineering-decision-discovery` | That skill grills the *caller* about a decision the caller can answer with enough interrogation; it has no mode for a decision the caller structurally cannot answer alone and must hand to a different person |

29 other not-yet-ported mattpocock skills were checked and are each either already covered by an
existing Software Builder skill (9: `domain-modeling`, `codebase-design`→`module-design`,
`improve-codebase-architecture`→`codebase-architecture-review`, `to-spec`→`prd-architect`,
`to-tickets`→`implementation-planner`, `implement`→`loop-task-implementer`, `tdd`→`unit-test-creator`,
`grilling`/`grill-me`→`engineering-decision-discovery`, `ask-matt`→registry routing itself), fail
the report-only doctrine because their own deliverable *is* written code/config/prose (14:
`prototype`, `wizard`, `setup-matt-pocock-skills`, `setup-ts-deep-modules`, `setup-pre-commit`,
`git-guardrails-claude-code`, `migrate-to-shoehorn`, `scaffold-exercises`, `teach`, `loop-me`,
`wait-what`, `writing-beats`, `writing-fragments`, `writing-shape`), or are out of this registry's
remit entirely (3: `writing-for-agents` — skill-authoring meta, this repo has its own doctrine docs;
`handoff`/`claude-handoff` — session continuity, not an SDLC artifact, and `claude-handoff`
literally spawns a background agent, violating offered-never-automatic).

## Global constraints — lessons from the five-skill batch, applied from the start this time

The five-skill batch needed, cumulatively, 9 whole-branch review rounds and 3 mid-flight branch
rebases to reach these two hard-won conclusions. Both apply to this batch from Task 1, not
rediscovered via review:

1. **Routing patterns must anchor on vocabulary confirmed unique to this skill**, never on a
   generic English verb/phrase alone (`find out whether`, `where do we even start`, bare `is this a
   duplicate` all turned out to be topic-free wrappers that collide registry-wide once tested
   against every sibling skill's own positive-eval prompt). Before writing `scripts/registry/skills.d/<id>.yaml`,
   grep the candidate anchor phrase(s) against `scripts/registry/skills.d/*.yaml` and
   `evals/positive/cases.yaml` — both `merge conflict` and `questionnaire` are already confirmed
   unused anywhere else in the registry (checked 2026-09-11), which is why each skill below uses a
   bare, co-occurrence-free compound-phrase trigger (mirroring `squad-map`'s and
   `initiative-mapper`'s proven-safe shape) rather than a verb+noun pattern needing its own
   collision sweep. Still run the full registry-wide wrapper sweep during Task 4 (one wrapper
   template per documented trigger phrase, tested against every sibling's positive-eval prompt) —
   "the anchor is unique" is a necessary condition, not by itself a sufficient proof.
2. **The artifact schema needs a `recommendation: string` field from the start.** Every one of the
   five prior ports' `reference/report-format.md` mandated a `## Recommendation` section that the
   Task 2 schema omitted on the first pass, caught only in round-1 review each time. Both skills'
   field lists below already include it.
3. **`exclude_patterns` must be justified against a real, reproduced collision — never added
   defensively.** Three of the five prior ports shipped an exclude that either protected nothing (a
   negative eval case that never matched the include pattern to begin with) or orphaned a
   legitimate request to `no_match`. Neither skill below ships an `exclude_patterns` list at Task 2;
   add one only if Task 4's sweep or review finds a real, reproduced false positive.
4. **A golden fixture's `require_pattern`/`forbid_pattern` assertions can use PR #237's real
   list-index/predicate path syntax** (`decision_tickets[?id=='T1'].field`) — already merged to
   `origin/main`, so both skills' golden fixtures should use structured per-item assertions from the
   start rather than the stringified-list-substring approach every prior port needed a review round
   to replace.

## Scope

### A — `merge-conflict-analysis`

- **Category**: `review` (same category as `bug-diagnosis`, `local-diff-review` — diagnostic
  inspection of repository state, not a proposed future change).
- **Deliverable**: `MERGE_CONFLICT_ANALYSIS.md` / `merge_conflict_analysis`.
- **Required inputs**: none from the caller — this skill inspects live repository state. **HARD
  STOP** if no merge or rebase is actually in progress (no `.git/MERGE_HEAD` and no
  `.git/rebase-merge`/`.git/rebase-apply`) — this skill has no "describe a hypothetical conflict"
  mode.
- **Workflow**: `Inputs` (detect the in-progress merge/rebase, list conflicted files) `→ Analyze`
  (per conflicted file, per hunk: read both sides' commit messages and, where discoverable, the
  originating PR/issue text; state each side's intent; recommend a resolution that preserves both
  intents where possible, and where genuinely incompatible, recommend the one matching the merge's
  own stated goal with the trade-off named explicitly) `→ Report`.
- **Boundary rules**: never runs a git command that mutates repository or index state — no
  `checkout --ours/--theirs`, no `add`, no `commit`, no `rebase --continue`/`--abort`, no `merge
  --abort`. Read-only git inspection only (`git status`, `git log`, `git show`, `git diff`). The
  actual resolution is `loop-task-implementer`'s job, handed the recommended per-hunk resolution as
  its input. Never invents behavior not traceable to one side's or the other's actual intent.
- **Escalation targets**: `loop-task-implementer` (apply the recommended resolution).
- **Permissions**: `repository: read`, `external_actions: none`.
- **Artifact fields**: `title, conflict_summary, hunks` (list of `{file, description,
  preserved_intent_ours, preserved_intent_theirs, recommended_resolution, trade_off_note}`),
  `unresolved_questions, recommendation, repository_write_action, automatic_downstream_invocation`.
- **Routing anchor**: bare `\bmerge conflict\b` (plus a `rebase conflict` alternative — same
  compound-phrase shape, confirmed unused elsewhere in the registry alongside `merge conflict`).

### B — `stakeholder-questionnaire`

- **Category**: `product` (closest existing category to a document that structures what's needed
  from a person rather than evidence from code or repository state — pairs conceptually with
  `prd-architect`).
- **Deliverable**: `STAKEHOLDER_QUESTIONNAIRE.md` / `stakeholder_questionnaire`. Emitted as the
  report/artifact response, exactly like every other skill's `.md` deliverable — **never written to
  the repository or filesystem directly**. This is a deliberate doctrine adaptation: mattpocock's
  original writes `to-questionnaire-<slug>.md` to the current directory as a side effect; Software
  Builder's report-only skills never write files as a side effect, they emit the document as their
  typed response.
- **Required inputs**: `decision_context` (what can't be resolved and why) and `recipient` (the
  person's role/expertise/relationship to the caller) — **HARD STOP** if either is absent. (Distinct
  from mattpocock's two-step interview — Software Builder's `Inputs` phase binds both as required
  fields up front, consistent with every other port's single HARD-STOP gate rather than a stateful
  multi-turn interview.)
- **Workflow**: `Inputs → Draft` (identify the concrete gap between what `recipient` is expected to
  know and what `decision_context` says the caller needs back; group questions by theme,
  most-important-first; every question is one idea, never compound, with a stated "why this
  matters" only where the question could be misread) `→ Report`.
- **Boundary rules**: never sends, posts, or delivers the questionnaire to anyone — report-only,
  same as every other skill in this registry; the caller decides how and whether to hand it to the
  named recipient. Never fabricates a plausible-sounding answer or fills in a stub itself.
- **Escalation targets**: `engineering-decision-discovery` (once the recipient's answers come back,
  grill on the now-resolved facts), `prd-architect` (the answers become PRD input).
- **Permissions**: `repository: read`, `external_actions: none`.
- **Artifact fields**: `title, decision_context, recipient, questions` (list of `{theme, question,
  why_it_matters}`), `recommendation, repository_write_action, automatic_downstream_invocation`.
  (No `unresolved_questions` field — this skill doesn't investigate evidence and hit gaps, it
  produces the very document meant to close a gap; report-format.md's Structure block has no
  "Unresolved questions" section for this skill.)
- **Routing anchor**: bare `\bquestionnaire\b` — confirmed unused elsewhere in the registry.

## Registry wiring (identical for both, per the five-skill-batch precedent)

For each skill: `skills/<id>/{SKILL.md,README.md,SETUP.md,CHANGELOG.md,examples.md,workflow/*.md,
reference/*.md}`; `scripts/registry/skills.d/<id>.yaml` fragment (category, capabilities,
permissions, `output_contract.produces`, `degraded_behavior`, `routing.patterns` — no
`exclude_patterns` at Task 2, per Global Constraint 3 — `composition.escalation_targets`);
hand-authored additions to `skills.yaml`'s `contracts.platform.artifact_runtime.{durable_artifacts,
artifact_schema_versions,state_semantics,allowed_state_semantics,payload_types}`,
`contracts.composition_runtime.artifact_ownership` (**not** `contracts.platform.artifact_ownership`
— a brief-writing mistake in the five-skill spec that cost real time during `bug-diagnosis`'s
implementation; the correct path is under `composition_runtime`), and
`contracts.composition.{artifact_types,artifact_schemas}`; `docs/skill-framework/shared/skill-routing.md`
row + disambiguation rule; `docs/skill-framework/shared/cross-skill-escalation.md` forward + reverse
rows for every escalation target; `docs/REPOSITORY.md` layout tree row; `make/core.mk`
`lint-<id>` target + `.PHONY`/`lint-static` wiring;
`evals/{positive,negative,ambiguous,adversarial,degraded}/cases.yaml` one row each;
`evals/golden/<id>/{golden-contract,golden-injection}.yaml` using PR #237's list-predicate
assertion syntax from the start (Global Constraint 4); `scripts/tests/test_<id>_routing.py`
regression test asserting every documented `examples.md` invocation-table row resolves against the
live dispatch oracle, PLUS a registry-wide wrapper sweep (one parametrized test per sibling's own
positive-eval prompt, confirming the new skill's bare anchor never becomes a false candidate — the
structural fix the five-skill batch's own sweep tests needed a review round each to arrive at,
applied from Task 4 directly here).

Note for whoever implements Task 2: `make generate`'s pre-write validation for a brand-new skill no
longer needs the bootstrap-ordering workaround four of the five prior ports required (PR #236 fixed
the root cause) — a plain `make generate` should succeed on the first attempt, as it already did for
`initiative-mapper`.

## Testing

Per skill: `make generate` / `make generate-check` clean; `python3 -m scripts.registry validate`
clean; `python3 -m scripts.evals` zero failures; the routing-regression test (including its
registry-wide sweep) passes and is verified to have teeth (temporarily revert the routing pattern,
confirm the test fails, restore); `make lint-static` clean including `verify-install-all`; full
`python3 -m pytest scripts/tests` green. Then a 3-round review (max effort → high effort → high
effort) with fixes applied and re-verified between rounds, before merge.

## Sequencing

Independent — implement and PR in either order; neither touches the capability catalogue or any
shared infrastructure the other depends on. `merge-conflict-analysis` is the stronger, better-fit
gap; `stakeholder-questionnaire`'s `product` categorization was the one open design question this
spec resolved by explicit user choice (over `analysis` or a new `communication` category) rather
than by precedent, since no existing skill's category cleanly fits a communications artifact.
