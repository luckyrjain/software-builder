# ADR 0006: Host registry and evidence model (`agent-hosts.yaml`)

**Status:** Accepted
**Date:** 2026-09-04

## Context

Before this registry, "which coding-agent hosts does software-builder support, and where does each one
discover a skill?" was answered by three unrelated places: `scripts/registry/host_contracts.yaml`'s
capability matrix, `install.sh`'s hard-coded destination cases, and prose in each skill's `SETUP.md`.
None of them separated *what we have observed a host do* from *what our generated adapter claims to
support* — so a host's support level was an assertion with no attached basis, and there was no way to
record "GitHub's docs say this works, but we have never run it."

The universal-compatibility work introduced a fourth need: a shared, multi-tool discovery directory
(`.agents/skills`) that belongs to no single host, so the "host owns its target" assumption baked into
`install.sh` no longer held.

## Decision

**1. `agent-hosts.yaml` is the canonical, evidence-gated host-identity source**, parsed and validated
fail-closed by `scripts/registry/host_registry.py` (`make validate-hosts`). It models three object kinds:

- **Targets** — a named install destination with a `scope` (`user` | `project`) and a path template
  (`~/...` for user scope, `{project_root}/...` for project scope). `resolve_target_path` is the only
  way a target becomes a concrete path.
- **Hosts** — an id, one or more **surfaces** (`LOCAL` | `REMOTE` | `CLOUD` | `WEB` | `UNKNOWN`), each
  binding targets with a discovery `mode` (`NATIVE` | `ADAPTER` | `ALIAS` | `MANUAL` | `NONE`) and a
  numeric `precedence` where **lower wins**, plus per-capability states, an isolation mode, free-text
  constraints, and the verification block below.
- **Aliases** — alternate host identities, currently empty.

**2. Support is a claim with evidence attached, not a bare assertion.**

Every host carries `verification`, `evidence`, and `maintainer_support`:

- `verification` ∈ {`UNVERIFIED`, `VERIFIED`, `STALE`, `CONFLICTED`}. `UNVERIFIED` is the deliberate
  default: nothing inherits a support level, it must earn one.
- `evidence` is a list of `{kind, reference, observed_at?}` entries, `kind` ∈ {`DOCUMENTATION`,
  `REPOSITORY`, `RUNTIME`}. `observed_at` is the ISO date the evidence was last checked against the
  real host.
- The load-bearing rule, enforced in `host_registry.py`: **`verification: VERIFIED` requires at least
  one `RUNTIME` evidence entry.** A vendor's published documentation is real evidence and is recorded
  as such, but it cannot promote a host on its own — `github-copilot` carries a `DOCUMENTATION` entry
  pointing at GitHub's own skills docs and still sits at `UNVERIFIED` because this repository has never
  run Copilot to confirm the documented behavior holds.
- **`STALE` is derived, not hand-set.** `defaults.evidence_max_age_days` (90) is how long a `RUNTIME`
  observation keeps a host's `VERIFIED` claim current; once every dated `RUNTIME` entry for a
  `VERIFIED` host is older than that, `host_registry.py` reports the host as `STALE` at parse time.
  Freshness is measured against `RUNTIME` evidence only, because that is the kind `VERIFIED` requires
  — re-reading a vendor's documentation does not re-verify a host. Evidence with no `observed_at` never
  ages: "we do not know when this was observed" is a different claim from "this was observed and has
  since expired", and every entry checked in before this field existed makes the former. That is why no
  host's state changes today.
- Capability states are separately `AVAILABLE` | `UNAVAILABLE` | `UNKNOWN`, and start `UNKNOWN` for the
  same reason.
- `maintainer_support` ∈ {`FIRST_CLASS`, `BEST_EFFORT`, `COMMUNITY`, `MANUAL_ONLY`, `DEPRECATED`}
  records the maintainers' own commitment, which is a separate question from what has been verified.
  All four hosts are currently `BEST_EFFORT`, deliberately kept uniform while they are all equally
  `UNVERIFIED`.

The verification state is not decorative: `scripts/registry/compatibility_resolver.py` combines it with
the capability engine's own answer to produce a resolved host × skill status. A concrete `BLOCKED`
capability always wins because it names exactly what is missing; otherwise a `CONFLICTED` or
`UNVERIFIED` host caps the result at `CONFLICTED`/`UNVERIFIED` rather than letting a `READY` claim
stand. `VERIFIED` and `STALE` both let the capability engine's `READY`/`DEGRADED` answer through —
staleness blocks *promotion*, it must not retroactively make an already-working skill unusable.

**3. The universal `.agents/skills` target belongs to no host.**

`agents-user` (`~/.agents/skills`) and `agents-project` (`{project_root}/.agents/skills`) are targets
with no owning host entry. `install.sh --agent agents` resolves through
`scripts/registry/install_resolver.py` directly to one of them — project when `--target-dir` is given,
else user — rather than through any host's discovery list. Because the target is shared with
other tools, install-destination ownership classification (`scripts/reference_utils.py`) is what keeps
an install from clobbering a directory this repository did not create.

**4. `agent-hosts.yaml` and `host_contracts.yaml` answer different questions, and are expected to
diverge.**

`scripts/registry/host_contracts.yaml` carries a six-host roster — `cursor`, `claude`, `codex`,
`chatgpt`, `kiro`, `generic` — consumed by `host_adapter.py` and the P1 adapter-generation path. It
answers **"what does the generated adapter support today"**. `agent-hosts.yaml` carries four hosts —
`cursor`, `claude`, `github-copilot`, `kiro` — and answers **"what has been independently
re-verified"**. The rosters are therefore not required to match, and a mismatch is not by itself a bug:

- `github-copilot` exists only in `agent-hosts.yaml`, with no adapter and no contract entry — a host may
  be modeled for discovery before it is modeled for adapter generation.
- `codex`, `chatgpt`, and `generic` exist only in `host_contracts.yaml` — they are adapter/capability
  contract identities, not hosts with an evidence-gated discovery binding.

Before treating a difference between the two files as drift, establish which question is being asked.

**5. Discovery precedence is a first-class fact, and shadowing is reported.**

Because a host may discover the same skill from more than one target, `scripts/registry/shadow_detector.py`
compares an install destination against the host's higher-precedence bindings and downgrades
`install.sh`'s success message when a *different* copy already occupies a winning root. It warns rather
than blocks: a deliberate project-level override on top of a user-level default is a valid setup, so the
requirement is only that the installer must not claim an install is what will run when it is not.

## Consequences

- **Positive:** A host's support level always carries its basis, and the strongest claim
  (`VERIFIED`) cannot be made from documentation alone.
- **Positive:** New hosts can be modeled — path templates, precedence, constraints — without touching
  `install.sh`'s destination logic or the adapter contract roster.
- **Positive:** `.agents/skills` gives one install destination that several tools can discover, instead
  of one destination per host.
- **Negative:** Two host files exist and their rosters differ on purpose, which reads as drift until the
  reader knows the split. This ADR and the header comment in `agent-hosts.yaml` are the only places that
  say so.
- **Negative:** Every host is `UNVERIFIED` with `UNKNOWN` capabilities, so the registry currently records
  the *absence* of runtime verification rather than its results. Nothing yet schedules re-verification;
  the `STALE` clock only starts once a maintainer records a dated `RUNTIME` observation. Operational
  guidance is in [docs/OPERATIONS.md](../OPERATIONS.md).
- **Follow-ups:** Decide whether `maintainer_support` should be allowed to exceed the verification
  state.
