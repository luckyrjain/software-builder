# Architecture review — A5 durable plan-state store and Builder checkpoint

**Decision: Approved with conditions**

Sound overall: both components deliberately reuse existing, already-correct repo infrastructure
(`scripts/atomic_write.py`, `run_log.py`'s directory/locking conventions, `implementation_plan.py`'s
already-tested in-memory CAS logic, `orchestrator.md §5`'s existing branch verification) rather than
inventing new mechanisms — a good sign for a solo-maintainer repo where every new subsystem is a new
thing to keep correct forever. Four gaps need closing before/during implementation, none of them a
redesign.

## Architecture decision

Two components close gap-backlog ticket A5. (1) A durable `plan_execution_state` store: a JSON file
plus a sibling `flock`-protected lock file, keyed by `plan_id` (not `run_id`, since the Orchestrator's
own resume semantics require state to survive a `run_resumed` event spanning multiple `run_id`s),
stored outside any git repository mirroring `run_log.py`'s `<home>/.software-builder/...` convention,
written via the already-existing `scripts/atomic_write.py`, wrapping the already-implemented in-memory
`advance_plan_execution_state` generation-based compare-and-swap rather than inventing a new consistency
model. (2) A Builder in-flight checkpoint, achieved not by a new storage channel (Builder is
architecturally barred from the run log and from `plan_execution_state`, which only the Orchestrator
mutates) but by a workflow change: `builder.md`'s commit/push cadence moves from "once, at the very
end" to "after each milestone," with a commit-message marker naming the milestone reached. A crash after
milestone N leaves real git-native evidence the Orchestrator's *already-existing* branch/PR verification
logic (`orchestrator.md §5`) can detect on resume, dispatching a fresh Builder told to continue rather
than restart from zero.

Motivation: `plan_execution_state` has zero persistence code anywhere in the repo today (confirmed by
direct grep — every reference is either the schema declaration, prose stating non-durability, or
in-memory-only validate/reconcile functions); a Builder that dies before its single final report loses
all unpushed work, detected only by a 30-minute timeout with no partial-progress signal.

## Risks

| Risk | Section | Severity | Notes |
|------|---------|----------|-------|
| Lock-acquisition has no stated timeout behavior — a crashed process holding the lock could wedge every future Orchestrator invocation against that `plan_id` forever | Failure modes | Blocking | See Conditions §1 |
| Design doesn't explicitly require the new store's directory to refuse a path inside any git repository, the way `run_log.py` does | Security | Blocking | See Conditions §2 |
| No stated retention/cleanup policy for an abandoned plan's state file (a plan started and never resumed leaves its file forever) | Operability | Conditional | See Conditions §3 |
| Builder's milestone commit-message marker is untrusted, PR-author-adjacent content; design doesn't explicitly say the Orchestrator must treat it as a hint to re-verify, never as authoritative evidence on its own | Security | Conditional | See Conditions §4 — consistent with existing "Builder prose is never sole source of merge-gate truth" doctrine (`orchestrator.md §13`), but worth stating explicitly since this is new surface |

## Scale limits

| Dimension | Breaks down at | Evidence |
|-----------|-----------------|----------|
| Concurrent `plan_execution_state` files | Not a realistic constraint — bounded by concurrent in-flight plans on a solo-maintainer repo, single-digit in practice | `design_description`; no stated scale target, consistent with this repo's actual usage pattern |
| `task_statuses`/`completed_evidence_refs` growth within one file | Bounded by the plan's own task count for `task_statuses` (fixed at plan-build time); `completed_evidence_refs` is a list that could in principle grow unboundedly across many resume cycles on one plan — `design_description` doesn't state a cap | Unknown — no stated bound; recommend `implementation-planner`/`system-design` name one, even a generous one, rather than leaving it open-ended |
| Lock contention (two Orchestrator processes on the same `plan_id`) | The scenario `orchestrator.md` itself already names as real: "The platform has no atomic cross-process lease... collision-safe, not exactly-once" | Not a new risk this design introduces, but the store's lock is the first place that statement becomes concretely testable — see Conditions §1 for the timeout gap |

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| Torn/partial write to the state file | N/A — prevented structurally | `atomic_write.py`'s tempfile-then-`os.replace` means a reader never observes a partial write | Reuses existing, already-correct utility |
| Two Orchestrator processes contend for the same `plan_id`'s lock | `flock` blocks the second caller | **Unknown — no stated timeout or error path** | See Conditions §1 |
| A crashed process holds the lock indefinitely | None stated | None stated | Same gap as above; `install_engine.py`'s `held_lock()` already has a `wait_timeout`-and-raise pattern this repo could mirror |
| Stale/mismatched `plan_digest` on a resume attempt | Already handled — `reconcile_plan_state` returns `BLOCKED` for a digest mismatch (existing, tested code) | Caller must reselect/rebuild the plan | No gap; the store just needs to surface this existing function's verdict faithfully |
| Builder dies after milestone N, before pushing milestone N+1's commit | Orchestrator's existing branch/PR verification (`orchestrator.md §5`) observes the branch stalled at milestone N's commit | A fresh Builder is dispatched with the branch's current state as context, told to continue from milestone N rather than restart | The core mechanism this design proposes; sound, reuses existing detection logic |
| Builder's milestone marker in the commit message is wrong, stale, or (if ever untrusted-content-adjacent) misleading | None stated as a distinct check | None stated | See Conditions §4 |

## Security

| Concern | Trust boundary / data flow | Blast radius | Notes |
|---------|------------------------------|---------------|-------|
| New durable-state directory's location relative to any git working tree | A Builder edits its own working tree; if the state directory sits inside a repo (or inside a Builder's worktree), Builder-authored content could tamper with Orchestrator state it must never touch, mirroring exactly the reason `run_log.py` refuses this today | Compromise of Orchestrator's own execution-tracking state by the actor it's tracking | See Conditions §2 |
| File/directory permissions on the new store | Local filesystem, single-user machine — same trust model as `run_log.py`'s `0700`/`0600` | Low, but should still match the existing precedent rather than default to permissive | See Conditions §2 |
| Builder's commit-message milestone marker as a data source for resume decisions | Builder-authored text is not adversarial in the way a PR-author's diff is (Builder is a dispatched, scoped agent, not an arbitrary external actor) — but it is still a claim, not verified fact, and the resume logic reads it before independently re-verifying | Bounded: worst case is the Orchestrator's own re-verification catches a wrong/stale marker before acting on it, *if* the design requires that re-verification explicitly | See Conditions §4 |

## Operability

| Concern | Owner | Operating cost | Notes |
|---------|-------|------------------|-------|
| Who runs/maintains this | Repo owner (solo maintainer), same as every other skill in this repo | New directory to exist on disk; no new service, no new credential, no new scheduled job | Consistent with the rest of the repo's operability posture — not a gap unique to this proposal |
| Stale state-file accumulation | Repo owner | **Unknown — no stated retention/cleanup policy** | See Conditions §3 |

## Alternatives considered

| Alternative | Why not chosen | Notes |
|-------------|-------------------|-------|
| Reconstruct `plan_execution_state` entirely from a richer run-log event stream (event-sourcing) instead of a separate snapshot store | `design_description` doesn't state this explicitly, but the research grounding it cites (`run-log.md`'s own redaction rules) already establishes the run log deliberately excludes rich state like `task_statuses`/`current_task_id` from its `data` field by design — extending the log's schema to carry this would be a materially bigger change (redaction-rule surface, event-replay reconstruction logic) than a separate CAS snapshot file for a net-equivalent outcome | Recommend `system-design` name this alternative explicitly and state this same rationale, since it's the most obvious "why not just use what already exists" question a reader will ask |
| A new Builder-writable checkpoint file (a third persistence channel alongside the run log and `plan_execution_state`) | `design_description` gives the reasoning directly: Builder is architecturally barred from the run log and from `plan_execution_state`; adding a third channel widens Builder's persistence surface and creates a consistency question between two independently-written stores (the new file vs. git) for no benefit git doesn't already provide | Sound rejection — the chosen approach (git itself as the checkpoint medium) has strictly fewer moving parts |
| Zero alternatives stated for *why* `plan_id` (not `run_id`, not a composite key) was chosen as the store's key | Addressed directly in `design_description` via `orchestrator.md`'s own resume-across-`run_resumed` semantics — this is a real, cited rationale, not an omission | No gap |

## Conditions

1. **Define the lock's timeout/error behavior before implementation.** Mirror `install_engine.py`'s
   `held_lock()` — a bounded `wait_timeout`, polled, raising a named error (e.g. a
   `PlanStateLockTimeoutError`) that names the process/pid apparently holding the lock, rather than an
   unbounded `flock()` block. A crashed holder must not be able to wedge every future Orchestrator
   invocation against that plan.
2. **Require the new store's directory to refuse any path inside a git repository**, and adopt
   `run_log.py`'s existing permission/ownership/symlink-refusal conventions (`0700`/`0600`, ownership
   check, no symlinks) rather than defaulting to something more permissive. This closes the same
   Builder-content-adjacent tampering risk `run_log.py` already defends against.
3. **State a retention/cleanup policy for abandoned plans' state files**, even a simple manual one
   (e.g. "the owner periodically removes state files for plans with no run in N days") — record it in
   the design doc's Rollout/Observability section rather than leaving it silently unaddressed.
4. **Treat the Builder's milestone commit-message marker as a hint, never as authoritative evidence.**
   State explicitly (in the system design, and in `builder.md`'s updated text) that on resume, the
   Orchestrator always independently re-verifies actual branch/test/CI state before acting — the marker
   only narrows *what* to re-verify and *where* to resume from, consistent with this skill's existing
   "Builder prose is never sole source of merge-gate truth" doctrine (`orchestrator.md §13`).

None of these four block starting a `system-design` pass — they're precise, implementable requirements
for that pass to satisfy, not open architectural questions.
