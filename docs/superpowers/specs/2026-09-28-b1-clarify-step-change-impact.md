# Change impact report — B1: optional clarify step in loop-task-implementer's task selection

**title:** B1 — optional clarify step in loop-task-implementer's task selection
**assessment_target:** [2026-09-28-b1-clarify-step-design.md](2026-09-28-b1-clarify-step-design.md) (revision 4, `proposed_state`), validated by [2026-09-28-b1-clarify-step-architecture-review.md](2026-09-28-b1-clarify-step-architecture-review.md) (Approved with conditions)
**coverage_status:** COMPLETE — repository read used to ground every field, including a direct check that this design's `plan_execution_state.clarifications` addition is purely additive against A5's own already-tested 11-field contract, and that the new cross-skill coupling to `engineering-decision-discovery` genuinely introduces no reverse dependency (that skill is consumed, not modified)

## material_unknowns

None on the design's own terms — 4 rounds of adversarial review, converging CLEAN, leave no undisclosed
gaps in the design itself. What this report cannot verify from documents alone is whether the Builder's
actual implementation preserves the specific, hard-won details 4 rounds of review fought to establish (see
`review_triggers` below — these are implementation-time checks, not change-impact unknowns).

## criticality

**High** — the widest single-file surface any ticket this session has touched.
`skills/loop-task-implementer/workflow/orchestrator.md` is confirmed (by this session's own prior
research) to be this repo's highest-blast-radius file, routed through by ~40+ other skills. This change
touches **seven of its numbered sections** (§2, §3, §4, §6, §9, §15, §16, §19) plus its "## Inputs"
section — no prior ticket this session made (A5, A6, F1, F4, F2) touched more than two or three sections
of any single file. It also modifies `scripts/implementation_plan.py`'s `plan_execution_state` read/write
chain, the same durable, CAS-protected, multi-consumer state A5 established — a defect in the new
`clarifications` field's merge logic has reach into every consumer of that checkpoint, not just this
ticket's own new behavior. And it establishes this repo's **first-ever cross-skill coupling** from
`loop-task-implementer` to `engineering-decision-discovery` — a new dependency surface no prior ticket
this session introduced.

## change_classes

- **Additive schema extension to already-shipped, CAS-protected durable state**: `plan_execution_state`
  gains a 12th field (`clarifications`) alongside A5's original 11 — confirmed additive-only by direct read
  of `EXECUTION_STATE_FIELDS`, `initial_plan_execution_state`, `reconcile_plan_execution_state`,
  `validate_plan_execution_state`; none of the 11 pre-existing fields' own logic is touched
- **Additive edits across 7 sections of the single highest-blast-radius file in this repo**
  (`orchestrator.md`) — each edit is individually additive (a new branch, a new bullet, a new list item, a
  new pre-dispatch check target), but the cumulative surface is the widest this session has produced
- **New closed-vocabulary registry member**: `run_log.py`'s `EVENTS` tuple gains `clarify_dispatched`/
  `clarify_returned`, with the same companion `reference/run-log.md` doc-table requirement A6 already
  established for this exact class of change (confirmed via the real, already-passing
  `test_reference_documents_every_event_actor_outcome_reason_and_exit_code` test)
- **Reused-not-modified existing primitive, new usage pattern**: `task_lease.py`'s `derive_lease_id`/
  `try_acquire` are called with a new input-string formula (`f"{task_id}:clarify"`) for a genuinely new,
  distinctly-scoped lease — zero code changes to `task_lease.py` itself, confirmed by the design's own
  4-round verification that this formula produces cryptographically non-colliding ids against the existing
  Builder-dispatch lease
- **First-ever cross-skill coupling**: `loop-task-implementer` → `engineering-decision-discovery`,
  consumer-only (the design makes zero changes to `engineering-decision-discovery` itself, confirmed
  across all 4 review rounds) — both a new forward and new reverse row land in
  `cross-skill-escalation.md`, matching this repo's own established convention for a new edge
- **New shared-doc table rows**: `prompt-injection.md` gains a row for a genuinely new untrusted-content
  source (a human's free-text clarify-interview answer)
- **No CI workflow changes, no new external dependency, no new service**

## impacted_repositories

- `luckyrjain/software-builder` only.

## impacted_services

- N/A — in-process orchestration logic plus durable checkpoint state; no runtime service.

## impacted_contracts

- **`plan_execution_state`'s existing 11-field contract (A5)** — confirmed, by direct read, genuinely
  unregressed: `clarifications` is additive to `EXECUTION_STATE_FIELDS`, and the new
  `reconcile_plan_execution_state` line (`normalized["clarifications"] = {**state.get("clarifications", {}), **(clarifications or {})}`)
  sits alongside, not instead of, the existing 5 explicit `normalized[...]` assignments — none of those
  are touched. A5's own already-tested guarantees (CAS generation-check, the
  `completed_evidence_refs`-union pattern, stale-writer rejection) are all confirmed to apply to the new
  field the same way, per 4 rounds of review tracing the exact code paths.
- **`task_lease.py`'s existing lease-identity contract** — confirmed unmodified; the new clarify-entry
  lease is a new *usage* of an existing, unmodified function, not a contract change.
- **`run_log.py`'s `EVENTS`/`REASON_CODES` closed-vocabulary contracts** — `EVENTS` gains 2 new members
  with the required companion doc-table update (real, test-enforced, confirmed by direct read of the
  actual test); `REASON_CODES` is **not** extended — this design deliberately reuses the existing
  `MISSING_DECISION` code rather than adding a new one, confirmed (across 3 review rounds) to be a
  semantically apt fit already used by §11 Remediation for an analogous case.
- **`orchestrator.md` §6's "neutral package"/"withhold" contract** — `resolved_summary` is added to the
  package list; confirmed (round 4) not to collide with anything on the existing "withhold or normalize"
  list (it's sub-step-derived content, not Builder-authored narrative).
- **`orchestrator.md` §9's admissible rebuttal-evidence contract** — gains an 8th category; confirmed
  (round 4) to fit the same "verifiable, Reviewer-checkable" shape as the existing 7.
- **`engineering-decision-discovery`'s own input/output contract** — confirmed, across all 4 rounds,
  **unchanged** — this design is a pure consumer, grounding its own `decision_scope`/return-parsing
  against that skill's real, already-shipped contract (`workflow/inputs.md`, `reference/report-format.md`),
  not asking for any change to it.

## impacted_data

- New field on already-durable data: `plan_execution_state.clarifications: dict[task_id, {status, resolved_summary, resolved_at}]`
  — no migration needed for existing checkpoints (absence has a well-defined "never triggered" meaning,
  and `initial_plan_execution_state`/`state-schema.yaml` both seed it for every *new* plan going forward).
- **Disclosed, not solved**: an in-flight plan checkpoint created *before* this change ships, if resumed
  *after* it ships, would be missing the `clarifications` key entirely — `validate_plan_execution_state`'s
  existing missing-field check would reject it. This is the same class of gap every prior
  `EXECUTION_STATE_FIELDS` addition in this repo already has (no stated migration path for in-flight
  checkpoints predating a schema addition) — confirmed by round 3's own review as "likely an accepted
  pre-existing convention... not a new gap," not something this design introduces freshly.

## impacted_dependencies

- **`engineering-decision-discovery`** — new consumer relationship. That skill's own test suite,
  documentation, and behavior are unaffected (it is not modified), but it now has a new, real caller whose
  correctness depends on this design's own field-mapping being accurate against that skill's real schema
  (confirmed accurate across rounds 2-4).
- **`spawn_lock_holder`-style real-subprocess test harness** (`scripts/tests/install_lock_test_helpers.py`)
  — reused for the new clarify-entry lease's contention test, same pattern A5/A6 already established.
- **`make lint-python`/`make generate`** — sweeps the modified Python files automatically; no registry
  field changes here (this ticket doesn't touch `skills.yaml`/`agent-hosts.yaml`), so no `make generate`
  regeneration is needed, unlike F2.
- **No new PyPI dependency.**

## impacted_owners

- Repo owner (`@luckyrjain`), sole owner, unchanged.

## required_tests

- `cas_advance`/`advance_plan_execution_state`/`reconcile_plan_execution_state`'s `clarifications` merge,
  using the corrected `state.get("clarifications", {})` line (not the round-3 `current.get(...)` bug) —
  required, this is the design's own core write-path fix.
- `initial_plan_execution_state()` seeds `clarifications: {}`; a companion test asserting
  `EXECUTION_STATE_FIELDS` matches `state-schema.yaml`'s `plan_execution_state:` block — required, this is
  the same class of drift-prevention test this repo's own `run_log.py` `EVENTS` precedent already
  established, now confirmed by round 2 to have no equivalent for `EXECUTION_STATE_FIELDS` today.
- `validate_plan_execution_state`'s new `isinstance(state.get("clarifications"), Mapping)` check —
  required, closes a real fail-open gap round 3 named.
- Real cross-process clarify-entry lease contention test (`spawn_lock_holder`-style) — required.
- **A dedicated post-acquisition re-check (TOCTOU) test**: state resolves *between* lease acquisition and
  the re-check, second process must skip the interview entirely — required, this is the concrete
  regression test for the sequential-race gap rounds 2-3 both independently found.
- The new `clarify_dispatched`/`clarify_returned` `EVENTS` pair's own companion doc-table test (mirroring
  the existing `builder_dispatched`/`builder_returned` pattern, confirmed real and test-enforced by
  round 4's direct read of `test_reference_documents_every_event_actor_outcome_reason_and_exit_code`) —
  required.
- Two new Tier-2 fixtures (`clarify-step-unattended-skip.yaml`, `clarify-step-resolves-and-persists.yaml`),
  registered in `eval_contracts.yaml` — required, per architecture review's own acceptance criteria.
- `make lint-python` — standing no-regression check.

## operational_impacts

- **First-ever new default-on behavior for existing callers of `loop-task-implementer`**: an underspecified
  task now attempts one bounded clarify interview before escalating, rather than escalating immediately —
  disclosed explicitly (design's revision-2 fix) as a genuine, intentional behavior change, not silently
  backward-compatible. Any existing automated caller of this skill that never passes `interaction_policy`
  will see this new behavior by default.
- **New, real dispatch-level cost**: the clarify sub-step's response-wait-budget is now a named, covered
  circuit breaker (extending an existing one, not inventing a new mechanism) — bounds wall-clock cost
  regardless of whether the human honors the disclosed-as-unenforced "3 questions" prompt guidance.
- **Reviewer-visibility fix has real operational weight**: without the round-3 §6/§9 fix, a Reviewer
  session reviewing a clarify-driven change would have had no way to verify a Builder's reliance on a
  human's clarification — this was the single most consequential fix across all 4 rounds, precisely
  because it's the kind of gap that would only surface in a real, high-stakes review (e.g. a change
  touching an auth check with no textual basis in the acceptance criteria alone), not in any unit test.
- **No new Actions minutes, no impact on required CI checks.**
- **Owner-visible cost**: none beyond ordinary review of the landing PR — no bulk classification pass, no
  repo-wide regeneration step (unlike F2), no manual owner action required beyond normal PR review.

## review_triggers

- **Recommended, strongly**: verify the Builder's actual implementation uses `state.get("clarifications", {})`
  (not `current.get(...)`) in `reconcile_plan_execution_state` — this exact bug was caught in the design
  doc itself (round 3) and a Builder copying stale context or an earlier draft could reintroduce it.
- **Recommended, strongly**: verify §6/§9's additions are actually present in the shipped `orchestrator.md`
  diff — this was the design's own most consequential, latest-caught finding (round 3, missed by rounds
  1-2), so it's exactly the kind of thing worth a named check rather than incidental coverage.
- **Recommended**: verify the clarify-entry lease's exact formula
  (`derive_lease_id(repo, base_branch, f"{task_id}:clarify")`) is implemented as an input-side
  modification, not an output-string suffix — the design's own round-2→3 history shows this distinction
  is easy to get wrong in a way that either always collides or always fails validation.
- **Recommended**: verify the post-acquisition re-check (TOCTOU close) is actually present, not just the
  lease acquisition itself — a Builder implementing only "acquire lease, invoke sub-step" without the
  re-read in between would silently reopen the sequential-race gap rounds 2-3 both found.
- No other hard trigger under this skill's own vocabulary — no external API, no database, no new attack
  surface beyond what's already been adversarially reviewed across 4 rounds.

## unknowns

- Whether a future refactor of `orchestrator.md`'s own section numbering ever shifts §2/§3/§4/§6/§9/§15/
  §16/§19 — this design's own cross-references (and this change-impact report's own citations) are tied
  to the current numbering; not this ticket's problem to solve, but worth noting for future maintainers
  touching this file's structure.
- Whether the disclosed, unenforced "3 questions" prompt guidance ever needs a stronger mechanism in
  practice (the design explicitly punts on this, relying entirely on the separately-enforced
  response-wait-budget breaker for the real bound) — not knowable until this ships and sees real use.

## evidence_refs

- `docs/superpowers/specs/2026-09-28-b1-clarify-step-design.md` (revision 4, full document, all 4 rounds'
  Revision history entries)
- `docs/superpowers/specs/2026-09-28-b1-clarify-step-architecture-review.md` (Approved with conditions)
- `skills/loop-task-implementer/workflow/orchestrator.md` (§2-§4, §6, §9, §15-16, §19, "## Inputs" — all
  read in full across review rounds, confirmed real section boundaries and existing content)
- `skills/loop-task-implementer/SKILL.md:117` (the real, pre-existing response-wait-budget circuit breaker
  this design extends rather than invents)
- `scripts/implementation_plan.py` (`EXECUTION_STATE_FIELDS`, `initial_plan_execution_state`,
  `reconcile_plan_execution_state`, `advance_plan_execution_state`, `validate_plan_execution_state` — all
  read and traced line-by-line across 4 review rounds)
- `scripts/plan_state_store.py` (`cas_advance`, confirmed the real write-path chain)
- `scripts/task_lease.py` (`derive_lease_id`, confirmed the real fixed-arity signature and the correct
  input-side-modification fix)
- `skills/loop-task-implementer/scripts/run_log.py` (`EVENTS`, `REASON_CODES`, confirmed real values) and
  `skills/loop-task-implementer/tests/test_run_log.py` (confirmed the real, already-passing companion-test
  pattern)
- `skills/loop-task-implementer/reference/state-schema.yaml` (confirmed the current `plan_execution_state:`
  block matches `EXECUTION_STATE_FIELDS` exactly, pre-change)
- `skills/engineering-decision-discovery/workflow/inputs.md`, `reference/report-format.md` (confirmed the
  real `decision_scope`/`status`/`resolved_decisions`/`unresolved_decisions` contract this design consumes)
- `docs/skill-framework/shared/cross-skill-escalation.md`, `docs/skill-framework/shared/prompt-injection.md`
  (confirmed the real existing table formats and precedent rows)
