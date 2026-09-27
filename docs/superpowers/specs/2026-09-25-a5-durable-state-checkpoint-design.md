# System Design Spec — A5 durable plan-state store and Builder checkpoint

**Readiness: Ready with open questions.**

**Source:** [2026-09-25-a5-durable-state-checkpoint-architecture-review.md](2026-09-25-a5-durable-state-checkpoint-architecture-review.md) (Approved with conditions — all 4 addressed below).

## Components

| Component | Responsibility | Boundary / owns | Notes |
|-----------|-----------------|------------------|-------|
| `scripts/plan_state_store.py` (new) | Durable read/CAS-write of one plan's `plan_execution_state`, keyed by `plan_id`. Wraps `scripts/implementation_plan.py`'s existing `advance_plan_execution_state`/`initial_plan_execution_state` (unchanged, in-memory, already tested) with a locked, atomic file backend | Owns the on-disk file format, directory/lock conventions, and the CAS entry point (`cas_advance`); never re-implements plan/task reconciliation logic itself | Mirrors `run_log.py`'s directory (`resolve_log_dir`), permission (`_private_dir`), and lock-timeout (`_locked`, `LOCK_TIMEOUT_SECONDS=30.0`) helpers directly — not imported (they're private/underscore-prefixed, not designed for reuse) but duplicated in miniature, matching the shape `idempotency_store.py`/`aggregate_migration_status.py` already independently duplicate. See Open Questions for why extracting a shared module is deliberately out of scope here |
| Builder checkpoint (workflow change, no new module) | `builder.md`'s commit/push cadence moves from "once, at the end" to "after each of two milestones," each commit carrying a `Checkpoint: <marker>` trailer | Applies only when `allowed_actions.commit`/`.push` are both `true` — when they're `false`, behavior is unchanged (§6's existing diff-only path) | No new persistence channel; git itself (the deterministic task branch) is the durable medium |
| `scripts/builder_resume.py` (new) | Given the deterministic task branch's actual current git state (commits since base, each parsed for a `Checkpoint:` trailer), decides whether a redispatched Builder should be told `FROM_SCRATCH`, `CONTINUE_FROM(<marker>, <head_sha>)`, or `ESCALATE` (ambiguous/unrecognized state) | Pure function of git-observable facts the Orchestrator has already gathered via its existing §5 branch/PR verification — never fetches anything itself, never trusts the marker as more than a hint (Condition 4) | The Orchestrator always independently re-runs real verification (tests, diff inspection) after a `CONTINUE_FROM` decision — this function only narrows *where* to resume, never certifies correctness |

## APIs

| Endpoint / method | Contract | Consumer(s) | Notes |
|--------------------|----------|-------------|-------|
| `plan_state_store.read_state(state_dir: Path, plan_id: str) -> dict \| None` | Returns the current durable checkpoint for `plan_id`, or `None` if none exists yet (fresh plan). Read-only, still lock-protected (shared lock) against a concurrent writer mid-write | Orchestrator, on every resume/task-selection pass | Shared (`LOCK_SH`) vs. exclusive (`LOCK_EX`) locking, exactly mirroring `run_log.py`'s `_locked(fd, exclusive=...)` |
| `plan_state_store.cas_advance(state_dir, plan, *, expected_generation, authoritative_task_statuses, current_head, updated_at, completed_evidence_refs=None, blocked_reason=None, timeout=30.0) -> dict` | Under one exclusive-lock critical section: read current file (or synthesize `initial_plan_execution_state` if absent), merge `completed_evidence_refs` with whatever's already durably stored, call the existing `advance_plan_execution_state` (CAS on `state_generation`), write the result via `scripts/atomic_write.py`, return it. Raises `PlanStateCasError` on a generation mismatch (someone else advanced first — caller must re-read and retry, exactly as `advance_plan_execution_state` already signals via its `errors` return today, just surfaced as an exception at the durable-store boundary) or `PlanStateLockTimeoutError` after `timeout` seconds contending for the lock (Condition 1) | Orchestrator, once per task-completion/advancement event | The one write entry point; there is no separate bare "write" function, so a caller can never bypass the CAS check |
| `scripts/builder_resume.py: decide(branch_commits: list[CommitInfo], base_revision: str) -> ResumeDecision` | `CommitInfo` = `{sha, message, checkpoint_marker: str \| None}` (the last `Checkpoint: <token>` trailer found in `message`, or `None`). Returns `ResumeDecision(action: "FROM_SCRATCH" \| "CONTINUE_FROM" \| "ESCALATE", last_marker: str \| None, resume_head: str \| None, reason: str)` | Orchestrator, after its existing §5 branch verification determines a branch already exists for the task | Pure, no I/O — the Orchestrator gathers `branch_commits` itself (already does, per §5) and passes them in |

## Data model

| Entity | Key fields | Relationships | Owner |
|--------|-----------|-----------------|-------|
| Durable `plan_execution_state` file | Identical schema to `state-schema.yaml`'s existing 11 fields (`schema_version`, `plan_id`, `plan_digest`, `target_repo`, `state_generation`, `current_task_id`, `task_statuses`, `completed_evidence_refs`, `observed_head_revision`, `blocked_reason`, `updated_at`) — no new fields added, this is a durable backing for the exact existing shape | One file per `plan_id` | `plan_state_store.py` |
| `.lock` sibling file | Empty; existence + `flock` state only, same pattern as `idempotency_store.py`'s `.locks/<key>.lock` | One per state file, `<plan_id>.lock` | `plan_state_store.py` |
| `Checkpoint:` commit-message trailer | A single token identifying the milestone reached: `implementation-complete` (after `builder.md` §3, before running the full test suite) or `tests-passing` (after §4's full test run succeeds, before §5's final diff inspection) | Embedded in the Builder's own commit messages on the deterministic task branch — no separate storage | `builder.md`'s workflow, parsed by `builder_resume.py` |

## State machines

| Entity | States | Transitions | Notes |
|--------|--------|-------------|-------|
| Plan-state file (per `plan_id`) | `absent → generation-0 (initial_plan_execution_state, written on first cas_advance)` → `generation-N → generation-N+1 (cas_advance succeeds)` \| `generation-N → CAS_REJECTED (a concurrent advance already moved to N+1; caller re-reads and retries)` | Every transition happens inside one lock-held critical section; no partial states are ever observable by a reader (atomic replace) | Directly mirrors the plan's own task-status state machine one level up — this file is a durable mirror of in-memory state that already has a correct state machine (`advance_plan_execution_state`); this component adds no new transition logic |
| Builder task branch (checkpoint perspective) | `no_branch → implementation-complete (first checkpoint push)` → `tests-passing (second checkpoint push)` → `final (last commit, §6, no special marker needed — its existence plus a PR is the existing "done" signal)` | A crash before the first checkpoint push looks identical to `no_branch` (nothing recoverable — same as today); a crash after either checkpoint push is detected by `builder_resume.decide()` on the next Orchestrator pass | `ESCALATE` fires when commits exist but none carry a recognized marker (a third-party or unexpected push, per existing §16 handling) or when a marker appears out of the expected order (`tests-passing` before any `implementation-complete` commit — a sign of an unrecognized branch state, not a Builder-produced one) |

## Consistency

| Boundary | Model (strong / eventual) | Why |
|----------|-----------------------------|-----|
| Plan-state file writes | Strong — single-writer-at-a-time via exclusive `flock`, atomic replace, generation-based CAS | Matches `run_log.py`'s own consistency model for the same reasons: local single-machine file, no distributed consensus needed, `flock` is sufficient |
| Builder checkpoint via git push | Strong at the git-ref level — `orchestrator.md`'s existing expected-head/fast-forward push preconditions already guarantee this; this design adds no new consistency requirement here, only more frequent pushes under the same existing rules |

## Retries & idempotency

| Operation | Idempotent? | Retry / backoff strategy |
|-----------|-------------|----------------------------|
| `cas_advance` | Yes in effect — a retried call with the same `expected_generation` either succeeds once (first caller) or fails closed with `PlanStateCasError` for every subsequent caller (never double-applies); the Orchestrator's existing pattern (re-read, recompute, retry with the new `expected_generation`) applies unchanged | No new backoff logic — a CAS rejection is immediate and cheap to detect; the lock's own `timeout` (default 30s, matching `LOCK_TIMEOUT_SECONDS`) bounds how long a caller waits for the lock itself, separate from CAS rejection |
| Checkpoint push | Idempotent by construction — pushing the same commit twice is a no-op fast-forward; `orchestrator.md`'s existing collision-safe (not exactly-once) branch-write rules already cover a race between two dispatches | Unchanged from existing doctrine |

## Capacity

| Dimension | Estimate | Basis |
|-----------|----------|-------|
| Concurrent plan-state files on disk | Single-digit, bounded by concurrent in-flight plans on a solo-maintainer repo | Architecture review's own Scale limits section; not a realistic constraint |
| `completed_evidence_refs` growth (architecture review's flagged open scale question) | Capped at `MAX_COMPLETED_EVIDENCE_REFS = 1000` per plan-state file. `cas_advance` merges newly-supplied refs with whatever's already durably stored (never silently drops without signaling); if the merged count would exceed the cap, `cas_advance` raises `PlanStateStoreError` rather than either silently truncating (losing audit evidence) or growing unboundedly — a plan reaching 1000 accumulated evidence refs indicates something pathological (e.g. a runaway resume loop), not normal operation, and should escalate to a human rather than be absorbed silently | New cap, chosen generously as a safety valve, not a realistic normal-use ceiling — normal plans (per this repo's own plan sizes, e.g. F1's 9-task and 6-task plans) accumulate single-digit evidence-ref counts |

## Failure strategy

| Failure mode | Degradation / mitigation |
|--------------|-----------------------------|
| Lock held past `timeout` (default 30s) — Condition 1 | `cas_advance`/`read_state` raise `PlanStateLockTimeoutError` naming the apparent holder's PID (read the same way `run_log.py`'s own diagnostic-only PID text is written/read, or simply surfaced from `flock`'s own failure — implementation detail for the Builder to resolve against `run_log.py`'s exact pattern), never blocks the Orchestrator indefinitely |
| State directory resolves inside a git repository — Condition 2 | `resolve_state_dir` refuses (mirrors `_refuse_repository` exactly: checks the directory's own ancestor chain, the caller's cwd-enclosing repo, and `$GIT_DIR`/`$GIT_WORK_TREE`), raising before any file is touched |
| State directory has permissive permissions, is a symlink, or is owned by another user — Condition 2 | Refused the same way `run_log.py`'s `_private_dir` refuses each case, `0700`/`0600` enforced on anything this code creates |
| Torn/partial write | Structurally prevented — `scripts/atomic_write.py`'s tempfile-then-`os.replace` means a reader never observes a partial file |
| Malformed/corrupt existing state file (hand-edited, disk corruption) | `read_state` raises `PlanStateStoreError` rather than returning a synthesized "looks empty" result — fails closed, matching every other fail-closed component in this repo (`sensitive_path_match.py`'s `SensitivePathListError` is the direct precedent) |
| Builder dies before any checkpoint push | Identical to today's behavior — nothing recoverable, 30-minute timeout, restart from scratch. Not a regression; this design closes the *post-first-checkpoint* gap, not every gap |
| Builder dies after a checkpoint push | `builder_resume.decide()` returns `CONTINUE_FROM` with the last marker and head SHA; Orchestrator dispatches a fresh Builder with that branch state as context and an explicit instruction to continue, not restart. The fresh Builder still independently re-verifies (re-runs tests, re-inspects the diff) before proceeding — the marker is a hint about *where*, never a certificate that the prior work was correct (Condition 4) |
| Branch has commits but none carry a recognized `Checkpoint:` marker (unexpected/third-party push) | `builder_resume.decide()` returns `ESCALATE` — this is exactly the class of situation `orchestrator.md §16` (third-party branch changes) already requires pausing and escalating for; this design routes into that existing handling rather than inventing a parallel one |
| A marker appears out of expected order (e.g. `tests-passing` with no prior `implementation-complete`) | `ESCALATE` — treated as an unrecognized/ambiguous state, never guessed at |

## Observability

| Signal | What's measured |
|--------|-------------------|
| `PlanStateLockTimeoutError`/`PlanStateCasError`/`PlanStateStoreError` occurrences | Surfaced directly to the Orchestrator's own escalation path (`orchestrator.md §19` escalation report already has a `supporting_evidence` list this fits into) — no new dashboard needed for a single-machine, solo-maintainer tool |
| `builder_resume.decide()`'s `ESCALATE` outcomes | Same escalation path — an `ESCALATE` is itself evidence worth recording in the run log as a distinct finding, the same way any other third-party-branch-change escalation already is |

## Rollout plan

| Phase | Scope | Notes |
|-------|-------|-------|
| 0 | Implement `scripts/plan_state_store.py` (with unit tests: CAS success/rejection, lock-timeout simulation via a held lock in a second process/thread, directory-refusal cases mirroring `run_log.py`'s own test shapes, malformed-file fail-closed, `completed_evidence_refs` cap) and `scripts/builder_resume.py` (unit tests: `FROM_SCRATCH`/`CONTINUE_FROM`/`ESCALATE` for each of the failure-strategy rows above — this is the pressure test the ticket's acceptance criteria ask for, driven against synthetic commit lists rather than a literal killed agent session, per the architecture review's own reasoning for why that's the right test shape here) | No workflow-file changes needed — this is pure Python, no CI wiring beyond the existing `lint-python`/test sweep |
| 1 | Update `skills/loop-task-implementer/workflow/builder.md` (commit/push cadence, `Checkpoint:` trailer convention) and `workflow/orchestrator.md` (call `plan_state_store.cas_advance` at the existing "reconcile plan execution state" step already named in §12/§20; call `builder_resume.decide` before dispatching a Builder for a task that already has a branch) | Doc-only changes to already-existing workflow files; no behavior change until an actual `loop-task-implementer` run exercises the new paths |
| 2 | Retention/cleanup policy (Condition 3): document in `skills/loop-task-implementer/reference/run-log.md` or a new short note alongside `plan_state_store.py`'s own module docstring — a simple, manual policy (e.g. "the owner periodically removes state files under `~/.software-builder/plan-state/` for plans with no `COMPLETE`/`ESCALATED` resolution and no activity in N days") rather than an automated sweep, consistent with this repo's existing operability posture (solo maintainer, no scheduled cleanup jobs for `run_log`'s own directory either, per the research that found none) | No code required for this phase — a documentation-only close-out of Condition 3 |

## Open questions

- **Deliberately out of scope**: extracting a shared `scripts/private_local_storage.py` module so `run_log.py` and `plan_state_store.py` stop independently duplicating directory/lock/permission logic (the architecture review's own "don't repeat this a third time" note). Rejected for *this* change specifically because refactoring `run_log.py` — a mature, heavily-hardened module that has already been through 11 rounds of prior review (#287/#291/#294) — inside the same change that introduces new functionality risks regressing something already correct, for a code-cleanliness benefit that doesn't block A5's own acceptance criteria. Worth its own future ticket.
- Exact mechanism for naming the lock's apparent holder in `PlanStateLockTimeoutError` (a PID diagnostic write/read, mirroring `install_engine.py`'s `_write_holder_pid`/`_read_holder_pid`, vs. simply surfacing the raw `OSError` from `flock`) — left to the implementation, not architecturally significant either way.
- Whether `orchestrator.md §20`'s run-log integration point and this design's `cas_advance` call site should be the *same* Orchestrator step or two adjacent ones — a sequencing detail for `implementation-planner`/the Builder to resolve against the current exact text of §12/§20, not a design-level open question.
