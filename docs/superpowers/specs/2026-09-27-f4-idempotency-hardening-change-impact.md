# Change impact report — F4: pr-gatekeeper idempotency store hardening

**title:** F4 — pr-gatekeeper idempotency store hardening
**assessment_target:** [2026-09-27-f4-idempotency-hardening-design.md](2026-09-27-f4-idempotency-hardening-design.md) (revision 4, `proposed_state`), validated by [2026-09-27-f4-idempotency-hardening-architecture-review.md](2026-09-27-f4-idempotency-hardening-architecture-review.md) (Approved with conditions)
**coverage_status:** COMPLETE — repository read used to ground every field, including a direct check that `run_log.py`'s `_fsync`/`_fsync_dir` are read-only reused, not modified, and that `check` already acquires `mr_lock` today (confirming the design's own claim that extending `--lock-wait-timeout` to `check` is not introducing a new lock acquisition path, just bounding an existing one)

## material_unknowns

None on the design's own terms — its final (revision 4) scope is deliberately narrow and every aspect has
either a concrete implementation answer or an explicit, disclosed limitation (out-of-order delivery,
forking children, the signal-handling trade-off). The one thing this report cannot verify from a design
document alone is whether the Builder's actual implementation preserves the exact signal-handler-scoping
boundary the design specifies (installed only from `Popen()` onward, never during lock-wait) — that is a
review-time check, not a change-impact unknown, and is called out under `review_triggers` below.

## criticality

**Medium** — lower than A5/A6/F1's tier. `idempotency_store.py` is explicitly documented as a reference
implementation for external integrators (`idempotency_store.py:2-5`), not code any of software-builder's
own skills invoke, unlike `orchestrator.md`/`run_log.py`'s `EVENTS` validation which sit on
`loop-task-implementer`'s own hot path. The one thing that keeps this above **Low**: this file's `main()`
CLI contract (exit codes, flag behavior) is documented in `reference/idempotency.md` as a stable
integration surface, and revision 4's own Failure strategy section names a genuine, disclosed behavioral
change (the SIGINT/uncooperative-child trade-off) — a defect in *how* that trade-off is actually
implemented, not just documented, would silently change what "safe to retry" means for whoever depends on
this file's exit codes.

## change_classes

- **Modified existing module**: `skills/pr-gatekeeper/scripts/idempotency_store.py` — `mr_lock()` gains
  bounded-wait + non-truncating lock-file open + pid-diagnostic write on every acquisition path;
  `save_record()` gains an fsync step; `run_if_new()` migrates `subprocess.run()` → `Popen()`/`wait()` with
  a scoped signal handler; CLI argparse gains `--lock-wait-timeout` (all three actions) and validates it;
  two new exit codes (`3`, `4`)
- **Modified existing doc**: `skills/pr-gatekeeper/reference/idempotency.md` — action-behavior table,
  disclosed-limitations section
- **Modified existing tests**: `skills/pr-gatekeeper/tests/test_idempotency_store.py` — additive only (new
  test functions); the 9 existing tests must pass with **zero changes to their own bodies**, since they are
  the concrete evidence for the design's own "byte-for-byte unchanged when flags omitted" claim
- **No new files**, **no new stored data field**, **no new dependency** (all additions are stdlib: `signal`,
  `subprocess.Popen` in place of `subprocess.run`, `os.fsync`/`fcntl.fcntl`/`F_FULLFSYNC` via the same
  pattern `run_log.py` already uses)
- **No CODEOWNERS, no CI workflow, no `docs/github-ruleset-main.json` change** — matches A6's own
  conclusion that the existing wildcard already covers this path; confirmed by direct read, not assumed

## impacted_repositories

- `luckyrjain/software-builder` only.

## impacted_services

- N/A — local CLI/file-based tooling, no runtime service.

## impacted_contracts

- **`run_if_new`'s child-execution mechanism** (`idempotency_store.py:94-108` today): confirmed by direct
  read — the current call is `subprocess.run(command, check=False)` with `command` as a list, `shell=False`
  (the default), stdio inherited (no `PIPE`). The design's migration to `Popen(command)` + explicit
  `.wait()` is behaviorally neutral for argv-list semantics (`subprocess.run` is implemented in terms of
  `Popen` internally) **provided stdio stays inherited**, which the design does not propose changing.
  Confirmed: no shell-vs-list contract change.
- **`mr_lock`'s file-open mode** (`idempotency_store.py:45-56` today): confirmed by direct read — currently
  `open(lock_path, "w", encoding="utf-8")`, which truncates on every open, including a contender's. This is
  a real, load-bearing fix (not cosmetic): without it, the new pid-diagnostic write the design adds would be
  unreliable under contention. The design's replacement (`os.open(path, os.O_RDWR | os.O_CREAT, 0o600)`,
  matching `install_engine.py:69-77`'s `_open_lock_file`) is confirmed accurate against that file's actual
  source.
- **`run_log.py`'s `_fsync`/`_fsync_dir`** (`run_log.py:875-923`, confirmed by direct read, matching the
  architecture review's own citation): this design **reuses these functions' pattern read-only** — it does
  not modify `run_log.py` itself. No change lands on that file, so its 12 rounds of prior hardening are
  undisturbed. This is a materially different (safer) situation than A6's change, which had to *add* a new
  event type to `run_log.py`'s own validated `EVENTS` tuple; here the dependency is one-directional
  (idempotency_store.py copies a pattern), so `run_log.py`'s own review history does not need re-opening.
- **`check`'s existing lock-acquisition path** (`idempotency_store.py:144-146`, confirmed by direct read):
  `check` already calls `mr_lock` today, same as `mark`. The design's claim that extending
  `--lock-wait-timeout` to `check` is "not a new lock acquisition path, just bounding an existing one" is
  accurate — this was the specific gap round 3's Software Architect review caught (revision 3's own
  documentation omitted this despite the code already doing it).
- **The CLI's exit-code contract, documented in `reference/idempotency.md`**: codes `0`/`1`/`2` are
  explicitly preserved unchanged (confirmed: no code in the design repurposes them); `3`/`4` are net-new.
  This is an external-facing contract for a file documented as "for webhook handlers" — see
  `operational_impacts` below.

## impacted_data

- New on-disk data: none. `last_processed_head_sha`'s stored shape is unchanged (revision 4 dropped the
  ordinal field entirely along with the rest of the descoped machinery).
- Lock file (`.locks/<project>-mr-<iid>.lock`): gains a reliably-written pid-diagnostic byte range (was
  previously vulnerable to being clobbered by a truncating contender open) — existing lock files need no
  migration, the new open mode is compatible with any pre-existing (possibly zero-length) file at that path.

## impacted_dependencies

- **`scripts/tests/install_lock_test_helpers.py`'s `spawn_lock_holder` pattern** (confirmed present and
  reusable, same as A5/A6): the design's own Rollout plan calls for a real cross-process lock-contention
  test; this repo already has the harness for it, no new test infrastructure needed.
- **`reference/idempotency.md`'s existing action-behavior table and "Recommended caller pattern" section**
  (confirmed by direct read): needs updating for `--lock-wait-timeout`, the two new exit codes, and the
  disclosed limitations/trade-off — the design's own Rollout plan already names this.
- **No new PyPI dependency** — confirmed stdlib-only (`signal`, `subprocess.Popen`, `os.fsync`,
  `fcntl.fcntl`/`F_FULLFSYNC` via the same conditional pattern `run_log.py:875-884` already uses).
- **`make lint-python`** sweeps the modified file automatically, same as every prior script this session.
- **No dependency on the cut ordinal/process-group machinery from revisions 1-3** — confirmed nothing in
  the final design references `--ordinal`, `os.killpg`, or `--emit-outcome`; a scan of the design doc for
  those tokens turns up only historical mentions inside the explicitly-labeled "Revision history" section,
  not the current contract.

## impacted_owners

- Repo owner (`@luckyrjain`), sole owner, unchanged. `pr-gatekeeper`'s own skill ownership is unaffected —
  this file is explicitly documented as not on that skill's own execution path.

## required_tests

- Every one of the 9 existing tests in `test_idempotency_store.py` must pass with **no changes to their own
  bodies** — this is the concrete, checkable form of the design's "byte-for-byte unchanged when flags
  omitted" claim; a Reviewer should treat any edit to an existing test's assertions (as opposed to adding
  new test functions) as a signal the claim may not hold.
- Real cross-process lock-contention test proving `--lock-wait-timeout` actually times out (exit `3`) and
  names the holder's pid, exercised against **all three** actions (`check`, `mark`, `run-if-new`), using
  `install_lock_test_helpers.py`'s `spawn_lock_holder` pattern per the design's own Rollout plan.
- `--lock-wait-timeout nan` / `--lock-wait-timeout -1` rejected at parse time (exit `2`).
- Cooperative-child signal test: real subprocess that catches SIGTERM and exits cleanly — assert
  `mark_processed` was skipped and the wrapper returns promptly (exit `4`).
- Uncooperative-child signal test: real subprocess that ignores/traps the forwarded signal and keeps
  running — assert the wrapper **blocks** rather than returning early, per the design's own disclosed
  trade-off (this is the one test that would fail loudly if a Builder "improved" the design back toward
  automatic escalation, which the owner explicitly cut).
- Explicit SIGINT case (not just SIGTERM) — assert the child is actually terminated, not silently orphaned
  by an uncaught `KeyboardInterrupt` from the `subprocess.run()`→`Popen()` migration losing that library's
  own implicit kill-on-interrupt behavior.
- Lock-wait-phase signal test: SIGTERM sent to a process blocked in the **default unbounded** lock-wait
  (a second real process holds the lock, no `--lock-wait-timeout` passed) — assert it still exits promptly,
  proving the new signal handler is scoped to post-spawn only, per the design's own stated boundary.
- fsync-sequence test matching `run_log.py`'s own test style (mock or inspect that `_fsync`-equivalent
  calls happen on the temp file before `os.replace()` and on the containing directory after).

## operational_impacts

- **Disclosed behavioral change for external integrators**: `reference/idempotency.md` must state plainly
  that a child which ignores a forwarded stop signal now requires an operator-issued `SIGKILL` to reclaim
  the lock — today, `subprocess.run()`'s own internal handling already killed an unresponsive child on
  `SIGINT`/`SIGTERM` without any wait. Any integrator who built implicit reliance on that accidental fast
  path (unlikely, since it was never documented as a feature, but not verifiably absent given this is a
  reference file with an unknown installed base) would see different behavior after adopting this change.
- **No new Actions minutes, no impact on required checks** — same as every prior finding this session for
  changes confined to `scripts/`/`skills/*/scripts/`.
- **Lower operational stakes than A5/A6**: this file is not invoked by any of software-builder's own skills;
  the blast radius of a defect here is bounded to whichever external integrator copies the updated file,
  same posture the original architecture review already established.

## review_triggers

- **Recommended, not required**: verify the Builder's actual implementation preserves the exact
  signal-handler-scoping boundary the design specifies — installed only from `Popen()` returning onward,
  never wrapping the lock-wait phase. This is the single most load-bearing correctness property in the
  design (round 3's SRE finding was specifically about this boundary being unspecified in revision 3, now
  fixed in prose in revision 4) — a Builder who installs the handler one scope too early would silently
  reintroduce the exact regression round 3 caught. Both `loop-task-implementer` review lenses should treat
  this as a named check, not incidental coverage.
- No other hard trigger under this skill's own vocabulary — no external API, no database, no new attack
  surface, and the harder problems (process-group reaping, ordinal DoS-bounding) were deliberately cut
  rather than built, so there is nothing at that tier left to specialist-review.

## unknowns

- Whether a future revision re-admits `--ordinal`/process-group reaping once this narrower version has
  been in use and the owner decides the added complexity is warranted after all — explicitly out of scope
  for this change, not a gap in this analysis.

## evidence_refs

- `docs/superpowers/specs/2026-09-27-f4-idempotency-hardening-design.md` (revision 4, full document,
  including its own Revision history section)
- `docs/superpowers/specs/2026-09-27-f4-idempotency-hardening-architecture-review.md` (Approved with
  conditions)
- `skills/pr-gatekeeper/scripts/idempotency_store.py:2-5,45-56,79-108,111-152` (current file, confirming
  the truncating lock-file open, `subprocess.run` usage, and `check`'s existing lock-acquisition path)
- `skills/pr-gatekeeper/tests/test_idempotency_store.py` (existing 9 tests, the concrete back-compat
  contract)
- `skills/pr-gatekeeper/reference/idempotency.md` (current action-behavior table and caller-pattern
  section)
- `scripts/install_engine.py:69-145` (`_open_lock_file`/`_try_lock`/`_write_holder_pid`/`_read_holder_pid`,
  the precedent for the lock-file fix)
- `skills/loop-task-implementer/scripts/run_log.py:875-923` (`_fsync`/`_fsync_dir`, confirmed read-only
  reused, not modified)
- `scripts/tests/install_lock_test_helpers.py` (the reusable real-subprocess test harness)
