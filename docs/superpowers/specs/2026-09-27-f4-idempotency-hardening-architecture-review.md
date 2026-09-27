# Architecture review — F4: pr-gatekeeper idempotency store hardening

**Decision: Approved with conditions**

Sound direction overall — the ticket correctly identifies `skills/pr-gatekeeper/scripts/idempotency_store.py`
as a weaker concurrency path than `install_engine.py`'s `held_lock()`/A5's `plan_state_store.py`, and reusing
that established flock/signal/fsync philosophy rather than inventing something new is the right call. Five
conditions need closing in `system-design` before implementation, two of them because the proposal's own
stated assumptions about existing repo precedent don't hold up against a direct read of the code.

## Architecture decision

Harden `idempotency_store.py` — a documented **reference implementation for external integrators**
(`idempotency_store.py:2-5`; `reference/idempotency.md:28-31`), not code any of software-builder's own
skills invoke — against five concrete gaps: an unbounded `flock` wait held across the whole child
subprocess, no signal handling (so a kill can orphan a still-running child), an overloaded exit code
(`1` means both "duplicate, skipped" and "child failed with that code"), a missing `fsync` before the
atomic replace, and a `last_processed_head_sha` check with no ordering signal, so an out-of-order webhook
delivery can silently revert a newer mark to an older one. The proposed fix reuses this repo's own
established primitives (`install_engine.py`'s `held_lock()`, `_sigterm_as_system_exit()`,
`_defer_interrupts()`) rather than inventing a new locking or signal-handling model — consistent with how
A5 and A6 both extended existing repo conventions instead of introducing parallel ones.

## Risks

| Risk | Section | Severity | Notes |
|------|---------|----------|-------|
| Signal-forwarding to a live child `subprocess` has no existing precedent anywhere in this repo (`held_lock()`'s protected region is in-process file I/O, not a child process) — treating it as a drop-in reuse of `_sigterm_as_system_exit()`/`_defer_interrupts()` understates the work | Failure modes | Blocking | See Conditions §2 |
| The design's stated fsync precedent (`atomic_write.py`) doesn't exist — direct read of `scripts/atomic_write.py` shows no `fsync` call anywhere in it; the real, correct precedent (`_fsync`/`_fsync_dir`, with macOS `F_FULLFSYNC` handling) lives in `run_log.py` instead | Failure modes | Blocking | See Conditions §3 |
| Reassigning or reusing exit code `1` for a new outcome would silently break any external integrator who already copied this reference file and branches on `returncode == 1` meaning "duplicate, skipped" (`test_run_if_new_skips_duplicate` encodes this exact contract today) | Security / Operability | Conditional | See Conditions §1 |
| The reject-older-head fix requires a new caller-supplied ordering input — a CLI/argument-contract change to a file explicitly documented as "for webhook handlers" to build integrations against, i.e. a public-ish contract this repo cannot fully see the installed base of | Operability | Conditional | See Conditions §4 |

## Scale limits

| Dimension | Breaks down at | Evidence |
|-----------|-----------------|----------|
| Concurrent MR locks | Not a realistic constraint — one lock file per `(project, merge_request_iid)`, bounded by concurrent in-flight MRs for whatever integrator deploys this | Same reasoning as A5/A6's own Scale limits sections |
| Cross-machine coordination | `flock` provides none, same accepted limit as A6's `task_lease.py` — not newly introduced by this change, but worth restating in `reference/idempotency.md` since this file is read by integrators who may not have read A6's precedent | `install_engine.py:336-339`'s NFS caveat, same class of limitation |

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| Gatekeeper subprocess hangs, lock held forever (current bug) | None today — caller just blocks indefinitely | Fix: bounded `wait_timeout` + a distinct exit code naming the lock holder's pid, matching `held_lock()`'s `LockTimeoutError` | Detection/recovery both currently absent; fix closes this cleanly |
| Wrapper process receives SIGTERM while the child is running (current bug) | None today — child can be orphaned, wrapper exits believing it's done | Fix needs a **new**, not reused, pattern: forward the signal to the live child via `subprocess.Popen` + `proc.send_signal()`, wait for the child's own exit, skip `mark_processed` (the run didn't complete cleanly), *then* exit `130` | Not equivalent to `_sigterm_as_system_exit()`, which only converts a signal into an in-process exception — nothing there forwards to a child. See Conditions §2 |
| Process crash (any cause) between `save_record`'s tempfile write and `os.replace()` | `os.replace()` remains atomic at the directory-entry level regardless of fsync — no torn/partial file is possible either way | None needed — the prior record (or no record) survives untouched | Correcting the ticket's framing, not softening it: this specific failure mode is **already safe** without the fsync fix |
| **Machine crash / power loss** (not an ordinary process kill) between `os.replace()` returning and the OS durably persisting that directory-entry update | Undetectable from the file alone — the record can silently revert to the previous value | Fix: `fsync` the temp file *and* the containing directory before/after replace, mirroring `run_log.py:875-923`'s `_fsync`/`_fsync_dir` (including its `F_FULLFSYNC` handling — a bare `os.fsync()` on macOS only reaches the drive's write cache) | This is the actual, narrower risk the ticket's "fsync" bullet closes — worth stating precisely rather than as generic "crash safety," since it reintroduces exactly the duplicate-processing hazard this file exists to prevent, only in the power-loss case |
| Out-of-order webhook delivery: an older `head_sha` arrives and is processed after a newer one was already marked | None today — `should_process` is a bare inequality check with no ordering signal | Needs a caller-supplied ordering value (sequence number or timestamp) to compare against, or an explicit documented limitation if no such value is available | See Conditions §4 — GitHub/GitLab webhook delivery is explicitly documented as at-least-once, not ordered, so this cannot be silently assumed away |

## Security

| Concern | Trust boundary / data flow | Blast radius | Notes |
|---------|------------------------------|---------------|-------|
| `--project`/`--merge-request-iid`/`--head-sha` are caller-supplied (ultimately webhook-payload-derived) values; `_safe_slug` already sanitizes `project` for path-safety (confirmed by existing tests: `test_safe_slug_rejects_path_traversal`, `test_store_path_stays_within_root_for_traversal_project`) | Webhook payload → CLI argv → filesystem path | Bounded — existing sanitization already covers this, no regression proposed here | Unchanged by this ticket; noted for completeness since the new ordering field (Condition 4) would sit in the same trust boundary and needs the same treatment, not a new unguarded path |
| A new caller-supplied ordering value (if Condition 4 resolves toward a new field) is itself untrusted input and needs type/bounds validation before being persisted or compared, same as every other CLI argument here | Webhook payload → new CLI argument → stored record | Same class as the existing `--head-sha`/`--project` handling — no new class of exposure, but a real gap if skipped | Must be explicit in system-design's field spec, not left implicit |
| Exit-code/contract changes are not a security boundary, but an unannounced breaking change to a "reference implementation for integrators" degrades an external caller's own security posture silently (e.g. a caller newly misreading `returncode == 1` as "duplicate" when it's actually "child process failed") | External integrator's own webhook handler | Bounded to whichever integrator's code branches on the old contract | See Conditions §1 |

## Operability

| Concern | Owner | Operating cost | Notes |
|---------|-------|------------------|-------|
| Who runs/maintains this file | This repo's owner maintains the reference implementation; each **external integrator** who copies it owns its production operation — explicitly stated in the file's own docstring (`idempotency_store.py:2-5`) and `reference/idempotency.md:28-31` | No new service, no new credential; same posture as today | Not a gap — the artifact's nature as a reference/documentation file, not an operated service, is already named by the code itself |
| Keeping `reference/idempotency.md`'s action-behavior table and recommended-caller-pattern section in sync with any CLI contract change | Repo owner | Manual — same "curated, can drift" cost A6's architecture review named for `.claude/settings.json` | Worth a condition, not a blocker: the doc update is part of `system-design`'s own scope, not a follow-up |

## Alternatives considered

| Alternative | Why not chosen | Notes |
|-------------|-------------------|-------|
| Leave the reference implementation as-is, since it's explicitly documented as "not invoked by the skill itself" and lower blast radius than A5/A6's core-executor changes | The ticket's own named gaps are real and concrete (confirmed by direct read, not assumed); leaving a documented reference implementation with a known hang/orphan/silent-reorder bug is a worse outcome for whichever integrator trusts it | Rejected — lower blast radius argues for lower urgency, not for skipping the fix |
| Replace file-lock + JSON with a different technology (SQLite WAL mode, a DB advisory lock) | Disproportionate for a solo-maintainer reference script; would also break the "matches every other locking primitive in this repo" consistency this repo has repeatedly chosen (A5, A6) | Correct rejection, same reasoning as A6's rejection of a distributed lock |
| Reassign/expand exit codes directly (e.g. give "duplicate" a new code, freeing `1` for child-passthrough) | Breaks the *existing* contract (`1` == duplicate) for whoever has already deployed this reference file — an integrator cannot be assumed to be watching this repo for silent CLI-contract changes | Should be weighed in system-design against the additive alternative below, not defaulted to |
| **Additive signaling**: keep existing exit codes as-is for back-compat, reserve genuinely *new* codes only for the genuinely *new* failure modes this ticket introduces (lock-timeout, signal-forwarded-teardown), and consider an optional `--json-output` line (`{"outcome": "duplicate"\|"ran"\|"lock_timeout"\|"child_failed"\|"interrupted"}`) for integrators who want to disambiguate a child's own exit-code collision with `1` without a breaking change | Not rejected — recommended as the leading candidate for Condition 1, but left for system-design to decide and justify, not mandated here | Reconciles the ticket's "distinct exit codes" ask with the backward-compatibility risk this review surfaces |
| Silently assume webhook delivery order is reliable and skip the reject-older-head fix | Both GitHub and GitLab explicitly document at-least-once, non-ordered webhook delivery — assuming otherwise would be an unstated, false assumption baked into a reference implementation | Correctly rejected by the ticket's own framing; system-design still owes a concrete mechanism or an explicit documented limitation (Condition 4) |

## Conditions

1. **Do not repurpose exit code `1`.** It is an existing, externally-observable contract
   (`test_run_if_new_skips_duplicate` encodes it; any integrator who already deployed this reference file
   may depend on it). Reserve new codes only for the genuinely new failure modes this ticket adds
   (lock-timeout, signal-forwarded-teardown). If finer disambiguation of a child's own exit code colliding
   with a reserved value is needed, prefer an additive mechanism (see Alternatives) over reassignment.
2. **Design a dedicated signal-forwarding path for `run_if_new`'s child subprocess** — this is not a
   straight reuse of `_sigterm_as_system_exit()`/`_defer_interrupts()`, which only protect in-process
   cleanup. It needs `subprocess.Popen` plus a handler that forwards the signal to the live child, waits
   for its actual exit, skips `mark_processed` for that run, and only then converts to `SystemExit(130)`.
   Pressure-test this with a real subprocess (this repo's own `spawn_lock_holder`-style harness), not
   asserted from reading the code.
3. **Fsync via `run_log.py`'s `_fsync`/`_fsync_dir`, not `atomic_write.py`.** Direct read confirms
   `atomic_write.py` has no fsync call today — there is no existing convention there to match. `run_log.py`
   is the real precedent, including its macOS `F_FULLFSYNC` handling that a bare `os.fsync()` would miss.
4. **Explicitly decide and document the reject-older-head mechanism before implementation**: a new
   caller-supplied ordering field (with its own validation, per the Security section above) versus an
   explicit documented known-limitation. Either way, treat this as a **versioned, disclosed change** to a
   file documented as a reference implementation for external integrators — `reference/idempotency.md`
   must say plainly what changed and what an existing integrator needs to do differently, not present it
   as a transparent drop-in upgrade.
5. **State the fsync failure mode precisely in the design and its rollout notes**: the real residual risk
   the fix closes is a machine crash/power-loss between `os.replace()` and the OS durably persisting that
   metadata update — not an ordinary process kill, which the existing tempfile+`os.replace` already
   survives cleanly. Avoid overstating the pre-fix risk as data corruption; it is a silent revert to the
   previous record, which reintroduces the exact duplicate-processing hazard this file exists to prevent,
   only in the power-loss case.

None of these five block starting a `system-design` pass — they're precise, implementable requirements
for that pass to satisfy, not open architectural questions.
