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
`last_processed_head_sha` store for webhook handlers (`check` / `mark` CLI). Tests:
`tests/test_idempotency_store.py`.

## Out of scope for this skill

- Cross-process locking inside pr-gatekeeper (no shared state store in the skill package).
- Replacing the caller's `last_processed_head_sha` store — that remains integration-owned per `SETUP.md`.

See also: [pressure-tests.md](pressure-tests.md) duplicate-webhook row and Tier-2 transcript fixture
`evals/transcripts/pr-gatekeeper/duplicate-webhook.yaml`.
