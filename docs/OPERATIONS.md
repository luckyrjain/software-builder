# Operations runbook

What to do when a software-builder tool fails in a way that needs a human decision. Release mechanics
live in [RELEASE.md](RELEASE.md); stale golden fixtures have their own runbook in
[evals/GOLDEN-REFRESH.md](evals/GOLDEN-REFRESH.md).

## Stale install lock

**Symptom:** `error: timed out waiting for lock on <skill> at <dest>/.<skill>.lock (held by pid N)`

`scripts/install.sh` serializes concurrent installs of the same skill into the same destination root
with a lock *directory* at `<dest_root>/.<skill>.lock` — `mkdir` is atomic and, unlike a symlink, cannot
be pre-planted to redirect a later write. The waiter clears a lock on its own in two cases: the recorded
PID is no longer alive (`kill -0`), or the lock is older than `LOCK_STALE_SECONDS` (default 300). It
gives up after `LOCK_WAIT_TIMEOUT_SECONDS` (default 30).

Seeing the timeout therefore means the lock is younger than `LOCK_STALE_SECONDS` **and** its holder
could not be proved dead — either the recorded PID is alive on this host, or there is no readable
`pid` file to check. In order:

1. Check whether that PID really is another install (`ps -p <N>`). If it is, wait for it — installs are
   seconds long, and two installs into one destination must not run concurrently.
2. If the PID belongs to something unrelated, the lock is a PID-reuse artifact. Either wait out
   `LOCK_STALE_SECONDS` (the next attempt clears it automatically) or re-run with a shorter window:
   `LOCK_STALE_SECONDS=0 bash scripts/install.sh <skill>`.
3. Remove `<dest_root>/.<skill>.lock` by hand only after confirming no install is running. The lock
   directory holds just `pid` and `acquired_at`; deleting it loses nothing.

A killed install does not leave a half-written skill: the installer stages into a temporary directory,
validates it, moves any existing install aside to a same-filesystem backup, and restores that backup if
the final move fails. A leftover `.<skill>.staging.*` or `.<skill>.backup.*` directory next to the lock
is safe to delete once no install is running.

## Host evidence refresh

`agent-hosts.yaml` records what has been independently verified about each host — `verification`,
`evidence` entries, and `maintainer_support` — and `make validate-hosts` enforces the shape. Promoting a
host to `verification: VERIFIED` requires at least one `RUNTIME` evidence entry; vendor documentation is
recorded as `DOCUMENTATION` evidence and cannot promote a host on its own.

Record each run as a `RUNTIME` evidence entry with the date you observed it — `{kind: RUNTIME,
reference: ..., observed_at: YYYY-MM-DD}` — rather than editing `verification` alone, and run
`make validate-hosts`. `defaults.evidence_max_age_days` (90) then ages the claim for you: once every
dated `RUNTIME` entry for a `VERIFIED` host is older than that, the parser reports it as `STALE`, and a
fresh dated run is what restores `VERIFIED`. An entry with no `observed_at` never ages, so evidence
recorded before that field existed keeps its declared state until someone re-verifies it.

**Nothing schedules re-verification** — the clock only tells you a past observation has expired, it
does not go and make a new one. Re-verify when a host ships a change to where or how it discovers
skills, when a capability claim is contradicted in practice, or before making a stronger
`maintainer_support` claim. See [ADR 0006](adr/0006-host-registry-and-evidence-model.md) for the model
and its known gaps.

## When to bump `VERSION`

`VERSION` is the distribution version stamped into installed manifests and release bundles. A tagged
release fails at `scripts/verify_release_tag.py` unless the tag is exactly `vMAJOR.MINOR.PATCH` and its
version equals `VERSION` — that check compares tag to file, so it cannot tell you that a *change*
needed a bump nobody made.

Bump before tagging, in the change that ships the behavior:

- **Major** — a registry schema, install packaging, or skill workflow contract changes incompatibly
  (see [RELEASE.md § Breaking changes](RELEASE.md#breaking-changes)). Ship migration notes in
  `CHANGELOG.md`; a major bump is the signal to a user that an upgrade or rollback may need manual steps.
- **Minor** — new skills, new registry fields, new install targets, or any other additive change a user
  could depend on.
- **Patch** — fixes and documentation that change no contract.

Editing `VERSION` without tagging is harmless; tagging without editing it fails the release workflow.

## Broken or missing generated roster

**Symptom:** `error: ALL_SKILLS is empty/undefined -- make/generated-roster.mk is missing or stale; run 'make generate' to regenerate it`

`make/generated-roster.mk` is generated from `skills.yaml` and pulled in with `-include`, not `include`,
precisely so this is recoverable: a plain `include` on a missing file aborts Make before any target —
including `generate`, the recovery command — can run. Run `make generate`, then `make generate-check` to
confirm nothing else drifted.

The same command is the fix for any generated-file drift `make generate-check` reports, including
`skills.yaml`'s `skills:` mapping, which is merged from `scripts/registry/skills.d/*.yaml` fragments
(see [ADR 0005](adr/0005-registry-authoring-model.md)). Never hand-edit a generated region to make the
check pass — fix the source and regenerate.
