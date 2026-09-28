# System Design Spec — B1: optional clarify step in loop-task-implementer's task selection

**Readiness: Ready to implement**

Revision 4, after round 3 of adversarial review found two narrow, mechanical bugs in revision 3's own
stated code (an undefined-variable reference; an unbacked "distinguishable signal" claim) and one genuinely
new, serious gap missed by rounds 1-2: the resolved clarification never reached the Reviewer, defeating
independent review exactly for the highest-risk case. **Round 4 (Security Architect, final) confirmed all
three fixes genuinely correct against the real code and real tests — verdict CLEAN.** This design has now
been through 4 full adversarial rounds, matching the depth this session's other shared-core-file change
(F2) needed, appropriate given `orchestrator.md` is this repo's single highest-blast-radius file. See
Revision history.

Revision 3, after round 2 of adversarial review confirmed 7 of revision 2's 8 fixed findings are
genuinely correct, but found the N=3 mechanism doesn't actually bound anything (no procedural hook exists
anywhere in `engineering-decision-discovery`'s own tree/frontier logic), the clarify-entry lease's
non-collision claim didn't match `task_lease.py`'s real fixed-arity signature, a TOCTOU gap between lease
acquisition and invocation, and that the resolved-clarification data shape didn't match the real
`engineering_decision_record` schema. See Revision history.

## Revision history

**Revision 1 → 2**: see the prior revision's own history entries — fixed 8 round-1 findings including an
unimplementable write path, a fresh-plan-breaking initializer gap, a false compatibility claim, and two
fabricated precedents. Kept for record, not repeated here at full length.

**Revision 2 → 3, round 2 findings:**

- **SRE (blocking, most consequential)**: N=3 embedded as prompt guidance has **zero procedural hook**
  anywhere in `engineering-decision-discovery`'s own mechanics — `tree.md`'s decomposition is
  evidence-driven only (ignores any number in the question text), `frontier.md` allows unbounded
  independent-node fan-out per round, and deferral is a human-initiated action with nothing tying it to
  "3." This isn't cosmetic — combined with the clarify sub-step never being added to §3's enumerated
  pre-dispatch budget check, a genuinely confusing task could consume significant budget on an interview
  before a Builder for *any* task in the plan ever runs, worse than revision 1's broken-but-conceptually-
  bounded hard cap. **Fixed**: two separate, honest mechanisms instead of one dishonest one. (1) "3
  questions" stays as prompt-level *steering*, explicitly disclosed as unenforceable guidance, not a
  bound — Condition 3 is satisfied by naming a concrete number for the guidance, not by claiming it's
  hard-enforced. (2) A **real, externally-enforceable** bound comes from a different, already-existing
  mechanism: this file's own standing circuit breaker, "a dispatched Builder or Reviewer session exceeds
  its response-wait budget" (`SKILL.md:117`, cross-referenced from `orchestrator.md` §3/§15) — extended to
  explicitly cover the clarify sub-step's dispatch too. The Orchestrator controls the dispatch regardless
  of what the sub-agent does internally, so this is genuinely enforceable, requires no change to
  `engineering-decision-discovery` itself, and reuses an existing, already-reviewed mechanism rather than
  inventing a new one.
- **Software Architect (blocking) + Security Architect (independently, same root cause)**: the clarify-entry
  lease's "suffixed lease id, never colliding with the Builder-dispatch lease" claim didn't match
  `task_lease.derive_lease_id`'s real fixed 3-argument signature (`repo, base_branch, task_id` — no
  purpose/kind parameter). Read literally, calling it unmodified with the same three inputs for both
  leases produces the *identical* id — always colliding, the opposite of the claim. **Fixed**: the exact,
  unambiguous formula is now stated — `derive_lease_id(repo, base_branch, f"{task_id}:clarify")`, an
  **input-side** modification to the `task_id` argument before calling the existing, completely unmodified
  function. SHA-256 collision resistance gives non-collision with the real Builder-dispatch lease
  (`derive_lease_id(repo, base_branch, task_id)`) with cryptographic, not just "high," confidence.
- **Software Architect + Security Architect (independently, same root cause)**: no re-check of
  `clarifications[task_id]` between acquiring the clarify-entry lease and invoking the interview — a
  sequential (not simultaneous) race where a second process's stale "absent" read, followed by a delayed
  lease acquisition after the first process already resolved and released, would trigger a fully redundant
  interview. This is exactly the discipline `orchestrator.md` already states for the Builder-dispatch lease
  ("a successful acquisition is not a license to skip verification... independently re-check... before
  treating the task as safe to restart") but the new lease's design never carried forward. **Fixed**:
  standard double-checked locking — re-read `clarifications[task_id]` immediately after acquiring the
  lease, before invoking `engineering-decision-discovery`; if now `RESOLVED`, skip the interview entirely.
- **Security Architect (blocking)**: `resolved_summary`'s shape didn't match the real
  `engineering_decision_record` schema — that schema's `status` is `SUCCESS|PARTIAL|BLOCKED` (not
  `RESOLVED|OPEN`), and resolutions come back as a `resolved_decisions` **table** (node, selected option,
  decided-by, stated reason — potentially multiple rows), not a single string. **Fixed**: the exact mapping
  is now stated (`SUCCESS -> RESOLVED`; `PARTIAL`/`BLOCKED` -> `OPEN`, detected via `status` and/or an
  `unresolved_decisions[]` entry reasoned `"explicitly deferred by the user"` — both real, structured
  fields, confirmed present in `reference/report-format.md`), and `resolved_summary`'s content is now
  explicitly bounded: a plain join of each `resolved_decisions` row's node + selected option + stated
  reason, nothing else — explicitly excluding the sub-step's own recommendation/rationale prose, keeping it
  distinct from §4's existing "no private reasoning" exclusion.
- **Security Architect (blocking)**: nothing told the Builder which of the two texts it now receives
  (original acceptance criteria, `resolved_summary`) is authoritative when they seem to address the same
  ambiguity differently. **Fixed**: §4's new bullet states explicitly that `resolved_summary`, when
  present, is authoritative for the specific ambiguity it addresses; any aspect of the acceptance criteria
  the interview never touched remains governed by the original text unchanged.
- **Software Architect (suggestions, taken)**: `reconcile_plan_execution_state` needs its own explicit
  `normalized["clarifications"] = <merged mapping>` line stated (not left implied by analogy to
  `completed_evidence_refs`'s own explicit line); `state-schema.yaml`'s `plan_execution_state:` block
  addition is now explicitly itemized as a required file change, not left to the companion test to
  discover; `MISSING_DECISION`'s pre-existing shared use by §11 Remediation is now noted explicitly for a
  future reader's clarity (not a conflict — disambiguated by `required_human_decision`/`supporting_evidence`
  either way, same as today).
- **Security Architect (suggestion, taken)**: `docs/skill-framework/shared/prompt-injection.md`'s shared
  table gets a new row too, not just `cross-skill-escalation.md` — a human's free-text clarify-interview
  answer is a genuinely new untrusted-content source this composition introduces, and the same rigor round
  1 already applied to the escalation matrix now applies here.
- **SRE (suggestions, taken)**: non-deterministic triggering (the same task can trigger or not trigger the
  clarify branch on different runs, since "sufficiently concrete" is an LLM judgment re-made fresh each
  time) is now named explicitly as a disclosed, accepted risk rather than silently omitted.

**Revision 3 → 4, round 3 findings:**

- **Software Architect (blocking)**: revision 3's stated `reconcile_plan_execution_state` line referenced
  a variable, `current`, that does not exist in that function's scope (confirmed by direct read of
  `implementation_plan.py:1410-1461` — the function's only locals are its `state` parameter and the
  deep-copied `normalized`). A Builder implementing the line as written would hit a `NameError` on first
  use. **Fixed**: corrected to `state.get("clarifications", {})` — `state` is the correct variable (traced
  through the full call chain: `cas_advance`'s own local `current` is passed as `advance_plan_execution_state`'s
  `state` parameter, which passes it straight through to `reconcile_plan_execution_state`'s own `state`
  parameter — the value is the same object, just named differently at each layer). Also corrected the
  inaccurate "mirrors the existing `completed_evidence_refs` line exactly" claim: the two are structurally
  different, not identical — `completed_evidence_refs`'s merge-with-durable-state happens one layer up,
  inside `cas_advance`, before `reconcile_plan_execution_state` is even called (that function's own line is
  a pure replace of the parameter); `clarifications`'s merge happens directly inside
  `reconcile_plan_execution_state` against `state`. Stating this precisely now, rather than the misleading
  "exact mirror" framing that likely caused the variable-name error in the first place.
- **Software Architect (blocking)**: the "budget-exhaustion-during-clarify now has its own distinguishable
  signal" claim (three places: Capacity, Failure strategy, Observability) was unbacked — traced the actual
  mechanisms (`run_log.py`'s real `EVENTS` tuple, `REASON_CODES`, and §19's escalation-report schema) and
  found none of them carry any clarify-specific marker; a response-wait-budget breach during the clarify
  dispatch produces byte-for-byte the same `escalation_reason: SESSION_TIMEOUT`/`TOKEN_BUDGET`/`TIME_BUDGET`
  report a Builder/Reviewer timeout would. **Fixed**: added a real `clarify_dispatched`/`clarify_returned`
  event pair to `run_log.py`'s `EVENTS` tuple, mirroring the existing `builder_dispatched`/`builder_returned`
  pair exactly, with the same companion doc-table requirement in `reference/run-log.md` this repo's own
  established convention already requires (confirmed real via the `EVENTS`-table test A6 relied on). The
  weaker, still-sound claim — that the response-wait-budget breaker itself is real, external, and genuinely
  bounds the clarify dispatch regardless of N=3 (`SKILL.md:117`, `orchestrator.md:232-233`) — is unchanged
  and was never in question; only the *distinguishability* of its escalation output needed a real fix.
- **Security Architect (blocking, genuinely new — missed by rounds 1-2)**: the resolved clarification never
  reached §6 "Neutral review package" or §9 "Builder rebuttal"'s admissible-evidence list — so a Reviewer
  session (which never sees `plan_execution_state`, only the neutral package it's handed) has no way to
  independently verify a Builder's reliance on a clarification, and no way to tell a legitimate
  clarify-driven change from an unexplained one. For exactly the highest-risk case the architecture review
  named (a clarify-driven change touching something Lens A would flag, like an auth check with no textual
  basis in the acceptance criteria alone), this silently defeats the independent-review safety net the
  whole dual-lens mechanism exists to provide. **Fixed**: §6's neutral package now includes
  `resolved_summary` (redacted/untrusted-tagged, same treatment as the rest of the package) when present;
  §9's admissible rebuttal-evidence categories gain a new entry backed by
  `plan_execution_state.clarifications[task_id]` specifically, so a Reviewer can check a Builder's claim
  against the real persisted record, not just the Builder's own say-so.
- **Security Architect (suggestions, taken)**: the precedence rule now has an explicit tie-breaker for the
  case a Builder can't cleanly map a resolved node to a specific acceptance-criteria clause — narrowest-scope
  default (treat as *not* covered, flag as a normal blocking-finding candidate rather than silently
  extending `resolved_summary`'s authority); disclosed explicitly that `stated_reason` (a real,
  human-authored field) can itself sometimes carry reasoning-shaped content despite the field-level
  exclusion of the sub-step's own recommendation prose — a content-level, not field-level, guarantee, named
  as an accepted characteristic rather than an absolute; the `prompt-injection.md` row is now given as exact
  literal table text, not just described narratively.
- **Software Architect (suggestions, taken)**: `validate_plan_execution_state` gains an explicit
  `isinstance(state.get("clarifications"), Mapping)` check, matching this codebase's established
  one-check-per-field convention (every other `EXECUTION_STATE_FIELDS` member already has one); the
  `task_id` collision edge case (a task literally named `"<other-id>:clarify"` colliding with another
  task's clarify-entry lease) is named as a disclosed, low-likelihood invariant rather than left implicit;
  the design now states explicitly that consuming `engineering-decision-discovery`'s return means reading
  its markdown report sections (`## Resolved decisions`/`## Unresolved decisions` table bodies), not a
  JSON/dict field on the machine-readable YAML trailer (which only carries `resolved_count`/
  `unresolved_count`/`frontier_at_completion`) — the same prose-report-reading pattern Builder/Reviewer
  reports already use elsewhere in this file, stated explicitly so a future reader doesn't expect structured
  field access that doesn't exist.

**Not yet re-reviewed**: a final, narrowly-scoped round 4 should confirm these three fixes (variable-name
correction, the new run-log event pair, the §6/§9 additions) land cleanly — none of them reopen the
mechanism itself, which round 2 already confirmed sound.

## Components

| Component | Responsibility | Boundary / owns | Notes |
|-----------|-----------------|------------------|-------|
| `orchestrator.md` §2 (extended) | New branch: check `clarifications[task_id]`; if absent and interaction available, acquire the clarify-entry lease (`derive_lease_id(repo, base_branch, f"{task_id}:clarify")`), **re-check `clarifications[task_id]` again** (double-checked locking), invoke `engineering-decision-discovery` with N=3 as disclosed-unenforceable steering, map its real `status`/`unresolved_decisions` fields to `RESOLVED`/`OPEN`, persist, release lease | Task-selection logic only | TOCTOU-closed per round 2 |
| `orchestrator.md` §4 (extended) | Builder-context bullet: `resolved_summary`, explicitly stated as authoritative for the specific ambiguity it addresses (narrowest-scope default when unclear), untrusted/redacted, scoped to the resolved decision only (never the sub-step's own recommendation/rationale prose — disclosed as a field-level, not content-level, guarantee) | Builder dispatch | Precedence rule + tie-breaker added per round 2/3 |
| `orchestrator.md` §3/§15 + `SKILL.md`'s circuit-breaker list (extended) | The existing "dispatched session exceeds its response-wait budget" breaker now explicitly names the clarify sub-step's dispatch as covered | Real, enforceable bound on interview duration | Resolves round 2's most consequential finding — N=3 itself stays soft guidance, but the dispatch is genuinely time-bounded regardless |
| `plan_state_store.cas_advance` / `advance_plan_execution_state` / `reconcile_plan_execution_state` (extended) | New `clarifications` parameter; `reconcile_plan_execution_state` gets its own explicit `normalized["clarifications"] = {**state.get("clarifications", {}), **(clarifications or {})}` line, plus a companion `isinstance(..., Mapping)` check in `validate_plan_execution_state` | The write path | Variable name corrected (`state`, not `current`) and the false "exact mirror" claim corrected per round 3 |
| `initial_plan_execution_state()` + `state-schema.yaml` (both extended) | Seeds `"clarifications": {}`; `state-schema.yaml`'s `plan_execution_state:` block gains the same key, itemized explicitly as a required file change | Fresh-plan initialization | Both halves now explicit |
| Clarify-entry lease (`task_lease.py`, reused, genuinely unmodified) | `derive_lease_id(repo, base_branch, f"{task_id}:clarify")` — exact, unambiguous formula | Never collides with the real Builder-dispatch lease (cryptographic, not just claimed, non-collision) | Formula stated precisely per round 2 |
| `engineering-decision-discovery` (existing, invoked, genuinely unmodified) | Runs its own normal interview; `status`/`unresolved_decisions[].reason` are the real, structured fields the Orchestrator reads to detect RESOLVED vs. OPEN | `decision_scope` built from `target_paths`/title/dependencies, N=3 as disclosed steering only | Confirmed by round 2 against the real schema |
| Two new Tier-2 fixtures | Regression-test unattended-skip and interactive-resolve-and-persist | `scripts/registry/eval_contracts.yaml` | Unchanged from revision 2 |

## APIs

| Endpoint / method | Contract | Consumer(s) | Notes |
|--------------------|----------|-------------|-------|
| `cas_advance(..., clarifications: Mapping[str, Any] | None = None)` | Merged by `task_id` under the exclusive lock; `reconcile_plan_execution_state` explicitly sets `normalized["clarifications"] = {**state.get("clarifications", {}), **(clarifications or {})}` (new entries win on key conflict) | Orchestrator | Corrected variable name per round 3 (`state`, not `current` — `current` doesn't exist in this function's scope) |
| §6 Neutral review package (extended) | `resolved_summary`, when present, added to the package handed to the Reviewer — same untrusted-tagging as everywhere else it appears | Reviewer (both lenses) | Closes round 3's most consequential finding — without this, the Reviewer has no way to verify a Builder's reliance on a clarification |
| §9 Builder rebuttal (extended) | New admissible rebuttal-evidence category: a citation of `plan_execution_state.clarifications[task_id]`, checkable by the Reviewer against the real persisted record, not just the Builder's assertion | Reviewer, adjudicating a rebuttal | Same fix as above, the other half of it |
| Clarify-entry lease | `task_lease.derive_lease_id(repo, base_branch, f"{task_id}:clarify")` — exact formula, input-side modification, zero changes to `task_lease.py` itself | Orchestrator, before invoking the sub-step | Precise per round 2 |
| `engineering-decision-discovery`'s real return, mapped | `status == "SUCCESS"` → `RESOLVED`; `status in ("PARTIAL", "BLOCKED")`, or any `unresolved_decisions[]` entry with `reason == "explicitly deferred by the user"` → `OPEN`. `resolved_summary` = join of each `resolved_decisions[]` row's `node`/`selected_option`/`stated_reason` — **only** this, never the sub-step's own recommendation/rationale prose | Orchestrator, consuming the sub-step's structured return directly (same pattern as Builder/Reviewer reports elsewhere in this file — no file reference) | Exact schema mapping per round 2 |
| §4 Builder dispatch (extended) | New bullet: "`resolved_summary`, when present — authoritative for the specific ambiguity it addresses; when unclear whether a clause is covered, treat it as not covered (flag as a normal blocking-finding candidate). Unresolved aspects of the acceptance criteria remain governed by the original text. Untrusted, ticket-and-interview-derived content, same scrutiny as original task text, Rule-5-redacted before persistence. Note: `stated_reason` is human-authored and may itself echo reasoning-shaped content — this is an accepted characteristic, not a leak." | Builder | Precedence rule + tie-breaker stated explicitly |
| `decision_scope` for the clarify sub-step | `{question: "Is task <task_id>'s acceptance criteria concrete enough to implement safely? As guidance only (not enforced): try to resolve within 3 questions; otherwise explicitly defer the rest and end the interview.", context: "<task's target_paths, title, dependencies>"}` | Orchestrator → `engineering-decision-discovery` | "As guidance only (not enforced)" is now stated in the prompt itself, not just the design doc |

## Events

None found.

## Data model

| Entity | Key fields | Relationships | Owner |
|--------|-----------|-----------------|-------|
| `plan_execution_state.clarifications` | `task_id -> {status: "RESOLVED" | "OPEN", resolved_summary: str | null, resolved_at: str | null}` | One entry per task that ever triggered the clarify step | `EXECUTION_STATE_FIELDS` + `state-schema.yaml`, both explicitly itemized |

Canonical `implementation_plan` remains untouched, same split A5 established.

## State machines

| Entity | States | Transitions | Notes |
|--------|--------|-------------|-------|
| A task's clarification status | `NEVER_TRIGGERED -> {RESOLVED | OPEN}` | `RESOLVED` on `status == SUCCESS`; `OPEN` on `PARTIAL`/`BLOCKED`/explicit-deferral, falls through to §19 with `escalation_reason: MISSING_DECISION` | Exact field-driven detection, per round 2 |
| Clarify-entry lease | `UNHELD -> HELD -> {STATE_ALREADY_RESOLVED (skip interview, release) | INVOKE_SUBSTEP} -> RELEASED` | The new `STATE_ALREADY_RESOLVED` branch is the double-checked-locking fix | TOCTOU-closed |
| The dispatched clarify sub-step itself | `RUNNING -> {COMPLETED | RESPONSE_WAIT_BUDGET_EXCEEDED}` | The second, real enforcement mechanism — independent of whatever N=3 guidance the human did or didn't honor | New, resolves round 2's most consequential finding |

## Consistency

| Boundary | Model (strong / eventual) | Why |
|----------|-----------------------------|-----|
| `clarifications` write | Strong, CAS-protected, genuinely reachable now | Unchanged from revision 2 |
| Two Orchestrators, same underspecified task, staggered timing | Serialized by the lease **plus** the post-acquisition re-check | TOCTOU gap closed per round 2 |

## Retries & idempotency

Unchanged from revision 2 — no new findings here.

## Capacity

| Dimension | Estimate | Basis |
|-----------|----------|-------|
| Clarify-step wall-clock cost | Bounded by the extended response-wait-budget circuit breaker (§3/§15/`SKILL.md:117`), not by N=3 (which is disclosed as unenforced steering only) | Resolves round 2's most consequential finding |
| Clarify-step token cost | Charged against the same per-task §3 budget as Builder dispatch; the clarify sub-step is now explicitly added to §3's enumerated pre-dispatch budget-check list ("before every dispatch (Builder, Reviewer, remediation, **clarify sub-step**)") | Closes round 2's SRE Finding 4 |
| Non-deterministic triggering | **Disclosed, accepted risk**: "acceptance criteria are sufficiently concrete" is an LLM judgment re-made fresh on every task-selection pass — the identical task can trigger the clarify branch on one run and not another, with no signal recorded distinguishing the two outcomes as the same task. Not solved by this design; named explicitly so a future operator isn't surprised by run-to-run divergence | Was silently omitted in revision 2; disclosed per round 2 |
| Multi-task plans with several underspecified tasks | Unchanged accepted scale limit from revision 2 | |

## Failure strategy

| Failure mode | Degradation / mitigation |
|--------------|-----------------------------|
| Clarify sub-step dispatch runs long | The extended response-wait-budget circuit breaker fires — a real, external, enforceable bound, independent of whether the human honored the N=3 steering | New, resolves round 2's most consequential finding |
| Budget exhausts during the clarify step specifically (not during Builder work) | The clarify sub-step is in §3's enumerated pre-dispatch check list, **and** a new `clarify_dispatched`/`clarify_returned` run-log event pair makes the escalation genuinely attributable, not just inferred from event absence | Fixed per round 3 — round 2's claim covered the budget *check* but not the escalation *output*; now both are real |
| Staggered-timing duplicate interview (lease freed after a stale reader's earlier snapshot) | Closed by the post-acquisition re-check | Fixed per round 2 |
| Builder receives both the original acceptance criteria and `resolved_summary`, unclear which wins | §4's new bullet states `resolved_summary` is authoritative for the specific ambiguity it addresses; everything else stays governed by the original text; a narrowest-scope default (not covered → normal blocking-finding candidate) resolves the disagreement case | Fixed per round 2/3 |
| A manipulated ticket or a human's own pasted content shapes `resolved_summary` toward an unsafe approval | Rendered under safe-output.md at question time; Rule 5 redaction and untrusted-content retagging applied again at Builder-dispatch consumption time; `prompt-injection.md`'s shared table now has an exact new row for this source | Fixed per round 2/3 |
| Fresh plan created after this change lands | `initial_plan_execution_state()` and `state-schema.yaml` both explicitly seed/declare `clarifications`; `validate_plan_execution_state` type-checks it | Both halves explicit, now type-checked too |
| Non-deterministic triggering | Disclosed, not solved (see Capacity) | New disclosure |
| Reviewer has no way to verify a Builder's reliance on a clarification is genuine | §6's neutral package now includes `resolved_summary`; §9 gains a matching admissible rebuttal-evidence category citing the real persisted record | Fixed per round 3 — the most consequential fix this round, missed by rounds 1-2 |
| Two different tasks' clarify-entry leases collide because one task's id literally equals another's `<id>:clarify` | Disclosed, low-likelihood invariant (task ids are short synthetic identifiers from `implementation-planner`, not free text) — not separately enforced | New disclosure per round 3 |

## Observability

| Signal | What's measured |
|--------|-------------------|
| `plan_execution_state.clarifications` entries | Which tasks needed clarification, resolved or left open |
| §19 `escalation_reason: MISSING_DECISION` | Reused, no new companion-test/doc-table burden |
| `clarify_dispatched`/`clarify_returned` run-log events (new) | Mirrors the existing `builder_dispatched`/`builder_returned` pair — makes a budget-exhaustion escalation during the clarify step genuinely attributable, closing round 3's finding for real |
| Response-wait-budget circuit breaker, extended | Fires distinguishably for a stuck clarify dispatch, same as it already does for Builder/Reviewer |

## Rollout plan

| Phase | Scope | Feature flag / migration order |
|-------|-------|----------------------------------|
| 0 | Tests: `cas_advance` chain's `clarifications` merge including `reconcile_plan_execution_state`'s corrected `state.get(...)` line; `initial_plan_execution_state()`/`state-schema.yaml` seeding; `validate_plan_execution_state`'s new `isinstance(..., Mapping)` check; companion field-set test; the new `clarify_dispatched`/`clarify_returned` `EVENTS` pair's own companion doc-table test (same pattern `run_log.py`'s existing events already require); clarify-entry lease contention test (real second process) **plus a new test for the post-acquisition re-check**; two Tier-2 fixtures registered in `eval_contracts.yaml` | No flag |
| 1 | Land all `orchestrator.md` edits (§2, §3, §4, §6, §9, §15, §16, §19, "## Inputs"), `SKILL.md`'s circuit-breaker list update, the extended write-path chain, the clarify-entry lease, `run_log.py`'s new `EVENTS` pair + `reference/run-log.md`'s companion table row, both `cross-skill-escalation.md` rows, the new `prompt-injection.md` row, and `state-schema.yaml` | Merge gate: both review lenses clean, `make lint-python`, fixture suite green |
| 2 (future) | `lease_denied`-style observability event for clarify-entry lease denials | Explicitly deferred |

## Open questions

- Whether round 3's three fixes (the corrected `state.get(...)` variable reference, the new
  `clarify_dispatched`/`clarify_returned` event pair, and the §6/§9 Reviewer-visibility additions) land
  cleanly — flagged for a final, narrowly-scoped round 4. None of the three reopens the mechanism itself,
  which round 2 already confirmed sound end to end.
