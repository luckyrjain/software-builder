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
- **Follow-up:** unify the shadow-warning message *formatting* the same way (tracked
  separately, not blocking on this ADR).
- **Follow-up:** make lock creation genuinely atomic (e.g. a single `O_CREAT | O_EXCL` file
  write instead of `mkdir` + two `write_text()` calls) instead of relying on staleness
  fallbacks to make a non-atomic window safe. Not done here because the current on-disk lock
  format (`.{skill}.lock/pid`, `.{skill}.lock/acquired_at` as separate files) is directly
  inspected by `scripts/tests/test_install_concurrency.py` and
  `test_install_engine_locking.py`; a format change needs its own pass.
