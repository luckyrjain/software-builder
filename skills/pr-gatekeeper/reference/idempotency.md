# Idempotency and concurrent runs — pr-gatekeeper

pr-gatekeeper assumes the **calling webhook integration** owns deduplication for duplicate deliveries of the
same `head_sha` (`workflow/inputs.md` § Event filtering). That short-circuit is necessary but **not
sufficient** when two genuinely concurrent pushes arrive for the same MR before either run finishes.

## What the skill guarantees

| Scenario | Behavior |
|----------|----------|
| Duplicate webhook with same `head_sha` as `last_processed_head_sha` | Inputs short-circuit — no second pr-review invocation |
| Concurrent overlapping runs for the same MR | **Not serialized by pr-gatekeeper itself** — caller must enforce |

## Recommended caller pattern

Integrators should wrap each gatekeeper invocation with a **per-MR lock** (or lease) keyed by
`project` + `merge_request_iid`:

1. Acquire lock (file lock, Redis lease, DB advisory lock — org choice).
2. Re-check `head_sha` against the integration's `last_processed_head_sha` store **after** acquiring the
   lock (double-checked locking).
3. Invoke pr-gatekeeper only if the head is still new.
4. Persist `last_processed_head_sha` only after a successful run completes.
5. Release lock in a `finally` block.

Without step 1–2, two overlapping runs can both pass the pre-lock dedupe check and invoke pr-review twice.

## Reference implementation

[scripts/idempotency_store.py](../scripts/idempotency_store.py) — file-based per-MR lock +
`last_processed_head_sha` store for webhook handlers.

| Integration style | Pattern |
|-------------------|---------|
| **Shell webhook** | `run-if-new` holds the lock for the full gatekeeper subprocess: `idempotency_store.py ... run-if-new -- <gatekeeper-cmd>` |
| **Python handler** | `with mr_lock(...):` → `should_process` → invoke gatekeeper → `mark_processed` on success |
| **Testing only** | Separate `check` / `mark` CLI actions (lock not held between them) |

Tests: `tests/test_idempotency_store.py`.

### Action behavior and exit codes

Every action takes the same `--store-root` / `--project` / `--merge-request-iid` / `--head-sha`
arguments, plus an optional `--lock-wait-timeout <seconds>` (finite, non-negative; `nan`/`inf`/
negative values are rejected at parse time with exit `2`). Omitting the flag preserves the
previous, genuinely unbounded lock wait byte-for-byte — this is an additive change, not a
default-behavior change.

| Action | `0` | `1` | `2` | `3` | `4` |
|--------|-----|-----|-----|-----|-----|
| `check` | Head is new (unprocessed) | Duplicate — already processed | Usage error | Lock held past an opted-in `--lock-wait-timeout` (error names the current holder's pid) — `check` has always acquired the same per-MR lock as `mark`/`run-if-new`, this just bounds an existing wait | N/A |
| `mark` | Head persisted | N/A | Usage error | Same as `check` | N/A |
| `run-if-new` | Command ran and exited `0` (marked) | Duplicate head — command not run | Usage error (e.g. missing command after `--`) | Same as `check`/`mark` | Interrupted: SIGINT/SIGTERM/SIGHUP arrived while the command was running, forwarded to it, `mark_processed` skipped |

Codes `3` and `4` are net-new and additive — `0`/`1`/`2` are unchanged from before this hardening,
including for any integrator who has already deployed this file and does not pass
`--lock-wait-timeout`. As before, a wrapped command's own exit code passes through `run-if-new`
unchanged when it isn't `0`, `1`, `3`, or `4` — a wrapped command that happens to exit with one of
those codes has always collided with this file's own contract, same posture this file already had
for `1`.

### Signal handling for `run-if-new`

Once the wrapped command's subprocess exists, `run-if-new` forwards SIGINT, SIGTERM, and SIGHUP
(POSIX only) to that direct child only — not to any process group, and not to any descendants the
child itself forks. `mark_processed` is skipped unconditionally for that run, even if the child
happens to exit `0` after the signal was forwarded, and the run reports exit `4`.

**Disclosed trade-off, not a hidden regression.** Before this change, `run-if-new` called
`subprocess.run()`, whose own internal exception handling already reliably killed an unresponsive
child the moment SIGINT (as `KeyboardInterrupt`) or an uncaught SIGTERM reached the wrapper,
without the wrapper ever needing to wait for it. Migrating to `Popen()` + `proc.send_signal()` +
`.wait()` — needed so the signal can be forwarded and `mark_processed` can be skipped correctly —
removes that accidental fast path: **a child that ignores the forwarded signal now makes
`run-if-new` block in its own `.wait()` for as long as that child keeps running**, and reclaiming
the lock early requires an operator to send `SIGKILL` directly to the `run-if-new` process itself
(which the OS-level `flock` then releases immediately, the same way it always has under any hard
kill). This is a deliberate, disclosed choice — kill-escalation that would close this gap
automatically was evaluated and cut as disproportionate to this file's scale (see the design doc's
Revision history) — not a bug to work around.

The lock-wait phase itself (before the child exists, whether the wait is the default unbounded one
or a `--lock-wait-timeout`-bounded one) is untouched by any of this: every signal's ordinary
default disposition applies there exactly as it always has.

**Accepted, disclosed limitations, unchanged by this hardening:**

- **Out-of-order webhook delivery** remains unprotected — `should_process`/`mark_processed` compare
  only against the single `last_processed_head_sha`, with no ordering/sequence signal. Both GitHub
  and GitLab document webhook delivery as at-least-once and not strictly ordered; an older
  `head_sha` delivered after a newer one was already marked can still silently "revert" the stored
  head. If an integrator needs strict ordering, it must be enforced by the caller (e.g. a
  sequence/timestamp check before invoking this file at all).
- **A wrapped command that itself forks additional processes** is only partially covered — only
  the direct child receives the forwarded signal; any descendants it spawns may keep running after
  `run-if-new` returns.

## Out of scope for this skill

- Cross-process locking inside pr-gatekeeper (no shared state store in the skill package).
- Replacing the caller's `last_processed_head_sha` store — that remains integration-owned per `SETUP.md`.

See also: [pressure-tests.md](pressure-tests.md) duplicate-webhook row and Tier-2 transcript fixture
`evals/transcripts/pr-gatekeeper/duplicate-webhook.yaml`.
