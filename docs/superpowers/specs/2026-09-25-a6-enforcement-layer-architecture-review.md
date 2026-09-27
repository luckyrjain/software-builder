# Architecture review — A6 permission template and run-identity lease

**Decision: Approved with conditions**

Sound overall: both components reuse this repo's own established patterns (flock-based, crash-safe-by-OS-release locking with no stale-reclaim logic; a curated rather than auto-generated permission template) rather than inventing new primitives. This is the first tool-level (host-enforced) mechanism this repo ships, which raises the bar on precision — four gaps need closing before implementation, none of them a redesign.

## Architecture decision

Two components close gap-backlog ticket A6. (1) A checked-in `.claude/settings.json` permission
template, curated against the specific commands `loop-task-implementer`'s Orchestrator/Builder
actually need (git commit/push, `gh pr` operations, `run_log.py`/`validate_loop_lifecycle.py`
invocations, test/lint commands) and the specific dangerous operations this repo's own standing
doctrine already names as needing explicit human authorization (force-push, `reset --hard`,
`rm -rf`, branch deletion, merge) — allow the former, deny the latter explicitly, leave everything
else at the host's default per-use prompt. Paired with a new doc section stating plainly that this
is the *first* tool-enforced gate in a repo where every other gate (A5's CAS store, ADR 0008's
write-authority policy, `allowed_actions` capability grants) is instruction-level — an LLM reading
prose, not something a host structurally blocks. (2) A new, minimal `scripts/task_lease.py`:
flock-based, non-blocking, keyed by a deterministic `SHA-256(repo, base_branch, task_id)` identity
deliberately distinct from `run_id` (which stays time-seeded for legitimate per-attempt audit-log
distinctness) — acquired before dispatch, released on terminal state or automatically by the OS on
process death, no stale-reclaim logic (matching `install_engine.py`'s `held_lock()`/`run_log.py`'s
own established philosophy). Also corrects an identified gap in A5's just-merged text: the
CAS-rejection retry instruction in `orchestrator.md` doesn't currently distinguish "retry my own
claim" from "someone else already has this task" — a literal retry could re-submit the identical
claim and produce double dispatch.

## Risks

| Risk | Section | Severity | Notes |
|------|---------|----------|-------|
| An `allow` rule pattern could inadvertently match a dangerous variant of an otherwise-safe command (e.g. a `git push` allow-pattern that isn't specific enough to exclude `git push --force`) | Security | Blocking | See Conditions §1 |
| Unclear whether the lease fd's holding process (the Orchestrator) actually spans the full lifetime of dispatched subagent work on this host platform, or could exit while background work continues | Failure modes | Blocking | See Conditions §2 |
| flock is single-machine only — the design doesn't state this limitation, and a reader could reasonably assume it protects against two different machines both working the same task | Scale limits | Conditional | See Conditions §3 |
| `.claude/settings.json` itself is an attractive tampering target (a modified copy checked out locally could silently grant permissions), and nothing in this design protects the file itself | Security | Conditional | See Conditions §4 — recommended, not mandatory, given F1's removal earlier today for being unsatisfiable by a solo maintainer; a heavier gate isn't being asked for again |

## Scale limits

| Dimension | Breaks down at | Evidence |
|-----------|-----------------|----------|
| Concurrent lease files | Not a realistic constraint — bounded by concurrent in-flight tasks on a solo-maintainer repo | Same reasoning as A5's own Scale limits section |
| Cross-machine coordination | **flock provides none** — two different machines each holding a local clone and independently running `loop-task-implementer` against the same task would each acquire their own OS-local lock and neither would see the other | Not stated in the design as submitted; must be named explicitly rather than silently assumed away (Condition 3) |

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| Lease holder process crashes | OS releases the flock the instant the fd closes, same guarantee every other lock in this repo already relies on | None needed — the next attempt acquires cleanly | No new gap; matches established pattern exactly |
| Lease holder process hangs (alive but stuck, not crashed) | The lease correctly stays held — this is the *intended* behavior, not a bug, since the whole point is mutual exclusion | A human must notice and kill the hung process; its fd closes, the OS releases the lock | Matches this repo's own ADR 0007 philosophy (no stale-reclaim logic, ever) — should be stated in Failure strategy as a deliberate, not accidental, property |
| The Orchestrator process exits (session ends) while a dispatched subagent's work is still logically "in flight" on this host platform | **Unknown — not verified against the actual target platform's process model** | Unknown | See Conditions §2 |
| Two Orchestrator processes on genuinely different machines race for the same task | Neither can see the other's lock | None — flock cannot provide this | Named as an accepted, explicit scope limit (Condition 3), not a defect to fix now |
| A5's CAS-rejection retry re-submits an identical claim | Currently: none — the text doesn't distinguish the two cases | Design's own fix (read the task's status after rejection, select a different task if already claimed) | This is the one genuine correctness gap A6 closes in existing (A5) text, not new-component risk |

## Security

| Concern | Trust boundary / data flow | Blast radius | Notes |
|---------|------------------------------|---------------|-------|
| Allow-rule precision | The permission template governs what one local Claude Code session may run *without a human prompt* — a rule that's too broad silently removes a human checkpoint for a genuinely dangerous operation | Whatever the over-broad rule actually allows (e.g. an unintended force-push) | See Conditions §1 |
| Deny-rule precedence | Must be verified that an explicit `deny` entry actually takes precedence over a broader `allow` entry in Claude Code's real settings-resolution order, not assumed | If deny doesn't win, the whole denylist is decorative | See Conditions §1 |
| Tampering with the settings file itself | A modified `.claude/settings.json` checked out locally (e.g. from an untrusted branch) changes what gets auto-approved for whoever opens Claude Code on that checkout | Bounded to the local session that opens the tampered checkout — not a remote/network risk | See Conditions §4 |

## Operability

| Concern | Owner | Operating cost | Notes |
|---------|-------|------------------|-------|
| Who runs/maintains this | Repo owner, solo maintainer, unchanged posture from every other component this session built | New file (`.claude/settings.json`) and one new small script; no new credential, no new service | Consistent with the rest of the repo |
| Keeping the allow-list current as `loop-task-implementer`'s actual command surface evolves | Repo owner | Manual — the template is curated, not auto-derived, so it can drift from reality over time | Worth a note in Rollout that this should be revisited periodically, not a blocking gap |

## Alternatives considered

| Alternative | Why not chosen | Notes |
|-------------|-------------------|-------|
| Auto-generate the permission template from this session's own transcripts (the repo's own `fewer-permission-prompts` skill does exactly this) | Usage-frequency-based generation optimizes for "what did we happen to run," not "what is safe to run without a human looking" — for a security-relevant allowlist, deliberate curation against a named dangerous-operations list is the safer default | A legitimate alternative for keeping the list current later, not for establishing the initial, safety-reviewed baseline |
| Extend `run_id` itself to be deterministic (drop the time seed) instead of introducing a separate `task_lease` identity | Would break `run_id`'s own legitimate purpose — distinct per-attempt audit trails, explicitly by design (`run-log.md`'s own stated rationale: "the UTC start time is a seed, so a task started again later is a new run") | Correct rejection — conflating audit-trail identity with mutual-exclusion identity would regress an already-working property |
| A distributed/cross-machine lock (e.g. a GitHub Issue or label used as a mutex) instead of local flock | Heavier machinery than this repo's actual scale (solo maintainer) clearly justifies today; git's own remote fast-forward semantics already provide *a* cross-machine safety net for the specific case of two processes racing to create the same branch, even without a true distributed lock | Correct rejection for now, but the resulting scope limit (Condition 3) must be stated, not silently absorbed |
| A blocking lease (wait for the holder to finish) instead of non-blocking fail-fast | The ticket's own acceptance criterion is "no double execution," not "queue and wait" — fail-fast lets the Orchestrator immediately select a different task or escalate, which is more useful behavior for an autonomous loop than blocking | Sound choice, consistent with the ticket's actual framing |

## Conditions

1. **Specify exact allow/deny patterns and verify deny-precedence before shipping.** Every `allow`
   entry must be precise enough that it cannot also match a named-dangerous variant (`git push` vs
   `git push --force`, etc.) — verify this isn't just asserted but actually tested against Claude
   Code's real permission-pattern matching, and confirm empirically (not assumed) that an explicit
   `deny` entry wins over a broader `allow` when both could match the same invocation.
2. **Verify the Orchestrator-process/subagent-lifetime relationship on the actual target platform
   before finalizing where the lease fd is held.** If dispatched work can genuinely outlive the
   Orchestrator's own process on this host, the lease design needs to account for that explicitly
   (e.g. document it as an accepted gap, or hold the lease somewhere that survives it) rather than
   silently assume same-process-lifetime throughout.
3. **State the single-machine-only scope limit explicitly** in the design's Failure strategy/Scale
   limits sections — flock provides no cross-machine protection, and a future reader should not have
   to rediscover this by reasoning from first principles.
4. **Recommended, not required**: consider adding `.claude/settings.json` to `CODEOWNERS` (an
   already-existing, lightweight mechanism — no new gate, no revival of the mechanism removed
   earlier today) so a change to it is at least visible as owner-attributable, given it's the one
   file in this design capable of silently widening what runs without a prompt.

None of these four block starting a `system-design` pass — they're precise, implementable
requirements for that pass to satisfy, not open architectural questions.
