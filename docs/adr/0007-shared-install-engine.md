# ADR 0007: `install.sh` shells out to `scripts/install_engine.py` instead of a parallel bash port

**Status:** Accepted  
**Date:** 2026-09-18

## Context

`sb install`/`sb uninstall`/`sb verify` (#259) were implemented by porting `install.sh`'s
locking and stage/backup/replace/cleanup state machine into a new, deliberately **parallel**
Python module, `scripts/install_engine.py` — `install.sh` itself was explicitly not touched,
by design, so the port could land without risk to the existing bash path. The module's own
docstring recorded this as a "wholly separate, parallel implementation for `sb`, not a shared
engine install.sh is refactored onto."

That boundary had already started eroding within the same review window: shadow-precedence
warnings were explicitly scoped out of the initial port, then ported back six commits later
(#266) with hand-matched wording. A codebase-architecture review of the `sb` CLI subsystem
(2026-09-18) found the two implementations had already drifted in ways a parity test would
have caught for every other `sb` subcommand (`doctor`/`list`/`explain`/`compatibility` each
have one) but this one did not:

- The ownership-block error wording diverged ("refusing to install over a symlink" vs.
  `install.sh`'s golden-tested "refusing to replace symlink").
- `install_engine.py`'s `held_lock()` treated a lock directory with an as-yet-unwritten `pid`
  file as immediately stale and reclaimable; `install.sh`'s own bash `acquire_lock` does not
  — it falls through to the age check and waits. This divergence was latent (only `sb
  install`'s own concurrent use exercised it) until `install.sh` began delegating to the same
  function under real concurrency, where it surfaced as an intermittent `FileNotFoundError`
  (fixed as part of this same change, not deferred).

`install.sh` was never bash-only to begin with — it already shells out to Python
(`run_python`) for `package_skill.py`, `install_support.py`'s destination classification and
target resolution, and `validate_references.py`. Keeping the locking/rollback state machine
as a second, hand-synced implementation had no technical justification once that was checked;
it was scope discipline for the original porting task, not a standing constraint.

## Decision

- `scripts/install_engine.py` is the single implementation of the install/uninstall state
  machine (locking, staging, backup, atomic replace, rollback-on-failure). `install_skill()`/
  `uninstall_skill()` are called in-process by `sb install`/`sb uninstall`
  (`cli/sb/__main__.py`), and via a new CLI (`python3 -m scripts.install_engine
  install|uninstall ...`, one subprocess call per skill × destination) by `install.sh`.
- `install.sh` no longer holds its own lock or performs its own staging/backup/replace; its
  `install_skill`/`uninstall_skill` bash functions are now thin wrappers: a couple of cheap
  pre-checks (skill-name format, registry membership) plus one call into the shared engine.
- User-facing message wording (ownership-block errors, dry-run/success lines) is bash's
  historical, golden-tested text — `install_engine.py`'s outcome objects carry that wording
  now, so `sb`'s own CLI output changed to match it, unifying wording across both entry
  points instead of the reverse.
- The shadow-precedence *detection* (`scripts/registry/shadow_detector.py`) was already
  properly shared before this change (both `install.sh`, via `install_support.py
  check-shadow`, and `sb`'s `_warn_if_shadowed` call the same `detect_shadow`); only the two
  callers' warning-message *formatting* still differs. That is a narrower, separate finding,
  not folded into this change.

## Consequences

- **Positive:** One state machine to reason about and test; the `held_lock()` staleness bug
  above would previously have needed fixing twice (or drifted further) had it been found
  later. This is a mitigation, not a root-cause fix — lock acquisition is still `os.mkdir()`
  followed by two separate `write_text()` calls, not one atomic operation, so a window with an
  identity-less lock directory still exists; the fix makes that window's consequences safe
  (wait, not wrongly reclaim) rather than closing the window itself.
- **Positive:** `install.sh`'s install path drops an internal-implementation-detail stdout
  line (`validate_references.py`'s own `"ok: <staging-dir>"` banner, a leftover of shelling
  out to that script separately) — one fewer subprocess invocation per install, not just
  fewer lines of duplicated logic.
- **Negative:** `install.sh`'s `uninstall` no longer re-checks registry membership before
  removing a skill (a deliberate divergence `install_engine.py` already carried for `sb
  uninstall`, documented as "arguably safer, not a gap" — ownership classification alone
  still bounds what gets touched). `install.sh` previously did perform that check.
- **Resolved (2026-09-18):** the shadow-warning message *formatting* is unified too now --
  `shadow_detector.render_shadow_warning()` is the one place that wording lives;
  `install_support.py`'s `check-shadow` prints the rendered line for `install.sh` to relay
  verbatim (a dumb newline-presence check, not a second copy of which statuses warn), and `sb
  install`'s `_warn_if_shadowed` calls it directly.
- **Resolved (2026-09-18):** lock creation is genuinely atomic now, without a format change.
  `_acquire_lock_dir()` builds a temp directory (same filesystem as `dest_root`, fully
  populated with `pid`/`acquired_at`) and `os.rename()`s it into place as `lock_dir` in one
  step -- a waiter's rename attempt fails exactly when a bare `os.mkdir(lock_dir)` used to
  fail, but now `lock_dir` is never visible at its canonical path before it's fully
  populated, closing the window the three prior staleness-fallback layers existed to
  tolerate. The on-disk format (`.{skill}.lock/pid`, `.{skill}.lock/acquired_at` as separate
  files) is unchanged, so `scripts/tests/test_install_concurrency.py` and
  `test_install_engine_locking.py` needed no format migration -- only two tests whose premise
  was specifically the now-closed mid-setup window (one rewritten to cover the new "an empty
  leftover lock dir is claimed directly, not waited on" behavior; the staleness-fallback
  tests still exercise real gaps, now via a non-empty-but-identity-less directory rather than
  a bare one, since a directory rename's failure semantics differ from a plain `mkdir`'s: an
  empty destination is silently replaced, matching "already vacated," so those tests were
  adjusted to stay non-empty). One residual, accepted risk: `_acquire_lock_dir()`'s own temp
  directory (`.{skill}.lock.tmp.*`) can be orphaned under a hard kill (SIGKILL, power loss)
  between its creation and the rename that either publishes or discards it -- nothing sweeps
  a stray one later, the same accepted gap `install_skill()`'s
  `.{skill}.staging.*`/`.{skill}.backup.*` directories already have under an equivalent
  window (the SIGTERM item below resolved the narrower, closely-related case of a *second*
  signal during cleanup, but not a hard kill). A second, empirically-verified interaction was found and
  judged benign, not fixed: `os.rename()` onto an *empty* existing directory succeeds (unlike
  a bare `os.mkdir()`, which fails unconditionally against anything at that path), so a new
  acquirer's rename can land in the brief window of the *previous* holder's own release
  (`held_lock()`'s `finally: shutil.rmtree(lock_dir, ...)`, after it has unlinked `pid`/
  `acquired_at` but before it removes the now-empty directory itself) — reproduced via a
  forced interleaving. The new acquirer wins cleanly; the departing holder's own `rmdir` then
  fails (already swallowed by `ignore_errors=True`) since the path is occupied again. No
  double-critical-section results, because this window only opens after the departing
  holder's guarded `with` body has already returned — its protected work is done by then, not
  still in flight. A real, separate bug this same review found *was* fixed: a TOCTOU where
  classifying a rename failure by re-checking `lock_dir.exists()` afterward (rather than by
  the exception's own `errno`) could re-raise an ordinary, already-resolved contention
  failure as a hard error if the contender finished releasing in the gap — closed by
  classifying on `errno` (`ENOTEMPTY`/`EEXIST`) instead, which has no such gap.
- **Resolved (2026-09-18):** an interrupt during cleanup no longer abandons it, and a signal
  aimed at `install.sh` itself now reaches the engine. `_sigterm_as_system_exit()` only
  protects the primary staged/mutating work; the cleanup that runs *after* a signal is caught
  (`_cleanup_failed_install()`'s rollback, `held_lock()`'s own `finally: shutil.rmtree(...)`)
  runs after the `with` block that registered it has exited, so a second, closely-timed signal
  used to terminate the process mid-cleanup. `held_lock()`'s release is self-healing (the next
  waiter reclaims a stale/partial lock), but the rollback is not: nothing sweeps an orphaned
  `.{skill}.staging.*`/`.{skill}.backup.*` directory, and a rollback cut short can leave the
  user's previous install sitting in the backup with nothing at the destination. Both now run
  under `_defer_interrupts()`: SIGINT or the terminate signal arriving during the block is
  recorded, the cleanup runs to completion, and only then does the process exit 130.
  - *Deferred, not converted to `SystemExit`.* A first attempt converted it: cleaner exit code,
    but the rollback was still interrupted partway. Its tests only asserted the exit code, so
    they passed anyway; the tests now assert the cleanup actually *completed* and were checked
    against that weaker version.
  - *SIGINT is deferred too.* An interactive Ctrl-C mid-rollback is at least as likely as a
    supervisor's SIGTERM, and Python's default would raise `KeyboardInterrupt` straight through
    it (reproduced: exit 130, staging left behind, previous install displaced into the backup).
  - *A recorded signal is never lost.* It is raised after the block whether the block returned
    or raised (superseding, and chained to, the in-flight exception). An earlier version dropped
    it when the rollback itself failed, so `sb install a b c` carried on after being told to
    stop. The interrupt handler in `install_skill()` likewise treats cleanup as best-effort
    (warns on failure) so a failed rollback can't convert the interrupt into a "failed" outcome.
  - *Main thread only.* `signal.signal()` raises `ValueError` elsewhere, so both context
    managers are no-ops off the main thread; a direct `held_lock()` user on a worker thread got
    a crash and a stranded lock without that.
  - *Through `install.sh`.* `kill <install.sh pid>` -- the usual way a supervisor stops it --
    never reached the engine: bash died at once and the engine was orphaned to init, finished
    the install anyway, and left the lock/staging behind if later killed hard. `install.sh` now
    runs the engine via `run_engine()`: a background child with TERM/INT trapped and forwarded,
    waiting for the engine's *own* exit status. Ctrl-C arrives as that forwarded TERM (an async
    child of a non-interactive shell has SIGINT ignored). Verified end to end by signalling the
    bash PID alone, and against the old script to confirm the test fails on it.
  - *Round-2 hardening.* The success path's own backup removal runs under the deferral too
    (an orphaned `.{skill}.backup.*` is never swept). A signal that was already ignored
    (`nohup`, an async child of a non-interactive shell) is left ignored by both context
    managers rather than turned into an abort. Handlers are recorded before being replaced,
    inside the `try`, so a signal landing between the SIGINT and SIGTERM installs still
    restores both. When a deferred signal supersedes a cleanup that itself failed, a
    `cleanup failed while handling an interrupt` warning is printed, since the `SystemExit(130)`
    would otherwise hide that failure.
    `run_engine()` polls for the engine's exit rather than blocking in `wait`, whose status a
    trapped signal could replace with 143 (which callers don't recognise as a stop), installs its
    trap before launching the engine, and returns 130 for a stop request even when the engine
    finished cleanly first.
  - *Round-3 hardening.* Lock reclaim was found to break mutual exclusion: a waiter that lost the
    race to a holder's release read the vanished lock as "unreadable, therefore stale" and
    renamed whatever a third party had acquired in between (two holders at once, reproduced with
    8 processes). A vanished lock now just retries the acquire, and a genuine reclaim compares the
    identity (`pid`/`acquired_at`) of the directory it moved with the one it judged stale,
    putting it back if they differ; a lock that cannot be judged (unreadable age *and* mtime) is
    waited on, not taken. Stale names are unique, a failing reclaim rename counts toward the
    timeout, pids `<= 0` or too large for a C int are treated as dead, the lock temp directory is
    removed on any interrupt, and waiting for a lock converts SIGTERM to the clean exit 130.
    `uninstall` renames the skill aside before deleting it, so a failed or interrupted deletion
    can't leave a half-removed, manifest-less directory that neither command would touch. Lock
    timing env values must be finite, and positive for the stale age. In `install.sh`, any stop
    request now ends the run with 130 (an engine killed by the forwarded TERM before installing
    its handler used to read as a plain failure and the run carried on); a script-level trap
    gives a stop outside `run_engine` the same code. `sb install`/`uninstall` report an interrupted
    batch and exit 130 for SIGINT and SIGTERM.
  - *Round-4 hardening.* The empty-lock removal added for Windows was first a rename-based reclaim, and
    it broke mutual exclusion (every release passes through an empty directory, so the reclaim became a
    hot path); it is now an `rmdir`, which cannot remove a populated lock. SIGHUP is a stop signal like
    SIGTERM (engine and `install.sh`); an ignored one (`nohup`) is left ignored. The uninstall restore is
    deferred. `.removing.*`/`.staging.*` leftovers are swept under the lock on the next run for that
    skill; `.backup.*` never is, since it can hold the only copy of a previous install.
  - *Residual-risk fixes.* `_sigterm_as_system_exit()` became two-phase (first stop signal raises, later
    ones are absorbed) and now also covers SIGINT, with `install_skill()`'s cleanup inside the block, so
    there is no longer a gap between the work ending and the rollback's deferral starting. Hard kills
    (SIGKILL, power loss) now self-heal on the next install/uninstall of the skill: orphaned lock temp
    directories older than 5 minutes are swept, a `.backup.*` is restored when the destination is absent
    and discarded only when the destination is a complete owned install, `.removing.*`/`.staging.*` are
    swept. A SIGKILLed `install.sh` no longer leaves the engine running: the engine polls its parent and
    stops itself (opt-in via `INSTALL_ENGINE_EXIT_WITH_PARENT`, set by `install.sh`). What remains is
    inherent: the process is gone until the next run cleans up, and the lock reclaim window below.
  - *Residual (round 3).* `_reclaim_stale_lock()` checks the identity of what it moved, but
    judging, moving and putting back is not one atomic step, so a third holder acquiring in that
    few-microsecond window is displaced. A signal in the couple of bytecodes between the lock
    rename succeeding and `acquired` being set leaves a lock naming this process's pid, which goes
    stale as soon as the process exits.
  - *Residual.* A signal landing in the few bytecodes between the primary work's
    `_sigterm_as_system_exit()` exiting and the rollback's `_defer_interrupts()` starting hits
    the default disposition; closing it needs the handler to stay installed across that
    hand-off. Signals that cannot be caught (SIGKILL, power loss), including SIGKILL of the
    `install.sh` process itself (which orphans the engine, as before), are unaddressed -- nothing
    short of an external sweeper handles them. A hard kill between `_acquire_lock_dir()`'s
    temp-directory creation and its rename can still orphan that temp directory, the same
    accepted gap `install_skill()`'s staging/backup directories always had. A deferred signal
    arriving during a *successful* install's lock release exits 130 with the skill installed
    and the "Installed" line unprinted -- the process was told to stop and did, but the exit
    code doesn't distinguish that from an interrupted install.
