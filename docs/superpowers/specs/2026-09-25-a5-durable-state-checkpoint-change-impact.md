# Change impact report — A5 durable plan-state store and Builder checkpoint

**title:** A5 — durable `plan_execution_state` store and Builder in-flight checkpoint
**assessment_target:** [2026-09-25-a5-durable-state-checkpoint-design.md](2026-09-25-a5-durable-state-checkpoint-design.md) (`system_design_spec`, `proposed_state`), validated by [2026-09-25-a5-durable-state-checkpoint-architecture-review.md](2026-09-25-a5-durable-state-checkpoint-architecture-review.md) (Approved with conditions)
**coverage_status:** COMPLETE — repository read available and used to ground every field (`run_log.py`'s directory/lock/permission helpers, `implementation_plan.py`'s existing CAS functions, `atomic_write.py`, `builder.md`/`orchestrator.md`'s exact current text, `skills.yaml`'s registry entries, `CHANGELOG.md` convention, `scripts/README.md`/`scripts/tests/` conventions all read directly)
**criticality:** High — `skills/loop-task-implementer/workflow/orchestrator.md` and `builder.md` are the two files ~40+ other skills' `repository-write` executor path routes through (ADR 0008); any edit to them, even purely additive, is higher-blast-radius than a typical single-script change, since a subtle regression here could affect every future `loop-task-implementer` run across every skill that uses it as an executor

## material_unknowns

None material enough to block Phase 0 authoring. `impacted_owners`/`review_triggers` below name a
recommended (not required) extra look at the two workflow-file edits given their blast radius.

## change_classes

- **New pure modules**: `scripts/plan_state_store.py`, `scripts/builder_resume.py` — both additive, no existing code calls either yet (they become load-bearing only once `orchestrator.md`'s text is updated to call them, Rollout Phase 1)
- **New tests**: `scripts/tests/test_plan_state_store.py`, `scripts/tests/test_builder_resume.py`
- **Additive documentation edits to core executor workflow files**: `skills/loop-task-implementer/workflow/builder.md` (new commit/push cadence + `Checkpoint:` trailer convention, gated on existing `allowed_actions.commit`/`.push` flags — no change to those flags' own semantics), `skills/loop-task-implementer/workflow/orchestrator.md` (two new call-outs: `plan_state_store.cas_advance` at the existing reconcile-state step, `builder_resume.decide` before dispatching to a task with a pre-existing branch) — both are additions to existing sections, not rewrites of existing instructions
- **Changelog entry**: `skills/loop-task-implementer/CHANGELOG.md` (new dated section, matching the existing "Unreleased — default task budgets and run log" convention)
- **Doc-only, Phase 2, deferred**: a retention/cleanup policy note (Condition 3) — no code
- **No workflow YAML, no `docs/github-ruleset-main.json`, no `skills.yaml` registry change** (the skill's `write_authority`/capability declarations are unaffected — this adds internal implementation detail to an already-registered skill, not a new skill or a new declared capability)

## impacted_repositories

- `luckyrjain/software-builder` only.

## impacted_services

- N/A — local CLI/file-based tooling, no runtime service.

## impacted_contracts

- **`plan_execution_state`'s schema** (`skills/loop-task-implementer/reference/state-schema.yaml`): unchanged — the design explicitly reuses the existing 11-field shape verbatim. No consumer of that schema needs to change.
- **`scripts/implementation_plan.py`'s public functions** (`advance_plan_execution_state`, `initial_plan_execution_state`, `reconcile_plan_execution_state`, `reconcile_plan_state`, `merge_plan_state`): unchanged, called but not modified — `plan_state_store.py` is purely an additive caller. Confirmed via direct read: no existing call site of these functions exists yet outside their own test file (`scripts/tests/test_plan_execution_state.py`), so there is no risk of this change altering behavior any existing caller depends on.
- **`builder.md`'s Builder output contract** (§8, the YAML shape a Builder returns): unaffected — the new checkpoint commits are additional intermediate git operations, not a change to the final report's field list.
- **`orchestrator.md §5`'s branch/PR verification contract**: unaffected — this design adds a new call-out (`builder_resume.decide`) that consumes facts §5 already gathers; §5's own verification steps are unchanged.
- **New internal contract**: the `Checkpoint: <token>` commit-message trailer convention. No external consumer today; `builder_resume.py`'s parser is its only reader.

## impacted_data

- New on-disk data: one JSON file per `plan_id` under `~/.software-builder/plan-state/`, plus a sibling `.lock` file per plan_id — new data, no migration of anything existing (no plan-state files exist anywhere today, confirmed by the design's own research: zero persistence code exists for this schema anywhere in the repo).
- No change to `run_log.py`'s own `~/.software-builder/runs/` directory or file format.

## impacted_dependencies

- **`scripts/README.md`** (confirmed convention via direct read, rows for `check_review_evidence.py`/`sensitive_path_match.py`/`lock_safety_patterns.py` etc.) — needs two new rows, one per new script.
- **`scripts/tests/test_<script>.py` naming convention** (confirmed: `test_check_review_evidence.py`, `test_lock_safety_patterns.py`, etc. all follow this pattern) — `test_plan_state_store.py`/`test_builder_resume.py` match it directly.
- **`make lint-python`** sweeps both new scripts automatically, same as every prior F1 script — confirmed no Makefile wiring needed (same finding as F1's own change-impact reports).
- **`skills/loop-task-implementer/CHANGELOG.md`** — confirmed active convention (dated "## Unreleased — ..." sections); this change should add its own entry, matching the existing run-log-addition entry's structure and level of detail (bullet list of what changed, cross-referenced to the pressure tests added).
- **No new PyPI dependency** — both new modules are stdlib (`fcntl`, `json`, `os`, `tempfile` via the reused `atomic_write.py`) plus a plain-function dependency on the existing `scripts/implementation_plan.py`, consistent with every other script this repo has added for F1.
- **`skills.yaml`'s `loop-task-implementer` registry entry** (lines 821, 968, 1021, 1061, 1099 per direct grep) — read and confirmed this change touches none of the fields registered there (`write_authority`, capability declarations); no registry regeneration (`make generate`) is required, since nothing in `skills.yaml` itself changes. Worth an explicit `make generate`/`make lint-static` run anyway as a no-regression sanity check, since these are core-skill files.

## impacted_owners

- **Repo owner (`@luckyrjain`)**: sole owner, unchanged. No new credential, no new operational owner.

## required_tests

- `scripts/tests/test_plan_state_store.py`: CAS success (generation N → N+1); CAS rejection (stale `expected_generation`, raises `PlanStateCasError`); lock-timeout behavior (a held lock in a second process/thread causes the configured `timeout` to elapse and raise `PlanStateLockTimeoutError`, mirroring how `run_log.py`'s own test suite pressure-tests its `_locked()` — check that test file's approach first and match it); directory-refusal (a `state_dir` resolving inside a git repository is refused, mirroring `run_log.py`'s `test_resolve_log_dir_refuses_repository`-shaped test if one exists); malformed/corrupt existing state file → `PlanStateStoreError`, fail closed; `completed_evidence_refs` cap (merged count exceeding `MAX_COMPLETED_EVIDENCE_REFS=1000` raises rather than silently truncating or growing).
- `scripts/tests/test_builder_resume.py`: `FROM_SCRATCH` (no branch/no commits), `CONTINUE_FROM` (one checkpoint marker present, correct ordering), `CONTINUE_FROM` (both markers present, in order), `ESCALATE` (commits with no recognized marker), `ESCALATE` (markers present but out of expected order — `tests-passing` with no prior `implementation-complete`).
- `make lint-python`, `make lint-static`/`make generate` (sanity check that the `skills.yaml` registry-derived artifacts, e.g. `cli/sb/_registry_snapshot`, don't drift — this change shouldn't touch them, but core-skill-file edits are exactly the class of change worth this extra check per the architecture review's own emphasis on blast radius here).

## operational_impacts

- **New directory on disk**: `~/.software-builder/plan-state/`, created on first use, same operational shape as `~/.software-builder/runs/` already has today (no new provisioning step, no new credential).
- **New commit cadence for `loop-task-implementer` Builders**: 2 additional small commits per task (when `allowed_actions.commit`/`.push` are both true) instead of 1 — negligible additional git history noise, bounded by task count, not by anything unbounded.
- **No impact on required CI checks** — this change ships no workflow-file edits.
- **Behavior is dormant until Rollout Phase 1's doc edits land** — Phase 0 (the two new modules + tests) can merge and be reviewed independently with zero behavioral effect on any live `loop-task-implementer` run, since nothing calls them yet. This is a real, useful phasing property worth preserving in the implementation plan: Phase 0 and Phase 1 are safely separable, and Phase 0 alone is a complete, mergeable, testable unit.

## review_triggers

- No hard trigger under this skill's own vocabulary (`security-review`/`api-design-review`/`database-review`/`observability-review`) — this is local file-based tooling with no external API surface, no database, no new attack surface beyond what `run_log.py`'s already-reviewed pattern already accepts as its risk model.
- **Recommended, not required**: given the criticality note above (core executor files, ~40+ skills route through them), the Phase 1 edit to `orchestrator.md`/`builder.md` specifically — not the Phase 0 code — is worth an extra careful look during `loop-task-implementer`'s own Reviewer lenses (both Lens A and Lens B naturally cover this ground already; no separate specialist skill invocation is warranted for a doc-only addition of this size).

## unknowns

- Exact mechanism for naming the lock's apparent holder in `PlanStateLockTimeoutError` — design's own Open Questions already name this as an implementation detail, not architecturally significant.
- Whether `orchestrator.md §12`/`§20`'s exact call-site wording needs its own sub-edit beyond "add a call-out" — a sequencing detail for the Builder to resolve against the current exact text, per the design's own Open Questions.

## evidence_refs

- `docs/superpowers/specs/2026-09-25-a5-durable-state-checkpoint-design.md` (system design spec, full document)
- `docs/superpowers/specs/2026-09-25-a5-durable-state-checkpoint-architecture-review.md` (architecture review, Approved with conditions)
- `scripts/implementation_plan.py` lines 1090-1492 (existing CAS/reconcile functions, confirmed no existing external caller beyond their own test file)
- `skills/loop-task-implementer/scripts/run_log.py` lines 715-856 (directory/lock/permission helpers this design mirrors)
- `scripts/atomic_write.py` (reused, not reimplemented)
- `scripts/README.md`, `scripts/tests/` directory listing (documentation/naming conventions)
- `skills/loop-task-implementer/CHANGELOG.md` (changelog convention)
- `skills.yaml` lines 821, 968, 1021, 1061, 1099 (`loop-task-implementer` registry entries, confirmed unaffected)
- `skills/loop-task-implementer/workflow/builder.md`, `workflow/orchestrator.md` (current text these edits are additive to)
