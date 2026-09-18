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
- **Resolved (2026-09-18):** a second SIGTERM during cleanup no longer abandons it.
  `_sigterm_as_system_exit()` only protects the primary staged/mutating work, and the cleanup
  that runs *after* a signal is caught (`_cleanup_failed_install()`'s rollback, `held_lock()`'s
  own `finally: shutil.rmtree(lock_dir, ...)`) runs after the `with` block that registered it
  has already exited -- so a second, closely-timed signal used to terminate the process
  mid-cleanup. `held_lock()`'s own release is self-healing (a stale/partial lock is reclaimed
  by the next waiter), but `_cleanup_failed_install()`'s rollback is not: nothing sweeps an
  orphaned `.{skill}.staging.*`/`.{skill}.backup.*` directory left by a kill mid-rollback.
  Both now run under a new `_defer_sigterm()`: a signal arriving during the block is recorded,
  the cleanup runs to completion, and only then does the process exit 130. Deliberately
  *deferred*, not converted to `SystemExit` the way the primary work's signal is -- a first
  attempt did convert it, which made the exit code clean but still interrupted the rollback
  itself partway, leaving exactly the orphan it exists to prevent. The tests assert the
  cleanup actually *completed* (directory gone), not just the exit code, and were checked
  against that weaker convert-style version to confirm they'd have failed on it. Residual:
  a signal that can't be caught at all (SIGKILL, power loss) still can, and a hard kill
  between `_acquire_lock_dir()`'s temp-directory creation and its rename can still orphan
  that temp directory -- nothing short of an external sweeper addresses those, and they're
  the same accepted gap `install_skill()`'s staging/backup directories always had.
