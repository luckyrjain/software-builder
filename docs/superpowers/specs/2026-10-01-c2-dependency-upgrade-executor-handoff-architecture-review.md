# Architecture review — C2: dependency-upgrade-review → executor handoff

**Decision: Approved with conditions**

Sound in shape — reuses C1's own just-converged pattern (legacy-envelope bypass, a real tested
classification function instead of prose, an independent downstream Reviewer backstop) rather than
re-deriving a new mechanism — but the ticket's own acceptance criteria ("stepwise upgrade plan becomes
tasks") introduce a genuinely new wrinkle C1 never had: ONE upgrade request can require MULTIPLE,
sequentially-dependent tasks, unlike C1's one-task-per-qualifying-finding model. Five conditions need
closing before implementation.

## Architecture decision

Four coupled pieces:

1. **A new `cross-skill-escalation.md` row pair**: `dependency-upgrade-review → loop-task-implementer`,
   confirmed via direct research to not yet exist (only `security-review ↔ dependency-upgrade-review`
   rows exist today) — mirrors C1's own just-established forward/reverse row convention exactly.
2. **A real, tested classification function** (mirroring C1's `classify_security_finding` precedent,
   itself mirroring B3's `validate_repro_command` precedent): `DEPENDENCY_UPGRADE_REPORT.md`'s own real,
   fixed 4-state verdict (`Do not upgrade yet` > `Blocked — insufficient info` > `Upgrade with
   mitigations` > `Safe to upgrade`, confirmed at the real `report-format.md`) is the natural, already-
   existing selection signal — `Safe to upgrade` and `Upgrade with mitigations` qualify for task-
   authoring; `Do not upgrade yet` and `Blocked — insufficient info` never do, by the same "real function,
   not prose a human applies by eye" discipline C1's own review history hard-won.
3. **Stepwise task decomposition (the genuinely new piece C1 didn't need)**: a single upgrade request
   (`dependency_name`, `current_version` → `target_version`) can require multiple, ordered, dependent
   steps when the version distance is large enough that a direct jump is unsafe (e.g. skipping multiple
   major versions) — the ticket's own "stepwise upgrade plan becomes tasks" acceptance criterion names
   this explicitly. This needs a concrete decomposition rule and an explicit statement of how step N+1's
   task depends on step N's completion, which C1 never had to solve (its own findings were always
   independent, never a necessarily-ordered chain).
4. **A rollback-note requirement** (the ticket's own explicit acceptance criterion): citing
   `DEPENDENCY_UPGRADE_REPORT.md`'s own real "Rollout risk" section (which already discusses
   reversibility/downgrade-path per the real report-format spec) as the source, never re-deriving this
   from scratch.

## Risks

| Risk | Section | Severity | Notes |
|------|---------|----------|-------|
| "Stepwise upgrade plan becomes tasks" could be read as license to invent a NEW multi-task-dependency mechanism when the legacy envelope bypass (C1's own precedent) has no `dependencies` field at all — confirmed by C1's own review history (SRE's finding on the legacy bypass's real field list) | Architecture decision | Blocking | See Conditions §1 |
| Reusing a 4-state verdict as a 2-way qualify/don't-qualify split needs the SAME "fail toward the safe side on ambiguity" discipline C1's own classification function established — a naive implementation could fail open toward `Safe to upgrade` on a malformed/ambiguous report instead of toward the non-qualifying states | Security | Blocking | See Conditions §2 |
| The standing CVE-training-cutoff caveat (`report-format.md`'s own disclosed limitation: CVE findings are reasoned from training-time knowledge, not a live advisory database) could be silently forgotten once a report's verdict is reduced to a single qualify/don't-qualify bit for task-authoring purposes — a human reading only the resulting task would lose this context entirely | Operability | Conditional | See Conditions §3 |
| C1's own central, twice-recurring bug (a mechanism described as "structural"/"by construction" while actually being an unenforced human convention) is a real risk class for THIS ticket too, given the stepwise-decomposition piece is new and unprecedented — must be designed with the same scrutiny from round 1, not discovered three rounds in | Architecture decision | Conditional | See Conditions §4 |
| Transitive-dependency conflicts (a real section in the existing report format) could themselves require their OWN upgrade, creating a potential unbounded cascade of dependent tasks if not explicitly scoped | Scale limits | Conditional | See Conditions §5 |

## Scale limits

| Dimension | Breaks down at | Evidence |
|-----------|-----------------|----------|
| Number of sequential steps in one stepwise upgrade chain | Unbounded if no explicit cap is stated — a sufficiently large version gap could in principle decompose into many steps | No existing precedent in this codebase for a bounded multi-task dependency chain originating from one upstream report; C1's own 1:1 (or small-merge-group) model never had to bound this |
| Transitive-dependency cascade (a flagged transitive conflict spawning its own upgrade task, which could itself have transitive conflicts) | Needs an explicit statement that this ticket scopes to the ONE directly-requested dependency's own upgrade, with transitive conflicts surfaced in the report as information for a human to separately decide on — not auto-escalated into their own recursive task chain | Not addressed by the ticket's own acceptance criteria; must be scoped explicitly, not left to drift |

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| A stepwise chain's step N fails or is rejected, but step N+1 was already authored/dispatched assuming N succeeded | Requires the same dependency-respecting task-selection discipline this skill already has for a planned (non-legacy) `implementation_plan`'s own `dependencies` field — but the legacy envelope bypass C1 established has NO such field | Must be resolved: either steps are authored and dispatched one at a time (step N+1 only authored after step N's own PR merges), or the stepwise decomposition explicitly does NOT use the legacy envelope bypass for anything beyond a single step | This is the ticket's own central new design question — see Conditions §1 |
| A verdict-to-qualification mapping fails open on a malformed/missing-field report | Requires the same fail-closed discipline as C1's `classify_security_finding` | Fails toward the non-qualifying/human-action-required state, never toward autonomous task-authoring | See Conditions §2 |
| A human reads a dependency-upgrade-derived task with no visibility into the standing CVE-training-cutoff caveat the original report disclosed | Requires the caveat to be explicitly carried into the task's own citation, not silently dropped when the report is reduced to a classification bit | A missing caveat doesn't cause an unsafe autonomous action by itself, but it does degrade the human's own ability to judge residual risk | See Conditions §3 |

## Security

| Concern | Trust boundary / data flow | Blast radius | Notes |
|---------|------------------------------|---------------|-------|
| `changelog_text`/`manifest_excerpt` are explicitly untrusted (per the real report-format's own Safe-rendered-output-boundary section) — any downstream task envelope populated from this report must maintain the SAME citation-by-reference discipline C1 established, never embedding raw changelog/manifest excerpts verbatim | Citation-by-reference only, mirroring C1's own Rule-5-re-redaction discipline for a report's own free-text fields | A verbatim-embedded changelog/manifest excerpt could carry an injected instruction or an embedded secret one hop downstream into the Builder's own task context | Must be stated explicitly as a requirement, not assumed inherited "because C1 did it" |
| Automatically triggering a version bump based on a 4-state verdict is a materially different risk shape than C1's own single-finding classification — a dependency upgrade can touch arbitrarily many files/call sites across the whole codebase, unlike a single-finding, single-file security fix | New, not present in C1 | A broad, codebase-wide autonomous change driven by an automated classification | Must be assessed on its own terms, not assumed safe by analogy to C1's narrower blast radius |

## Operability

| Concern | Owner | Operating cost | Notes |
|---------|-------|------------------|-------|
| Deciding the stepwise decomposition for a large version gap | Repo owner / Orchestrator, or `dependency-upgrade-review` itself if re-invoked per hop | Real, new cost class this ticket introduces — not present in C1 | Must be named explicitly, not assumed free |
| Each step's own PR must keep tests green (the ticket's own explicit acceptance criterion) | Existing Builder/Reviewer completion-gate discipline already enforces this for every task this skill dispatches | No new operability cost — this is already how every task works | Correctly not a new mechanism to invent |

## Alternatives considered

| Alternative | Why not chosen | Notes |
|-------------|-------------------|-------|
| No handoff at all (current state) | Rejected: literally the gap this ticket exists to close | Correctly motivates building something |
| Treat every upgrade as exactly one task regardless of version distance, no stepwise decomposition | Rejected: directly contradicts the ticket's own explicit "stepwise upgrade plan becomes tasks" acceptance criterion | Not a real option given the ticket's own stated requirement |
| Build a brand-new, planned (non-legacy) `implementation_plan` with real `dependencies` fields for the stepwise chain, rather than reusing the legacy envelope bypass | A real candidate, left open for `system-design` to weigh against the simpler legacy-bypass-plus-sequential-dispatch alternative — not pre-decided here | See Conditions §1 |
| Reuse C1's exact classification-function shape unmodified | Reasonable as a starting point, but the underlying signal (a 4-state verdict vs. C1's 3-state classification) and risk shape (codebase-wide blast radius vs. single-finding) are different enough that `system-design` should re-derive the mapping on its own merits, not copy C1's literal keyword logic | Matches C1's own "Precedent for Epic C" framing: the PATTERN generalizes, the literal content doesn't |

## Conditions

1. **Resolve the stepwise-decomposition mechanism concretely**: either (a) each step is authored and
   dispatched one at a time, with step N+1 only authored after step N's own PR has actually merged (no
   new `dependencies` field needed, sequential-dispatch discipline instead), or (b) state explicitly why a
   real dependency-respecting mechanism is needed and how it's built given the legacy envelope bypass's
   own real field limitations. Do not leave this as an unspecified "stepwise" gesture.
2. **Build the verdict-to-qualification classification as a real, tested function**, mirroring C1's
   `classify_security_finding` precedent exactly — fail-closed toward the non-qualifying/human-action-
   required state on any ambiguous or malformed report input, never fail-open toward autonomous
   task-authoring.
3. **State explicitly how the standing CVE-training-cutoff caveat is carried forward** into any
   downstream task's own citation — not silently dropped when the report's verdict is reduced to a
   classification bit.
4. **Apply the same "is this actually code-enforced or just a documented convention" scrutiny from round
   1**, given this ticket's own stepwise-decomposition piece is genuinely new and unprecedented — name
   explicitly, for each new mechanism this ticket introduces, whether it's backed by real code or is a
   disclosed, human/Orchestrator-applied convention.
5. **State an explicit scope boundary for transitive-dependency conflicts**: a transitive conflict
   flagged in the report is surfaced as information for a human to separately decide on, never
   auto-escalated into its own recursive upgrade-task chain — this ticket scopes to the one, directly-
   requested dependency's own upgrade only.

None of these five block starting a `system-design` pass — they're precise, implementable requirements
for that pass to satisfy, not open architectural questions.
