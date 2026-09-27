# System Design Spec — F4: pr-gatekeeper idempotency store hardening

**Readiness: Ready to implement**

Revision 4 — closes round 3's findings against the deliberately-descoped revision 3 (see Revision history).
All three round-3 reviewers confirmed the narrow scope itself (bounded lock-wait, fsync, direct-child-only
signal forwarding, small exit-code scheme) is sound and did not ask to reopen anything cut in revision 3.
Round 3's findings were precise gaps within that narrow scope — mostly honesty-of-claim and
signal-semantics-scoping issues — not new missing features.

## Revision history

**Revision 1**: initial design — lock timeout, signal-forwarding, fsync fix, `--ordinal` reject-older-head,
`--emit-outcome`.

**Revision 1 → 2** (round 1, 8 converged findings): fixed a false back-compat claim, added process-group
signaling, ordinal bounds/mandatory-adoption, a lock-file truncation bug, moved `--emit-outcome` to stderr,
dropped exit code `130` for a plain `4`.

**Revision 2 → 3** (round 2, both Security Architect and SRE independently found the same deeper
process-group-confirmation bug, plus an unsafe third-signal escape hatch and an ordinal-enforcement scope
gap): **owner decision** to cut process-group reaping, kill-escalation, and ordinal reordering entirely
rather than keep patching an escalating bug chain — descoped to unbounded-by-default lock timeout, fsync,
direct-child-only signal forwarding, and a small exit-code scheme, with out-of-order-delivery and
forking-children explicitly documented as accepted, unsolved limitations.

**Revision 3 → 4** (round 3, final — confirms the descoping itself was sound; all three reviewers found only
in-scope gaps, no reopened territory):

- **Security Architect + SRE (independently, same underlying issue from two angles)**: the design's "no
  regression" claim for signal-forwarding was false in the exact case the feature exists to help. Moving
  from `subprocess.run()` to `Popen()`+`proc.send_signal()`/`wait()` silently **removes** an existing,
  accidental safety net — `subprocess.run()`'s own internal exception handling already reliably kills the
  child on `KeyboardInterrupt` today. **Fixed**: the design now explicitly enumerates the forwarded signal
  set (SIGINT, SIGTERM, SIGHUP) and states plainly, as a disclosed trade-off rather than a hidden
  regression, that a child which ignores the forwarded signal now requires an operator-issued `SIGKILL` to
  reclaim the lock — whereas today, a plain Ctrl-C already did that automatically via `subprocess.run`'s own
  behavior.
- **SRE**: signal-handler scoping during the *lock-wait* phase (before any child exists) was unspecified —
  if the handler were active there and silently absorbed a signal, it would make the deliberately-preserved
  unbounded default lock-wait **uninterruptible** except by `SIGKILL`, a real regression against today's
  "any signal kills the process, lock-wait included" baseline. **Fixed**: the design now states the handler
  is installed only from the moment the child is spawned onward — lock-wait (bounded or unbounded) keeps
  today's exact signal disposition, untouched.
- **Software Architect**: `check`'s row never stated it also gets exit `3` on an opted-in lock-wait timeout,
  despite `check` already acquiring the same lock as `mark`/`run-if-new` today. **Fixed**: `check`'s
  behavior row and the state-machine table now say so explicitly.
- **Suggestions taken**: reject non-finite/negative `--lock-wait-timeout` values at parse time; corrected a
  cross-platform-precedent wording nit for the lock file's byte-0 comment; confirmed (and now states
  explicitly) that the pid-diagnostic write happens on every successful lock acquisition, not just a
  bounded one, and includes a truncate-before-write step matching `install_engine.py`'s
  `_write_holder_pid` exactly.

## Components

| Component | Responsibility | Boundary / owns | Notes |
|-----------|-----------------|------------------|-------|
| `idempotency_store.py` (existing, hardened) | Per-MR file lock + `last_processed_head_sha` store; CLI entrypoint for `check`/`mark`/`run-if-new` | `<store-root>/<project>/mr-<iid>.json`, `<store-root>/.locks/<project>-mr-<iid>.lock` | Data model and CLI argument shape otherwise **unchanged** — no new stored field |
| `mr_lock` (existing, hardened) | Optionally-bounded exclusive lock acquisition, used by **all three** actions (`check`, `mark`, `run-if-new`) | The `.lock` file's `flock` state + a pid-diagnostic byte range | Lock file opened via non-truncating `os.open(path, os.O_RDWR \| os.O_CREAT, 0o600)`, matching `install_engine.py`'s `_open_lock_file`. The pid-diagnostic write (`os.ftruncate(fd, 0)` then seek-and-write at `_PID_TEXT_OFFSET`, mirroring `install_engine.py`'s `_write_holder_pid` exactly) happens on **every** successful acquisition across all three actions, not only when `--lock-wait-timeout` is passed — otherwise a concurrently-waiting bounded caller's timeout error could name a stale pid |
| `_forward_signal_to_child` (new, deliberately minimal) | Traps **SIGINT, SIGTERM, SIGHUP** — installed **only from the moment `Popen()` returns**, never during lock acquisition — forwards the received signal to the direct child only, then performs the same ordinary blocking `proc.wait()` this file already does today; skips `mark_processed` for that run | The single `Popen` object; main-thread only, POSIX-only | No process groups, no escalation, no separate confirm-timeout. Explicitly does **not** wrap the lock-wait phase — before the child exists, every signal's default disposition applies exactly as it does today (an uncaught `SIGTERM` terminates the process immediately; `SIGINT`'s default handler raises `KeyboardInterrupt`, which propagates through `mr_lock`'s `finally` and exits), so the deliberately-preserved unbounded default lock-wait remains as interruptible as it is today |
| `reference/idempotency.md` (existing, updated) | Documents the CLI contract, exit codes, and the disclosed limitations (out-of-order delivery, forking children, **and now the signal-handling trade-off** below) | Doc only | |

## APIs

| Endpoint / method | Contract | Consumer(s) | Notes |
|--------------------|----------|-------------|-------|
| `idempotency_store.py --store-root R --project P --merge-request-iid N --head-sha S [--lock-wait-timeout T] check` | Exit `0` if `S` is unprocessed, `1` if duplicate, **`3` on an opted-in lock-wait timeout (same as `mark`/`run-if-new` — `check` already acquires the same lock today)**. Byte-for-byte unchanged when `--lock-wait-timeout` is omitted. `T` must be finite and non-negative — `nan`/`inf`/negative values are rejected at parse time (exit `2`), since a `nan` comparison against an elapsed-time check would silently produce an unbounded wait from a caller who explicitly asked for a bounded one. | Webhook integrators, tests | |
| `... mark` | Persists `S` as processed. Exit `0`, or `3` on an opted-in lock-wait timeout. Same `T` validation as `check`. | Webhook integrators, tests | |
| `... run-if-new -- <command>` | Holds lock (`3` on opted-in timeout), skips duplicate heads (exit `1`), else runs `<command>` as a child, marks on child exit `0`. Exit `4` if any of SIGINT/SIGTERM/SIGHUP arrives once the child is running: forwarded to the child, `mark_processed` skipped, wrapper then waits for the child exactly as it already does today (unbounded, no escalation). **Disclosed trade-off, not a hidden regression**: if the child ignores the forwarded signal, the wrapper now blocks until the child exits or an operator sends `SIGKILL` directly to the wrapper — today, by contrast, `subprocess.run()`'s own internal exception handling already reliably kills an unresponsive child the moment `KeyboardInterrupt`/`SIGTERM` propagates, without the wrapper needing to wait it out. Codes `3`/`4` are a small, new, disclosed collision class with a child's own exit code, same posture this file already had for code `1`. | Webhook integrators (shell style) | |

## Events

None found.

## Data model

| Entity | Key fields | Relationships | Owner |
|--------|-----------|-----------------|-------|
| MR record (`mr-<iid>.json`) | `last_processed_head_sha: str` (unchanged) | One record per `(project, merge_request_iid)` | `idempotency_store.py` |
| Lock file (`.locks/<project>-mr-<iid>.lock`) | Byte 0: reserved to mirror `install_engine.py`'s cross-platform layout (where it holds the mandatory Windows byte-range lock) — **unused on this file**, which is POSIX/`fcntl`-only and locks the whole fd, not a byte range; byte offset 1+ (`_PID_TEXT_OFFSET`): holder pid as ASCII text, diagnostic only, written (with a truncate-before-write step) on every successful acquisition | One per `(project, merge_request_iid)` | `mr_lock` — non-truncating open so this survives a contender's open |

## State machines

| Entity | States | Transitions | Notes |
|--------|--------|-------------|-------|
| Any invocation's lock acquisition (`check`/`mark`/`run-if-new` alike) | `LOCK_WAIT -> {LOCK_TIMEOUT \| LOCK_HELD}` | `LOCK_TIMEOUT` only reachable if `--lock-wait-timeout` was passed; exit `3` for all three actions | Signal disposition during `LOCK_WAIT` is untouched — today's default behavior for every signal applies exactly as it does today, this revision installs no handler here |
| A `run-if-new` invocation, post-lock | `LOCK_HELD -> {DUPLICATE_SKIP \| RUNNING}`, `RUNNING -> {CHILD_EXITED \| INTERRUPTED}`, `CHILD_EXITED -> {MARKED \| NOT_MARKED}` | `RUNNING -> INTERRUPTED` on SIGINT/SIGTERM/SIGHUP, forwarded to the child; terminal — `mark_processed` is unconditionally skipped even if the child happens to exit `0` after the signal was forwarded | The signal handler is installed only for this `RUNNING` phase (from `Popen()` returning to `proc.wait()` completing), not before |

## Consistency

| Boundary | Model (strong / eventual) | Why |
|----------|-----------------------------|-----|
| `mr_lock` acquisition | Strong, single-machine | `flock`, unchanged from today |
| `should_process` read-then-act | Strong *within the lock* | Unchanged |
| Delivery ordering | **Not modeled** — explicitly out of scope | Architecture review Condition 4's "(b)" outcome |

## Retries & idempotency

| Operation | Idempotent? | Retry / backoff strategy |
|-----------|-------------|----------------------------|
| `mark` / `run-if-new`'s mark step | Yes — unchanged | N/A |
| Lock acquisition | No automatic retry; unbounded by default (all three actions), bounded only if `--lock-wait-timeout` is passed | Caller-driven |
| Signal-interrupted run (exit `4`) | Yes — nothing was marked, a fresh delivery safely re-attempts | Caller-driven |

## Capacity

| Dimension | Estimate | Basis |
|-----------|----------|-------|
| Concurrent MR locks | Not a realistic constraint | Bounded by concurrent in-flight MRs |

## Failure strategy

| Failure mode | Degradation / mitigation |
|--------------|-----------------------------|
| Lock held past an opted-in `--lock-wait-timeout` (any of `check`/`mark`/`run-if-new`) | Exit `3`, error names the holder's pid (reliable now under contention, and now confirmed written on every acquisition path, not only bounded ones) |
| Stop signal arrives while the child is running, child exits promptly (cooperative) | Forwarded, `mark_processed` skipped, wrapper returns quickly — clear improvement over today's silent orphaning |
| **Disclosed trade-off, not a silent regression**: stop signal arrives while the child is running, child ignores/traps it (uncooperative) | Wrapper blocks holding the lock until the child eventually exits or an operator sends `SIGKILL` directly to the wrapper. This is genuinely different from **today's** actual behavior on the same signal — `subprocess.run()`'s own internal handling already reliably kills an unresponsive child on `KeyboardInterrupt`/an uncaught `SIGTERM`, without any wait. Kill-escalation that would close this gap automatically was cut in revision 3 as disproportionate to this file's scale; this revision accepts and states the trade-off rather than hiding it |
| Stop signal arrives during the **lock-wait** phase (before a child exists), any action, bounded or unbounded | Untouched — today's default signal disposition applies exactly as it does today; this revision installs no handler until after the child is spawned |
| **Accepted, disclosed limitation**: a wrapped command that itself forks additional processes | Only the direct child is signaled; descendants may keep running |
| **Accepted, disclosed limitation**: out-of-order webhook delivery | Unprotected, per architecture review Condition 4's "(b)" |
| Ordinary process kill between `save_record`'s write and `os.replace()` | Already safe — atomic at the directory-entry level |
| Machine crash / power loss between `os.replace()` and durable persistence | Narrowed by fsyncing the temp file then the containing directory, matching `run_log.py`'s `_fsync`/`_fsync_dir` exactly |
| `--lock-wait-timeout` given a non-finite or negative value | Rejected at parse time (exit `2`) — a `nan` timeout would otherwise silently defeat its own bound (a `waited >= nan` comparison is always false) |

## Observability

| Signal | What's measured |
|--------|-------------------|
| Exit code `3` (lock timeout) | Reachable from any action once `--lock-wait-timeout` is opted into; names the holder's pid |
| Exit code `4` (interrupted) | Distinguishes a clean skip/run from a run that was killed mid-flight and wasn't marked |

No `--emit-outcome` — cut along with the rest of the descoped surface.

## Rollout plan

| Phase | Scope | Feature flag / migration order |
|-------|-------|----------------------------------|
| 0 | Tests: unbounded-by-default lock-wait regression (every existing test in `test_idempotency_store.py` unmodified); real lock-contention test proving a bounded `--lock-wait-timeout` times out and names the holder pid, exercised from **all three** actions; `--lock-wait-timeout nan`/`-1` rejected at parse time; a real-subprocess signal-forwarding test with a **cooperative** child (catches SIGTERM, exits cleanly — `mark_processed` skipped, wrapper returns promptly); a second signal-forwarding test with an **uncooperative** child (ignores/traps the forwarded signal, keeps running) asserting the wrapper blocks rather than returning early, and that this is deliberate per the disclosed trade-off, not a hang bug; an explicit **SIGINT** case alongside the SIGTERM case, confirming the child is actually terminated, not silently orphaned by an uncaught `KeyboardInterrupt`; a test sending SIGTERM to a process blocked in the **default unbounded lock-wait** (a second process holds the lock, no `--lock-wait-timeout` passed) asserting it still exits promptly, exactly as today; fsync-sequence test matching `run_log.py`'s own style | No flag — script, not a service |
| 1 | Land the code, update `reference/idempotency.md`'s action-behavior table (including `check`'s exit `3`), and state both disclosed limitations plus the signal-handling trade-off explicitly | Merge gate: both `loop-task-implementer` review lenses clean, `make lint-python`, full test suite green |

## Open questions

None.
