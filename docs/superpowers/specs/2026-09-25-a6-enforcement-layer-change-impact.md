# Change impact report — A6 permission template and run-identity lease

**title:** A6 — permission template and run-identity lease
**assessment_target:** [2026-09-25-a6-enforcement-layer-design.md](2026-09-25-a6-enforcement-layer-design.md) (revision 3, `proposed_state`), validated by [2026-09-25-a6-enforcement-layer-architecture-review.md](2026-09-25-a6-enforcement-layer-architecture-review.md) (Approved with conditions)
**coverage_status:** COMPLETE — repository read used to ground every field, including a direct check of `run_log.py`'s `EVENTS` validation mechanics (not assumed) that surfaced a real gap the design's Rollout plan didn't fully specify (see `impacted_dependencies`)

## material_unknowns

`.claude/settings.json`'s content correctness against the live host's actual permission-matching
behavior is explicitly unverified by design (Rollout Phase 1 names this as a required, not yet
performed, empirical step) — this is a genuine, disclosed unknown carried forward from the design,
not a gap in this analysis.

## criticality

High — same tier as A5. This is the **third** consecutive change to `skills/loop-task-implementer/workflow/orchestrator.md`
(after F1, since reversed, and A5) and the **first-ever** change to `run_log.py`'s `EVENTS`
validation surface, a module that has been through 11 rounds of its own prior hardening (#287/#291/#294)
and is treated in this repo's own documentation as especially sensitive (it is the one component every
`loop-task-implementer` run depends on for tamper-evident audit logging). Additionally, `.claude/settings.json`
is the first tool-level (host-enforced) security control this repo ships — a defect here has a
different failure mode than a defect in an instruction-level document (a wrong `allow` entry is
silently permissive, not something an LLM reading prose could "notice is wrong" and route around).

## change_classes

- **New pure module**: `scripts/task_lease.py` (non-blocking flock primitive, no I/O beyond lock-file/directory management)
- **New test**: `scripts/tests/test_task_lease.py`
- **New security-relevant config**: `.claude/settings.json` (Claude Code's own permission-template schema; this repo's first)
- **New doc**: `skills/loop-task-implementer/reference/enforcement-layer.md`
- **Additive edits to already-shipped, high-blast-radius files**: `skills/loop-task-implementer/workflow/orchestrator.md` (three distinct additive edits — lease call-out + amended resume rule, corrected CAS-retry fork, `lease_denied` logging call-out), `skills/loop-task-implementer/scripts/run_log.py` (one line added to `EVENTS`, **plus a required companion validation-rule addition the design doc does not explicitly call out — see `impacted_dependencies`**), `skills/loop-task-implementer/SKILL.md` (one new cross-reference link)
- **No workflow YAML, no `docs/github-ruleset-main.json`, no `CODEOWNERS` change** (already covered by the existing wildcard, per the design's own Data model section)

## impacted_repositories

- `luckyrjain/software-builder` only.

## impacted_services

- N/A — local CLI/file-based tooling plus a host-level (Claude Code) permission config; no runtime service.

## impacted_contracts

- **`run_log.py`'s `EVENTS` tuple and its per-event validation** (confirmed via direct read, not assumed): `EVENTS` at `run_log.py:120-138` is a flat tuple, but is **not the only place an event's shape is enforced** — `run_log.py:614` shows a concrete example of per-event-type field validation beyond membership in `EVENTS` (`task_selected` specifically requires a non-empty string `task_id` in `data`). **The design's Observability section says only "implementation adds `lease_denied` to that set" — this undersells the actual required change.** A correct implementation must also add a companion validation rule (mirroring the `task_selected` pattern at line 614) requiring `lease_denied`'s `data` to contain non-empty `task_id` and `lease_id` strings, matching the design's own stated data shape. Landing only the `EVENTS` tuple addition without this companion rule would make `lease_denied` appendable with an arbitrary or missing `data` payload — silently weaker validation than every other event type in the file, which is exactly the kind of inconsistency this module's own 11 rounds of hardening were meant to prevent.
- **`plan_execution_state.task_statuses`'s existing contract** (unchanged) — the corrected CAS-retry fork reads this field, doesn't modify its schema; already-established by A5, confirmed consistent by the design's own revision-3 fix.
- **`orchestrator.md §2`'s existing "never dispatch a task already BUILDING" rule** — amended, not replaced, per the design's Consistency section; the amendment is additive (a new exception clause), the base rule's existing behavior for every other case is unchanged.
- **`.claude/settings.json`'s own schema** — Claude Code's own contract, not owned by this repo; this change only populates content within an existing external schema.

## impacted_data

- New on-disk data: `~/.software-builder/task-leases/<lease_id>.lock` files (empty, existence + flock state only) — new data, no migration.
- No change to `plan_state_store`'s or `run_log`'s own existing on-disk data shapes (the `lease_denied` event is a new record TYPE within `run_log`'s existing file format, not a schema change to the file format itself).

## impacted_dependencies

- **`scripts/README.md`** — needs a new row for `scripts/task_lease.py`, matching the established convention (confirmed via direct read of the existing table).
- **`scripts/tests/test_<script>.py` naming convention** (confirmed, established by every prior F1/A5 script) — `test_task_lease.py` matches directly.
- **`run_log.py`'s validation surface, corrected scope** — as detailed in `impacted_contracts` above: the design's stated change ("add to `EVENTS`") is necessary but not sufficient; a companion field-validation rule at/near `run_log.py:614`'s pattern is required too. Flagged here as a concrete, evidence-grounded correction to the design's own Rollout Phase 2 scope, not a new open question — the fix is well-defined once the gap is named.
- **`make lint-python`** sweeps the new script automatically — confirmed, same finding as every prior script this session.
- **No new PyPI dependency** — `task_lease.py` is stdlib (`fcntl`, `hashlib`, `os`), consistent with every sibling module.
- **`.claude/settings.json`'s dependency on the live host's actual behavior** — not a repository dependency in the usual sense, but the single most consequential "external dependency" this change has: its safety properties depend entirely on Claude Code's real permission-matching semantics, which this repo cannot pin, version, or test in CI the way it can test its own Python code. Flagged as the change's primary residual risk, matching the design's own Rollout Phase 1 requirement.

## impacted_owners

- Repo owner (`@luckyrjain`), sole owner, unchanged.

## required_tests

- `scripts/tests/test_task_lease.py`: single-process acquire/release; same-process double-`try_acquire`-fails-immediately; infrastructure-failure raises `TaskLeaseError` (not `None`) for a disk/permission failure (e.g. point `lease_dir` at an unwritable path); a genuine cross-process test reusing `scripts/tests/install_lock_test_helpers.py`'s `spawn_lock_holder` pattern (real subprocess, real held flock) asserting a second real `try_acquire()` returns `None` immediately — per the design's Rollout Phase 0.
- **New test for the corrected `run_log.py` validation** (the gap this report names above): a test asserting `append(..., event="lease_denied", data={"task_id": "...", "lease_id": "..."})` succeeds, and a companion test asserting it's rejected (exit 2, matching every other malformed-event case in this file) when `task_id`/`lease_id` is missing or empty — mirroring whatever existing test already covers `task_selected`'s field requirement, so the new event type gets equivalent coverage, not weaker coverage.
- **Design's own Phase 2 acceptance test**: two real, separate `loop-task-implementer` invocations targeting the same task, asserting the second's run log contains `lease_denied` and that it selects a different task rather than double-dispatching — already specified in the design, restated here as a required test, not optional.
- `.claude/settings.json` empirical verification (design's Rollout Phase 1, restated as a required, checkable step, not prose): manually exercise each `allow` entry once and confirm it doesn't prompt; manually exercise each `deny` entry once and confirm it's refused; manually exercise the historically-exploited chain (`git add -f .env`, etc. — now moot since `add`/`commit`/`push` are no longer allow-listed at all in revision 3, but worth a smoke-check that they correctly fall through to a prompt rather than silently erroring).
- `make lint-python`, `make lint-static` — standing no-regression checks for a change touching core skill files.

## operational_impacts

- **New security-relevant config file the owner must personally trust** — unlike every other component this session built, `.claude/settings.json`'s correctness cannot be fully verified by CI or by this repo's own test suite; it depends on the live host. This is the first component this session has produced where "all tests pass" does not equal "this is definitely safe" — worth the owner's own attention before/shortly after this merges, not just trusting green CI.
- **New Actions minutes**: none — no CI workflow changes.
- **No impact on required checks** — `lint-static`/`lint-suites` remain the only required checks.
- **Removed friction-reduction scope relative to the original ticket's spirit**: revision 3's `.claude/settings.json` no longer allow-lists `git add`/`git commit`/`git push`/`gh pr create`/`gh pr comment` — the operations a Builder actually performs most often still prompt per-use. This is a deliberate, disclosed trade-off (see design's own revision-3 rationale), not an oversight, but it does mean this ticket's friction-reduction benefit is smaller than originally scoped. Worth the owner knowing this plainly rather than discovering it after the fact.

## review_triggers

- No hard trigger under this skill's own vocabulary — no external API, no database, no new attack surface beyond what's already been adversarially reviewed twice at the design level.
- **Recommended, not required**: given `run_log.py`'s sensitivity (11 prior hardening rounds) and this being its first-ever event-type addition, the implementation's specific edit to that file is worth the same "extra scrutiny" flag A5's change-impact report gave `orchestrator.md`/`builder.md` — both review lenses already cover this ground; no separate specialist skill invocation is warranted for a change this contained.

## unknowns

- `.claude/settings.json`'s actual behavior against the live host — explicitly named, unresolved by design, resolved only by Rollout Phase 1's empirical step (implementation-time, not analysis-time).
- Whether a future revision re-admits `commit`/`push`/`add` to the allow list once Phase 1's verification establishes the host's matcher is precise enough — explicitly deferred by the design itself, not part of this change's scope.

## evidence_refs

- `docs/superpowers/specs/2026-09-25-a6-enforcement-layer-design.md` (revision 3, full document)
- `docs/superpowers/specs/2026-09-25-a6-enforcement-layer-architecture-review.md` (architecture review, Approved with conditions)
- `skills/loop-task-implementer/scripts/run_log.py:115-144,614` (EVENTS tuple, LOCK_TIMEOUT_SECONDS, and the concrete per-event validation example that grounds this report's `impacted_contracts` finding)
- `scripts/README.md`, `scripts/tests/` directory listing (documentation/naming conventions)
- `skills/loop-task-implementer/workflow/orchestrator.md` (current text these edits are additive to)
- `CODEOWNERS` (confirmed wildcard coverage, no new entry needed)
