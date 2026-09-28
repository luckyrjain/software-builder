# Architecture review — F2: per-skill platform support declaration + install-time enforcement

**Decision: Approved with conditions**

Sound direction — reusing `risk_class`'s exact schema-validation precedent for a new `platforms` field,
and hooking enforcement into `install_engine.py`'s single, already-cross-platform `install_skill()` entry
point, both match this repo's own established conventions rather than inventing new ones. Four conditions
need closing before implementation, none of them a redesign — the most important is that this repo has
direct, recorded precedent (ticket F7, same tracking doc) that a "required, hand-authored" schema field
does not reliably get populated, and this design must not repeat that mistake silently.

## Architecture decision

Two components close gap-backlog ticket F2, plus one belt-and-suspenders fix the ticket's own framing
implies. (1) A new per-skill `platforms` field in `skills.yaml`/`scripts/registry/skills.d/*.yaml`,
schema-validated in `scripts/registry/schema.py` following `risk_class`'s exact pattern (an enum-checked
list, modeled in `SkillEntry`), documented in `CONTEXT.md`'s glossary alongside `risk_class`/write-authority,
and rendered as a new column in the generated skills table. (2) Install-time enforcement hooked into
`install_engine.py`'s `install_skill()`, immediately after the existing registry-membership check and
before the ownership-classification check — one hook point covers both `sb install --agent` and
`install.sh`, and the dry-run path, since both already funnel through this single function. (3) Guard the
two skills (`pr-gatekeeper`'s `idempotency_store.py`, `migration-program-manager`'s
`aggregate_migration_status.py`) that currently do an unconditional top-level `import fcntl` — mirroring
`run_log.py`/`install_engine.py`/`plan_state_store.py`/`task_lease.py`'s already-established guarded-import
pattern — so a Windows invocation that reaches these scripts at all (whether or not the install gate
caught it first) fails with a clean, readable message instead of a raw `ModuleNotFoundError`.

## Risks

| Risk | Section | Severity | Notes |
|------|---------|----------|-------|
| A "required, hand-authored" `platforms` field would very plausibly repeat ticket F7's own finding — 26 of 50 skills never got a required `risk_class` populated despite schema enforcement — leaving most skills either falsely blocked (fail-closed on a missing field) or silently unprotected (fail-open, defeating the ticket's purpose) | Failure modes | Blocking | See Conditions §1 |
| The install-time gate only protects hosts that route through `install_skill()` (`sb install`, `install.sh`) — `skills.yaml`'s own `hosts:` block shows other hosts (e.g. Cursor's rule-based discovery, GitHub Copilot's/Kiro's manual discovery) never call this function at all, so they get zero protection from this mechanism regardless of how `platforms` is declared | Scale limits / Operability | Blocking | See Conditions §2 |
| Any automatic/derived detection of a skill's real platform support (e.g. grep for `import fcntl`) is a heuristic, not a proof — it would miss a POSIX-only dependency that isn't `fcntl` (e.g. `pwd`, `grp`, `termios`, a POSIX-only third-party package), silently misclassifying a skill as Windows-safe when it isn't | Failure modes | Conditional | See Conditions §1, §3 |
| A hard refuse (vs. a warning) at install time compounds the risk above — a false-positive from an imperfect detection heuristic would incorrectly block an install that would have actually worked | Operability | Conditional | See Conditions §3 |

## Scale limits

| Dimension | Breaks down at | Evidence |
|-----------|-----------------|----------|
| Number of skills needing a `platforms` declaration | Not a realistic constraint — ~50 skills today, one-time schema addition plus (per Condition 1) a default that doesn't require a manual pass over all of them | Confirmed via direct read of `skills.yaml`/`scripts/registry/skills.d/` |
| Host coverage of the install-time gate | **Breaks down immediately for any host that doesn't route through `install_skill()`** — confirmed via `pr-gatekeeper`'s own `hosts:` block (Cursor: `discovery: rule`, GitHub Copilot/Kiro: `discovery: manual`, only Claude: `install: true`) that most non-Claude-Code hosts use a different discovery path entirely | See Conditions §2 — this is a real, present-day scale limit, not a hypothetical future one |

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| `platforms` required but left unpopulated for most skills (F7's own precedent) | Schema validation would catch a missing field only if failing closed — which then blocks installs of every under-populated skill, a worse regression than today | A derived/defaulted value (Condition 1) sidesteps this structurally rather than relying on a future hand-authoring pass that this repo's own history shows doesn't reliably happen | Named explicitly rather than assumed away |
| Detection heuristic misses a real POSIX-only dependency, skill is declared (or defaults to) Windows-safe incorrectly | None automatic — the install gate would pass, and the skill would still fail deep into execution | **This is exactly what Component 3 (the guarded-import fix) exists for** — even when the registry/gate layer is wrong, the script's own guard turns the eventual failure into a clean, readable message instead of a raw crash. Component 3 is defense-in-depth, not a lower-priority afterthought | Worth stating explicitly so it isn't deprioritized relative to the registry field, which is the flashier but less universally protective piece |
| A host that bypasses `install_skill()` entirely (rule/manual discovery hosts) installs or invokes a POSIX-only skill on Windows | None from this design's Component 2 — only Component 3's per-script guard still applies, since it runs regardless of how the skill was discovered/installed | Same as above — Component 3 is the only piece of this design with universal coverage | See Conditions §2 |
| A skill's declared `platforms` value turns out to be wrong in practice, with no CI ever having exercised it on the claimed platform | None — `install-engine-windows` CI (per this repo's own F5/F6 history) tests the shared install engine, not each individual skill's own runtime behavior | None short of adding per-skill Windows smoke tests, which is disproportionate to this ticket's scope | See Conditions §4 — must be disclosed as a trust-level claim, not a verified guarantee |

## Security

| Concern | Trust boundary / data flow | Blast radius | Notes |
|---------|------------------------------|---------------|-------|
| A skill author could declare an inaccurate `platforms` value | Self-authored registry content, solo-maintainer trust domain — not adversarial input | Same as any other metadata error in this registry today (e.g. a wrong `risk_class`) | Not a new class of exposure; no new trust boundary is crossed by adding this field |

## Operability

| Concern | Owner | Operating cost | Notes |
|---------|-------|------------------|-------|
| Keeping `platforms` accurate as skills evolve | Repo owner | Low if defaulted/derived (Condition 1); would be meaningfully higher, and historically unreliable per F7, if hand-authored and required | Same "curated, can drift" cost class as `risk_class`/A6's `.claude/settings.json` |
| Explaining to a Windows user why the install gate didn't catch a failure it appeared to guard against | Repo owner, via documentation | Low, one-time | Directly addressed by Condition 4's disclosure requirement |

## Alternatives considered

| Alternative | Why not chosen | Notes |
|-------------|-------------------|-------|
| Do nothing beyond fixing the two raw-crash skills' import guards (Component 3 only, skip the registry field and install gate) | Cheaper, but leaves the ticket's own core complaint unaddressed — a Windows user can still install and dispatch `loop-task-implementer` only to discover incompatibility deep into a real run, with zero pre-install signal | Rejected as insufficient against the ticket's explicit ask, but correctly identifies Component 3 as valuable on its own regardless of the other two |
| Full CI-verified Windows compatibility testing for every skill claiming Windows support | Would give the strongest guarantee, but this repo has no existing precedent for per-skill (as opposed to shared-install-engine) Windows CI, and building it for ~50 skills is disproportionate to this ticket's scope | Correctly out of scope for now; worth naming as a future escalation path in the design, not silently ignored |
| Required, hand-authored `platforms` field (exact `risk_class` clone) | This repo's own F7 finding shows a required schema field can go unpopulated for roughly half of all skills in practice — repeating that pattern here would either falsely block most installs or silently provide no protection | Correctly avoided per Condition 1, in favor of a derived default |

## Conditions

1. **Specify a concrete default/derivation strategy for `platforms`, not a required hand-authored field.**
   Given this repo's own recorded F7 finding that a required schema field does not reliably get populated
   across all ~50 skills, the design must define an automatic default (e.g. defaulting every skill to
   `[posix, windows]` unless a documented detector — such as a grep for an unconditional `import fcntl`/
   platform-specific import — or an explicit `skills.d` override says otherwise) so the mechanism provides
   real protection from day one without depending on a manual, error-prone authoring pass.
2. **State plainly, in whatever doc/report surfaces this feature, that the install-time gate only covers
   hosts routing through `install_skill()`** (`sb install`, `install.sh`) — hosts using rule-based or manual
   discovery (confirmed present today in `skills.yaml`'s own `hosts:` blocks) receive no protection from
   this mechanism. Do not let the design imply universal coverage it cannot provide.
3. **Decide and justify warn-vs-refuse explicitly**, weighing the false-positive risk from Condition 1's
   necessarily-imperfect detection heuristic — a hard refuse amplifies the cost of a wrong classification,
   a warning does not. Pick one (or a threshold-based hybrid) and state the reasoning, rather than defaulting
   silently to whichever the ticket's own wording happened to list first.
4. **Disclose that a skill's declared `platforms` value is a trust-level claim, not a CI-verified
   guarantee**, since no per-skill Windows smoke-test precedent exists in this repo today (only the shared
   install engine itself is Windows-CI-tested). Component 3 (the guarded-import fix) must be treated as a
   first-class, universally-applicable part of this ticket's fix — not a lower-priority afterthought to the
   registry field — since it is the only piece of this design that offers protection regardless of which
   host discovered the skill or whether the `platforms` declaration was accurate.

None of these four block starting a `system-design` pass — they're precise, implementable requirements
for that pass to satisfy, not open architectural questions.
