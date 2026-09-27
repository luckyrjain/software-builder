# System Design Spec — A6 permission template and run-identity lease

**Readiness: Ready with open questions.**

**Source:** [2026-09-25-a6-enforcement-layer-architecture-review.md](2026-09-25-a6-enforcement-layer-architecture-review.md) (Approved with conditions — all 4 addressed below; Condition 2's platform-lifetime question is addressed as a named, honest scope limit, not a proven universal guarantee — see § "Condition 2 — platform-lifetime analysis" under Failure strategy).

**Revision history.** Two rounds of 3-persona adversarial review (Security Architect, SRE, Software
Architect), matching the rigor F1's design went through earlier this session.

*Round 1 → revision 2* fixed: (1) Condition 2's resolution asserted but never argued in the body; (2)
a working, zero-prompt secret-exfiltration chain in the original allow list (`git add -f .env &&
git commit -m wip --no-verify && git push origin claude/exfil-1`); (3) the deny-precedence and
pattern-matching-model claims asserted as "verified" with no evidence; (4) the A5 CAS-retry
two-branch fix underspecified for LLM-prose execution; (5) missing failure modes (disk-full during
lease creation, a second consecutive CAS rejection, lease-denial observability).

*Round 2 → revision 3* (re-reviewing revision 2 against ground truth — official Claude Code docs, live
`gh api` branch-protection state, and this repo's own actual code — rather than trusting revision 2's
self-report) found: (6) a real vocabulary bug — the corrected CAS-retry fork checked for `"BUILDING"`,
a value from a *different* field (`task.status`) than the one it actually reads
(`task_statuses`, which can only hold PENDING/IN_PROGRESS/COMPLETE/BLOCKED) — fixed to check
`"IN_PROGRESS"`, the field's real vocabulary; (7) two further exfiltration siblings revision 2's
narrower allow list didn't cover (`gh pr comment -F <file>`; a `git push origin claude/foo:main`
refspec trick writing to `main` while matching the `claude/*` allow prefix) — closed by removing
`add`/`commit`/`push`/`gh pr create`/`gh pr comment` from `allow` entirely rather than continuing an
arms race against a permission-pattern language whose exact matching semantics this document could
not establish with certainty even after two review rounds; (8) `run_log.py`/
`validate_loop_lifecycle.py`'s allow patterns used a repo-root-relative path that doesn't match the
scripts' real location (`skills/loop-task-implementer/scripts/`), which would have made the two most
frequent operations prompt on every use — fixed; (9) `make test-*` matched no real target (only
`lint-*` targets exist) — removed; (10) no documented escape hatch for a legitimate-but-denied
command, and no concrete acceptance test for the Orchestrator-level "select a different task"
behavior beyond the lease primitive itself — both closed below.

## Components

| Component | Responsibility | Boundary / owns | Notes |
|-----------|-----------------|------------------|-------|
| `.claude/settings.json` (new) | Declares which Bash command patterns Claude Code may run without a per-use prompt on this repo, and which are explicitly denied regardless of any matching allow rule | Static config, no code | Curated by hand against a named list (below), not auto-generated |
| `skills/loop-task-implementer/reference/enforcement-layer.md` (new) | States the enforced-vs-instruction-level distinction plainly: what `.claude/settings.json` actually constrains (one local Claude Code session's own Bash calls) and what it does *not* (nothing at the git-server, CI, or cross-host level; a Builder/Reviewer running under a different host/agent gets none of it) | Doc only | Answers the architecture review's Architecture-decision requirement; linked from `SKILL.md` |
| `scripts/task_lease.py` (new) | Non-blocking, flock-based mutual exclusion over a deterministic `(repo, base_branch, task_id)` identity — answers "is anyone already working this task on this machine" | Owns lease acquire/release and the deterministic identity derivation; never touches `run_id` or `plan_execution_state` | Sibling in style to `scripts/plan_state_store.py` (directory/permission conventions) but a materially different acquisition model — see Consistency |
| `orchestrator.md` edit (existing file, two edits) | (a) Acquire a task lease before dispatch, release on terminal state; (b) correct the A5 CAS-rejection-retry text to distinguish "retry my own claim" from "task already claimed, select a different one" | Doc-only, additive to existing sections | Both edits sit in/near the existing §2 Task selection and the A5 addendum paragraph |

## APIs

| Endpoint / method | Contract | Consumer(s) | Notes |
|--------------------|----------|-------------|-------|
| `task_lease.derive_lease_id(repo: str, base_branch: str, task_id: str) -> str` | `"lease-" + SHA256(f"{repo}\|{base_branch}\|{task_id}")[:16]` — **no timestamp**, so the same three inputs always produce the same id (deliberately the opposite of `run_id`'s per-attempt distinctness) | Orchestrator, once per task, before dispatch | Mirrors `derive_run_id`'s hashing shape (`run_log.py`) but with a fixed, non-time-seeded input set — the one deliberate structural difference from `run_id` that makes this a lease identity instead of an audit identity |
| `task_lease.try_acquire(lease_dir: Path, lease_id: str) -> LeaseHandle \| None` | Opens (creating if absent) `<lease_dir>/<lease_id>.lock`, attempts `fcntl.flock(fd, LOCK_EX \| LOCK_NB)` **once**, non-blocking. Returns a `LeaseHandle` (wrapping the open fd) on success; returns `None` immediately on failure — never waits, never retries internally. A failure to even *create/open* the lease file or directory (disk full, permission error, filesystem unavailable) is a **different** outcome from a contended lease and must not be conflated with it — see Failure strategy's new "lease infrastructure failure" row: `try_acquire` **raises `TaskLeaseError`** for that case, it never returns `None` for it. Directory resolution/creation mirrors `plan_state_store.resolve_state_dir`/`_private_dir` exactly (outside any git repo, `0700`/`0600`, symlink/ownership refusal) — default `~/.software-builder/task-leases/` | Orchestrator, before Builder dispatch | Named `try_acquire`, not `acquire` (revision 1's name), because plain `acquire` reads as blocking by convention in this codebase — `install_engine.py`'s `held_lock()` and `run_log.py`'s `_locked` both block-with-timeout; `plan_state_store.cas_advance` blocks up to `LOCK_TIMEOUT_SECONDS`. This primitive is the only non-blocking one of the four, and the name should say so on sight |
| `LeaseHandle.release() -> None` | Closes the held fd (OS releases the flock the instant it closes) | Orchestrator, on task terminal state (`COMPLETE`/`ESCALATED`/`BLOCKED`) or naturally via the process exiting | Idempotent — closing an already-closed fd is a no-op, matching `plan_state_store`'s own release pattern |
| `task_lease.LeaseHandle` (context manager) | Usable as `with task_lease.try_acquire(...) as handle:` for the common case where the lease should be held exactly as long as one Python `with` block's scope; `try_acquire` returning `None` is not itself a context manager, so the caller's own `if handle is None:` branch handles the "already leased" path explicitly | Orchestrator | Keeps the "lease not acquired" case a plain, checkable value rather than an exception — this is an expected, common outcome (a peer working the same task), not an error. Infrastructure failure (see above) stays an exception, so the two cases can never be silently confused by a caller that only checks `is None` |

## Data model

| Entity | Key fields | Relationships | Owner |
|--------|-----------|-----------------|-------|
| `<lease_id>.lock` file | Empty; existence + `flock` state only, identical shape to `plan_state_store`'s `.lock` siblings and `idempotency_store.py`'s `.locks/*.lock` | One per `(repo, base_branch, task_id)` triple, independent of `plan_id`/`run_id` | `task_lease.py` |
| `.claude/settings.json` | `permissions.allow: list[str]`, `permissions.deny: list[str]` (Claude Code's own schema — this design only populates the content, not the schema) | N/A | Repo owner; already matched by `CODEOWNERS`'s existing `*  @luckyrjain` catch-all — **but this is honestly weaker protection than revision 1 implied**. `CODEOWNERS` in this repo is `require_code_owner_review: false` (non-enforcing, an established fact from this session's own earlier ruleset research) — it does not block a merge, and more importantly it provides **zero protection against the actual named threat**: a repo owner locally checking out an *unmerged*, attacker-modified PR branch and opening Claude Code on it never goes through any merge/review gate at all, CODEOWNERS or otherwise. This design does not claim CODEOWNERS mitigates that threat; it only records that the file is nominally owned, for visibility, and names the real mitigation as operator discipline (see Failure strategy) — not a technical control |

### `.claude/settings.json` content (Condition 1 — precise allow, explicit deny)

```json
{
  "permissions": {
    "allow": [
      "Bash(git status:*)",
      "Bash(git diff:*)",
      "Bash(git log:*)",
      "Bash(git fetch origin:*)",
      "Bash(git checkout -b claude/*)",
      "Bash(git checkout main)",
      "Bash(gh pr view:*)",
      "Bash(gh pr checks:*)",
      "Bash(gh pr diff:*)",
      "Bash(python3 skills/loop-task-implementer/scripts/run_log.py:*)",
      "Bash(python3 skills/loop-task-implementer/scripts/validate_loop_lifecycle.py:*)",
      "Bash(python3 -m pytest:*)",
      "Bash(make lint-*)"
    ],
    "deny": [
      "Bash(git reset --hard:*)",
      "Bash(git clean -f:*)",
      "Bash(git branch -D:*)",
      "Bash(git merge:*)",
      "Bash(rm -rf:*)"
    ]
  }
}
```

**This block is narrower than both revision 1 and revision 2's intermediate draft**, after two rounds
of adversarial review. Revision 1's `git add:*`/`git commit -m:*`/`git push origin claude/*` composed
into a working, zero-prompt secret-exfiltration chain. Revision 2's fix (exact-string `git add .`/
`git commit -m` plus a longer deny list) closed that specific chain but round 2 review found it
reopened by two siblings the deny list didn't cover: `gh pr comment -F <file>` (posts an arbitrary
local file's contents to a public PR comment in one command — a strictly simpler exfiltration path
than the one just closed) and `git push origin claude/foo:main` (a refspec that pushes the *local*
`claude/foo` branch to the *remote* `main` ref — matches the `git push origin claude/*` allow prefix
literally while actually writing to `main`, and a bare trailing `--force` on any push is a separate,
analogous flag-placement bypass the deny list's left-anchored patterns structurally cannot catch,
since they only match commands that *start* with the dangerous flag).

**Revision 3's resolution, given two rounds of adversarial review converging on the same underlying
problem**: a prefix/deny pattern list cannot be made provably safe against a variable-content
command (a commit message, a branch name, a comment body) without either (a) confirmed, precise
knowledge of exactly how Claude Code's matcher tokenizes and evaluates a compound or flag-appended
invocation — which two rounds of review could not establish with certainty from this repository
alone — or (b) simply not allow-listing the highest-value targets for this attack class. This
revision takes (b): **`git add`, `git commit`, `git push`, and `gh pr create`/`gh pr comment` are
removed from `allow` entirely** and fall through to the host's default per-use prompt. This is a real
trade-off (less friction reduction than originally scoped) made deliberately, because after two
rounds of dedicated adversarial review still surfacing new bypasses for these specific commands, the
responsible conclusion is that this permission-pattern language cannot be trusted to gate them safely
without the empirical verification Phase 1 already required — and a template that ships unsafe
defaults is worse than a template that ships a smaller, verifiably-safe allow list. The remaining
allow entries are either read-only (`status`/`diff`/`log`/`fetch`/`gh pr view`/`gh pr checks`/
`gh pr diff`) or exact, argument-free, non-destructive fixed commands (`checkout -b claude/*` only
creates a new branch, never overwrites one; `checkout main` only switches context) — none of them
have a "safe verb + dangerous flag" shape for an attacker to exploit, because none of them accept
free-form trailing content at all. If Phase 1's empirical verification later demonstrates the host's
matcher is precise enough (e.g. genuinely argument-aware, not naive prefix) to safely re-admit
`commit`/`push`/`add` with tight patterns, that is a follow-up revision, made with evidence in hand
— not something this revision assumes it can do safely today.

**Deny-precedence claim**: this is the documented, expected behavior of Claude Code's permission
system as of this design's authoring; this document has not executed a test against the live host to
confirm it. Rollout Phase 1 requires that confirmation regardless of the narrowed allow list above,
since `deny` still matters for the read-only/fixed commands that remain allow-listed.

## State machines

| Entity | States | Transitions | Notes |
|--------|--------|-------------|-------|
| Task lease | `unheld → held (try_acquire() succeeds)` \| `unheld → acquire_failed (try_acquire() returns None — a peer holds it)` \| `unheld → infrastructure_error (try_acquire() raises TaskLeaseError — disk/permission/filesystem failure, not contention)` \| `held → unheld (release(), or process exit closes the fd)` | No other states — this is deliberately the simplest possible state machine; there is no "stale," no "expired," no "reclaimed" state, matching this repo's `held_lock()`/`run_log.py` philosophy exactly | `acquire_failed` is not an error state, it's the *expected* signal to select a different task; `infrastructure_error` IS an error state and must escalate (see Failure strategy) — the two must never be conflated by a caller |
| A5's CAS-rejection retry (corrected, concrete) | `claim_attempted → claim_succeeded (cas_advance returns cleanly)` \| `claim_attempted → claim_rejected (PlanStateCasError) → call plan_state_store.read_state(state_dir, plan_id) fresh → look up the SAME task_id in the freshly-read task_statuses map: if its value is still "PENDING" (nobody else claimed it — the rejection was caused by an unrelated generation bump, e.g. a different task's own advance), re-derive expected_generation from the fresh read and retry the SAME claim, exactly once → if its value is now "IN_PROGRESS" (the specific, concrete signal that a peer's claim landed first — this is the correct `plan_execution_state.task_statuses` vocabulary value, per `implementation_plan.py`'s `OFFICIAL_TASK_STATUS_MAP`/`TASK_STATUSES`; **not** "BUILDING", which belongs to a different, legacy field — `state-schema.yaml`'s standalone `task.status` — and must not be checked here), select a DIFFERENT task — never retry this one → if a second consecutive rejection occurs on the retry, STOP retrying and escalate per orchestrator.md §19 (do not loop indefinitely on generation churn)` | The corrected text (see Rollout) replaces the current single branch ("retry once") with this explicit, field-value-grounded fork. **Revision 3 correction**: revision 2 wrote "BUILDING"/"IN_PROGRESS" as if interchangeable — round-2 adversarial review confirmed only `IN_PROGRESS` is a legal `task_statuses` value; `BUILDING` is legacy `task.status` vocabulary (the field the *separate* Consistency-section resume rule below correctly checks). The two fields/vocabularies must not be conflated, even though this fix happened to be harmless in practice (the `IN_PROGRESS` branch is the one that actually fires either way) | This is the fix for the identified A5 gap — a genuine behavior change to already-shipped text, not new functionality. The second-rejection-escalates rule closes the SRE-identified gap where an undefined outcome on a second rejection could let two Orchestrators churn indefinitely |

## Consistency

| Boundary | Model | Why |
|----------|-------|-----|
| Task lease acquisition | Strong *on the host where the Orchestrator's process genuinely spans its dispatched work's lifetime* (verified for Claude Code; not established for every host — see Condition 2's platform-lifetime analysis below, which this row is not independent of), single-machine, real OS `flock`, non-blocking | Matches the architecture review's chosen alternative (fail-fast over queue-and-wait); stated here without qualification would overclaim relative to Condition 2's own honestly-scoped conclusion |
| Task lease vs. `plan_state_store`'s CAS | **Two independent mechanisms, not layered** — the lease answers "is anyone actively working this task right now" (process-lifetime scoped); the CAS store answers "what is the durable, authoritative status of this task" (survives across process restarts). A task can legitimately have `task_statuses[task_id] == "BUILDING"` in the durable store from a now-dead process (crash) while no lease is currently held. **Concrete resolution rule (closes the SRE-identified gap against `orchestrator.md §2`'s existing unconditional "never dispatch a Builder for a task already BUILDING")**: that existing rule is amended, not overridden — `task_status == "BUILDING"` still blocks dispatch *unless* `task_lease.try_acquire` for that same task's `lease_id` **succeeds**. A successful lease acquisition on a `BUILDING`-status task is the concrete, checkable signal that the prior claimant is actually gone (its lock would still be held if it were alive), not a license to ignore the durable status — the Orchestrator must still independently re-verify SCM state (existing §5 checks: does a branch/PR already exist, what's its actual state) before treating the task as safe to restart, exactly as it already does for any other resume scenario | Deliberately not unified into one mechanism — a durable CAS store and a process-lifetime lease have genuinely different consistency models (survive-restart vs. tied-to-a-live-process) and conflating them would either make the lease outlive its holder's death (bad) or make the durable record disappear with the process (also bad). The resolution rule above is what makes the two-mechanism split actually usable rather than merely "the Orchestrator must figure it out" |
| Cross-machine | **None — explicitly out of scope** (Condition 3) | flock is local-filesystem-only; two different machines each holding a clone would each acquire their own independent lock and never see each other. Git's own remote fast-forward semantics (the pre-existing `orchestrator.md §2` disclaimer) remain the only cross-machine safety net, and it operates at a different layer (branch/ref writes, not task-start decisions) |

## Retries & idempotency

| Operation | Idempotent? | Retry / backoff strategy |
|-----------|-------------|----------------------------|
| `task_lease.try_acquire` | Yes — calling it again after a failed attempt is always safe (no side effect on failure beyond the directory/lock-file existing, which is itself idempotent to create) | No backoff/retry logic built into the primitive itself — the *caller* (Orchestrator) decides whether to try a different task, wait, or escalate; the primitive stays a single, cheap, one-shot check |
| `LeaseHandle.release` | Yes — closing an already-closed fd is a no-op | N/A |
| A5's corrected CAS-rejection handling | Yes in effect — re-deriving `expected_generation` from a fresh read before retrying means a repeated rejection just produces another fresh read, never a stuck loop (bounded by the existing "retry once" cap, now explicitly only exercised on the `status_still_available` branch) | One retry, exactly as today's text already caps it — the fix narrows *when* that one retry is appropriate, not the cap itself |

## Capacity

| Dimension | Estimate | Basis |
|-----------|----------|-------|
| Concurrent lease files | Single-digit, bounded by concurrent in-flight tasks on a solo-maintainer repo | Same reasoning as every other local-state component this session built |
| Permission-check overhead | Negligible — pattern matching against a fixed, small list, evaluated by the host per Bash invocation | Not a component this design controls the performance of |

## Failure strategy

### Condition 2 — platform-lifetime analysis

The architecture review's Condition 2 asked whether dispatched Builder/Reviewer work can outlive the
Orchestrator process holding the lease fd. Revision 1 asserted this was "resolved" without argument;
adversarial review correctly rejected that as unsubstantiated. The actual analysis, done properly:

- **On Claude Code specifically** (this session's own host, per `skills/loop-task-implementer/reference/platform-adapters.md`'s
  Claude Code section): the documented isolation primitives are "subagents," "fresh sessions," and
  "worktrees" — dispatch modes that run *within* an Orchestrator session's own lifetime, not a
  detached background daemon. A background-tracked Agent-tool dispatch delivers its completion
  notification back into the same session later; nothing in this platform's own documentation
  describes work surviving the full termination of the dispatching session.
- **This is not a universal guarantee across every host this skill supports.** `platform-adapters.md`'s
  own **Cursor** section (a different platform, not Claude Code) explicitly names "background agents"
  as an available dispatch mode — language that, on its face, suggests detached execution is at least
  possible on some host this skill is designed to run under. This design does not have enough
  information to rule that out for Cursor, and does not attempt to.
- **Conclusion, honestly scoped**: holding the lease fd open in the Orchestrator's own long-lived
  process is a sound design **for Claude Code**, based on that host's own documented isolation model.
  For any host where dispatched work can genuinely outlive the dispatcher (Cursor's background agents
  being the one named candidate in this repo's own docs), the lease's guarantee weakens to
  best-effort: it correctly prevents double-dispatch *from the same Orchestrator process*, but cannot
  prevent a detached background task from continuing after its dispatcher exits and a *new*
  Orchestrator process later reacquiring the now-free lease. This is named as an accepted,
  host-dependent residual risk, not silently assumed away — git's own remote fast-forward semantics
  (the pre-existing `orchestrator.md §2` disclaimer) remain the backstop for the downstream
  branch-write collision even in that scenario, the same way they already are for the cross-machine
  case (Condition 3).

### Failure mode table

| Failure mode | Degradation / mitigation |
|--------------|-----------------------------|
| Lease holder process crashes | OS releases the flock the instant the fd closes — no stale-lease reclaim logic exists or is needed, matching `held_lock()`/`run_log.py`/`plan_state_store.py`'s identical, repeatedly-reaffirmed philosophy (ADR 0007) |
| Lease holder process hangs (alive, stuck) | The lease correctly stays held — this is the intended mutual-exclusion behavior, not a bug. A human must notice and terminate the hung process; the OS then releases the lock automatically |
| Two Orchestrator processes on the *same* machine race for the same task | `try_acquire()` succeeds for exactly one; the other gets `None` immediately and must select a different task or escalate — no double dispatch |
| Two Orchestrator processes on *different* machines race for the same task | **Not protected against — explicit, named scope limit** (Condition 3). Mitigated only indirectly, by git's own remote fast-forward semantics catching the downstream branch-write collision if both proceed anyway |
| Dispatched work outlives the Orchestrator process on a host where that's possible (Condition 2) | **Not protected against on such a host — explicit, named scope limit**, see analysis above. Same git-remote backstop as the cross-machine case |
| Lease-directory/lock-file creation fails for an infrastructure reason (disk full, permission error, filesystem unavailable) | `try_acquire` **raises `TaskLeaseError`**, distinct from returning `None` — must escalate, must never be silently treated as "task already claimed" (that would incorrectly stop all progress on every task, masking a systemic failure as normal contention) |
| Same process calls `try_acquire` twice for the same `lease_id` | Fails fast on the second call (a fresh fd's non-blocking `flock` contends with the process's own already-held lock — `flock` binds to the open-file-description, not the process, confirmed against `plan_state_store`'s identical per-call-fresh-fd pattern) — no self-deadlock, no false success |
| A CAS-rejection retry (corrected logic) hits a second consecutive rejection | Escalate immediately, per the concrete state-machine fork above — never a third attempt, never an indefinite churn |
| An `allow`-listed command's prefix is later extended with a dangerous flag not covered by an existing `deny` entry | Falls through to the host's default behavior (a per-use prompt) for patterns that still use a wildcard; for the two highest-risk steps (`add`, `commit -m`) this design removes the wildcard entirely rather than relying on deny coverage alone (see `.claude/settings.json` rationale above) |
| A5's CAS-rejection retry, uncorrected | (Pre-fix state, being closed by this design) a literal retry of an identical claim could succeed and produce double Builder dispatch for the same task — closed by the state-machine fix above |

## Observability

| Signal | What's measured |
|--------|-------------------|
| `try_acquire()` returning `None` | The common case (contention → pick a different task → finish normally) must leave a durable trace, not just a possible mention in an escalation report that only fires on a terminal stop (the escalation path alone was confirmed, on review, to leave zero record for the non-escalating common case). **Fix**: the Orchestrator records a `lease_denied` event via `run_log.py`'s existing `append` mechanism (a new entry in its closed `EVENTS` set, alongside `task_selected`/`builder_dispatched`/etc. — implementation adds `lease_denied` to that set) with `data: {task_id, lease_id}` — a lightweight, always-written record, not contingent on the run ending in escalation |
| `TaskLeaseError` (infrastructure failure) | Same `orchestrator.md §19` `supporting_evidence` escalation path A5's own errors already use — this case DOES escalate, unlike a plain lease denial |
| `.claude/settings.json` drift from actual command usage | No automated signal — noted in Rollout as a manual-revisit item, matching the architecture review's own Operability note |

## Rollout plan

| Phase | Scope | Notes |
|-------|-------|-------|
| 0 | Implement `scripts/task_lease.py` with unit tests: single-process acquire/release, double-acquire-in-same-process-fails-immediately, an infrastructure-failure case (`TaskLeaseError` raised, not `None`, e.g. by pointing `lease_dir` at an unwritable path), and a genuine cross-process test using `scripts/tests/install_lock_test_helpers.py`'s `spawn_lock_holder` pattern (a real subprocess holding the real flock) asserting a second, real `try_acquire()` attempt from the test process returns `None` immediately. **Honestly scoped**: this proves the *primitive* is correct — it does not, by itself, prove the ticket's full "no double execution" acceptance criterion, which depends on the Orchestrator's own prose-level "select a different task on denial" behavior (see Phase 2) | New file only, no wiring yet — zero behavior change until Phase 1 |
| 1 | Write `.claude/settings.json` (the content above) and `skills/loop-task-implementer/reference/enforcement-layer.md`; link the new doc from `SKILL.md`. **New required step**: before treating the template as load-bearing, empirically verify against the real host — construct the exact exfiltration chain adversarial review found (`git add -f .env`, `git commit -m wip --no-verify`, `git push origin claude/exfil-1`) and confirm each step is denied or falls through to a prompt, not silently allowed; also confirm empirically that an explicit `deny` entry actually overrides a broader `allow` match on this host, since this document only asserts that as documented behavior, not as something it tested | Config + doc, plus the one verification step this revision adds as a hard requirement, not an assumption |
| 2 | Edit `orchestrator.md`: (a) add the lease acquire/release call-out near where Builder dispatch happens (Core responsibilities items 2→4, mirroring where A5's own addendum sits), including the amended §2 "BUILDING-status + lease-available" resume rule from Consistency above; (b) correct the CAS-rejection-retry text to the concrete, field-grounded fork in the State machines table above; (c) add `lease_denied` to `run_log.py`'s `EVENTS` set for the Observability fix above. **Concrete acceptance test for this phase** (closing the round-2 finding that "exercises this" alone isn't a checkable criterion): with two real, separate `loop-task-implementer` invocations targeting the same `implementation_plan`/`task_id` (mirroring `scripts/tests/test_install_concurrency.py`'s real-subprocess pattern, not a mock), assert the second invocation's own run log contains a `lease_denied` event for that `task_id` and that it proceeds to select a *different* task (or, if none remains, escalates) rather than dispatching a second Builder for the same one — this is the actual, end-to-end "no double execution" property, distinct from and in addition to Phase 0's primitive-level unit test | The one edit to already-shipped A5 text — this is a real, deliberate correction, not new functionality layered on top |
| 3 | Write `skills/loop-task-implementer/reference/enforcement-layer.md` (component already named above) with an explicit paragraph on the no-override tradeoff: a `deny`-matched command is refused outright by the host, with no in-session escape hatch — deliberately, since the denied set is narrow and named specifically as "operations that must never be autonomous" (round-1/round-2 review both confirmed the actual deny list stayed narrow: `reset --hard`, `clean -f`, `branch -D`, `merge`, `rm -rf`). A human who legitimately needs one of these runs it themselves outside the agent, or edits `.claude/settings.json` directly — this is accepted friction, not a gap, and the doc should say so plainly rather than leave it implicit (round-2 finding: this repo's own F1 precedent — a mechanism too restrictive for actual solo-maintainer use gets removed — is exactly the failure mode a silent, undocumented "no escape hatch" invites; naming the tradeoff explicitly is the mitigation) | Doc-only, closes the round-2 "no interactive override" finding |

## Open questions

- Whether `.claude/settings.json`'s `allow` list needs periodic revisiting as `loop-task-implementer`'s actual command surface evolves (architecture review's Operability note) — no automated drift-detection designed here; left as a manual owner task.
- Exact wording/placement of the `enforcement-layer.md` doc's cross-reference from `SKILL.md` — an editorial detail, not architecturally significant.
- Whether Claude Code's actual permission matcher is a naive string-prefix check or an argument-aware tokenizer — this document deliberately does not claim to know, and Phase 1's empirical verification step is the intended way to close this for real rather than continuing to assert it either way.
