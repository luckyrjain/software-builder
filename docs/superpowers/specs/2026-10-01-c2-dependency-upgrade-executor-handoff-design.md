# System Design Spec — C2: dependency-upgrade-review → executor handoff

**Readiness: Ready with open questions**

## Revision history

**Revision 1** (initial): reused C1's pattern wherever it applies unmodified (legacy-envelope bypass, a
real tested classification function, an independent downstream Reviewer backstop), and designed one
genuinely new piece C1 never needed — a stepwise, sequentially-dependent multi-task decomposition for a
large version gap — stated honestly as a human/Orchestrator-applied convention, not code-enforced,
deliberately pre-empting C1's own round-1 "claimed structural, actually convention" mistake.

Round 1 adversarial review (Security Architect, SRE, Software Architect — all three, fresh, in parallel)
converged on one central defect from two independent angles, plus four more real gaps. One sub-finding
(Software Architect's claimed `app_run`/16-field error) was independently re-verified against
`origin/main` and found **false** — B7 is merged (`d74b3fd`, PR #318) and `app_run` is the real 16th
field of `implementation_task`; that sub-finding is dropped, the rest of that review stands. Fixed in
**revision 2** (this revision):

- **The stepwise-sequencing mitigation didn't actually hold, and the blast radius is worse than C1's
  merge-rule ever was** (Security Architect AND SRE, independently convergent — the central finding).
  Revision 1 asserted that a premature hop N+1 "would visibly mismatch... via the Builder's own git
  state" — an unconfirmed property stated as fact, the same overclaim shape as C1's round-1 "structural
  impossibility," except here the silent-failure mode is worse: a premature hop doesn't surface as a
  mis-scoped task, it can silently execute a larger, unintended version jump that passes tests and reviews
  as an ordinary bump. Compounding this, `dependency-upgrade-review`'s own report-format states inputs are
  "not validated beyond presence," so re-invoking it for hop N+1 inherits any stale `current_version`
  rather than catching it. **Fixed**: a new, real, tested function,
  `verify_dependency_hop_precondition`, reads the manifest/lockfile's actual pinned version at Builder
  dispatch time and aborts the task if it doesn't match the hop's declared `expected_current_version` —
  converting the disclosed convention into a code-enforced precondition, mirroring B3's
  `validate_repro_command` precedent for exactly this class of problem. A new, shared Reviewer
  Blocking-standard condition (mirroring C1's condition 7) independently checks the PR's actual version
  delta against the hop's declared span. Separately, the rule for re-deriving `current_version` before
  re-invoking `dependency-upgrade-review` is now stated explicitly: always from the live manifest, never
  from the stepwise plan's own memory.
- **The `backlog-runner` "cardinality" citation was the wrong precedent, and the stepwise chain doesn't
  fit backlog-runner's actual dependency-ordering mechanism** (SRE). `queue-policy.md`'s real
  dependency gate requires a dependent ticket's content to pre-exist with a declared `dependencies: []`
  field; C2's hop N+1 has no content until hop N merges (its scope comes from a fresh
  `dependency-upgrade-review` invocation against post-hop-N state), so it cannot be pre-registered that
  way. **Fixed**: stated as an explicit scope boundary, not left to drift — a multi-hop chain is never
  dispatched through `backlog-runner`'s automated nightly batch-picking at all; each hop is a direct,
  manual `loop-task-implementer` invocation. This also closes the undisclosed cross-contamination risk
  SRE raised (one hop's `ESCALATED` outcome contributing to backlog-runner's 3-consecutive-escalation
  circuit breaker for unrelated queued tickets).
- **`regression_gate` population had no stated discovery procedure and no check against
  `validate_repro_command`'s actual accepted shapes** (SRE) — the same bug class C1's round-3 fix closed
  for its own domain (a raw `curl` line silently downgraded to the null path). **Fixed**: a stated
  discovery order (Makefile `test` target → `package.json` `scripts.test` → `pytest.ini`/`pyproject.toml`
  → `tox.ini` → CI config), and an explicit rule that a discovered command not matching
  `validate_repro_command`'s real regex (`pytest`/`python3 -m pytest`/`make <target>`/`npm test`/`npm run
  <script>` shapes only) falls back to `regression_gate: null` with the gap disclosed, never asserts a
  command re-verification will reject.
- **`classify_dependency_upgrade`'s exact-string-match never specified the extraction step from the
  report's actual rendered markdown** (SRE) — the real verdict line is `**Verdict: <state>**` (bold
  markers, literal prefix), and one state contains a Unicode em-dash (`"Blocked — insufficient info"`), so
  a naive extraction could silently route a qualifying report to `NOT_QUALIFYING` forever. **Fixed**: the
  function's contract now states the extraction regex explicitly, with the em-dash required as a literal
  in test fixtures.
- **Citation-by-reference discipline was underspecified**: no field in `report-format.md` is literally
  called "mitigation text," so the source column per verdict-driving category was ambiguous (Security
  Architect), and the copy-time Rule-5 re-redaction instruction wasn't restated for the Rollout-risk
  paragraph copied into the same field (Security Architect). **Fixed**: the exact source column per
  category is now named, and re-redaction is stated for every verbatim-copied field, not just the first.
- **The CVE-cutoff caveat, embedded in `acceptance_criteria`, was in the wrong field** (Security
  Architect) — an epistemic disclaimer isn't an actionable, testable criterion and risked being skimmed
  past or misread as "something to fix." **Fixed**: moved to `specialist_inputs` alongside the existing
  `dependency_upgrade_origin: true` marker, a field already meant for non-actionable context.
- **No disclosed residual for "tests still pass" not being evidence against a security-relevant behavior
  change inside the dependency itself** (Security Architect) — unlike C1, which added a bespoke
  security-specific test requirement precisely because generic green tests don't prove a security
  property. **Fixed**: added as an explicit disclosed residual in Failure strategy.
- **No plan/hop traceability marker, and no rejection/abort transition in the stepwise state machine**
  (Software Architect) — "tracked only as a human/Orchestrator-held plan" meant tracked nowhere but
  short-term memory, and only the happy path was modeled. **Fixed**: `specialist_inputs` gains
  `plan_id`/`hop_index`/`expected_current_version`/`expected_target_version`; the state machine gains a
  `PLAN_ABORTED` transition with a stated recovery action.
- **Field-population rigor regressed from C1's bar** (Software Architect) — up to 8 fields were lumped
  into one blanket "unchanged" clause, including `test_framework_hint`, despite `regression_gate`'s own
  population rule needing ecosystem/test-command detection that field exists to carry. **Fixed**:
  `level_hint`, `specialist_inputs`, `test_framework_hint`, and `run_tests` now get individual, concrete
  treatment; `test_framework_hint` carries the discovered test-runner identity.
- **`max_files_per_run: 5`'s justification was a single unsupported sentence** (Software Architect), not
  differentiated by hop size the way C1's final value was differentiated by finding category. **Fixed**:
  stated explicitly why it does NOT need to scale with hop count — the one-major-version-per-hop
  granularity rule already bounds each hop's own footprint, so file-count risk doesn't compound across
  hops, only within one.
- **The Epic-C precedent note never addressed the stepwise-decomposition mechanism's own
  generalizability** (Software Architect) — the ticket's signature new mechanism, left unmentioned
  rather than explicitly scoped. **Fixed**: added an explicit disclaimer, mirroring C1's own "not a
  literal mirror" disclaimer for B8's shape.

Round 2 adversarial review (same three personas, fresh, in parallel, pointed specifically at revision 2's
fixes) confirmed the round-1 central defect's *direction* was right but not yet fully closed, plus found
real secondary gaps. Fixed in **revision 3** (this revision):

- **`verify_dependency_hop_precondition`'s own input — "the extracted pinned version string" — was never
  specified, reopening round 1's exact bug class one layer down** (Security Architect — the central
  finding). A manifest (`package.json`, `requirements.txt`, `Gemfile`, `go.mod`, `Cargo.toml`) typically
  declares a *range*, not an exact version; the real resolved version lives in the *lockfile*, a different
  file per ecosystem. Left unspecified, a sloppy implementation (e.g. reading the manifest's declared
  range instead of the lockfile's resolved pin) could let a drifted hop pass the very check meant to catch
  it. **Fixed**: the extraction contract is now stated explicitly, mirroring `regression_gate`'s own
  discovery-order treatment — read the lockfile (not the manifest) per ecosystem
  (`package-lock.json`/`yarn.lock`/`pnpm-lock.yaml`, `poetry.lock`/`Pipfile.lock`, `Gemfile.lock`, `go.sum`,
  `Cargo.lock`), compare the resolved version by exact string equality, fail closed (`False`) if the
  dependency isn't found there at all.
- **The Reviewer's new Blocking-standard condition was going to collide with C1's own condition 7, which
  is already real and merged** (confirmed directly against `origin/main`'s `workflow/reviewer.md`: C1's
  condition 7 — a task whose `scope`/`acceptance_criteria` describes contacting, authenticating against,
  or modifying a live external credential/identity/secrets-management system, a backstop for
  `classify_security_finding` — landed via PR #320, not a future collision, an already-wrong number).
  **Fixed**: renumbered to **condition 8** throughout, with its own evidence-prefix convention
  (`"dependency_hop: "`, mirroring condition 6's `"regression_gate: "` convention) stated explicitly, and
  the same lockfile-based version-delta computation the Builder-side check uses, so both checks apply the
  identical extraction rule rather than two independently-guessable ones.
- **`specialist_inputs.plan_id` collides in name with an existing, different, code-tracked `plan_id`
  concept already load-bearing in this same skill** (Software Architect — `plan_execution_state.plan_id`/
  `task.plan_context.plan_id` in `reference/state-schema.yaml`, derived via
  `scripts/implementation_plan.py`'s `derive_plan_id`, consumed by `execution_branch_name()` for real git
  branch naming). A human or future tool could easily conflate the two. **Fixed**: renamed to
  `dependency_chain_id` everywhere in this design.
- **`dependency_chain_id`'s hashing scheme used naive concatenation instead of this codebase's own
  established namespaced-digest convention** (Software Architect — `canonical_payload_digest()`/
  `source_digest_bundle()` already exist precisely to avoid the ambiguity raw concatenation introduces).
  **Fixed**: now hashes a structured, namespaced payload via the same existing helper, truncated to 16 hex
  characters (mirroring `derive_plan_id`'s own truncation convention, distinguishable at a glance from that
  function's 8-character truncation).
- **Two citation-grounding nits against the real `report-format.md`** (Security Architect, Software
  Architect, independently convergent on both): the CVE table has no `Source` column at all (nothing to
  avoid citing — the instruction was correct in effect but imprecise in its reasoning), and the carried-
  forward CVE-caveat text dropped a parenthetical clause present in the real source
  (`"...not a live database (this skill has no CVE/advisory MCP or external lookup), and may miss..."`).
  **Fixed**: both corrected to match the real file exactly.
- **`max_files_per_run: 5`'s round-2 justification proved hop-count-invariance but never answered
  absolute sufficiency across dependencies of very different footprint size** (Software Architect) — a
  major-version bump of a large, central framework vs. a small utility library are both "one hop," but not
  comparable in blast radius, and `workflow/builder.md` has no documented overflow-handling convention for
  this field at all (an inherited gap from C1, not newly introduced). **Fixed**: reframed honestly as a
  disclosed residual rather than a fully-closed question — see Open questions.
- **The Builder-side insertion point ("existing pre-implementation step") doesn't name a real section** —
  `workflow/builder.md`'s actual structure has no such step (Security Architect, Software Architect, SRE —
  all three independently flagged this). **Fixed**: pinned precisely to a new named sub-section at the
  very top of the real `## 1. Understand before changing code`, mirroring B7's own precise
  insertion-point precedent.
- **`PLAN_ABORTED` retry bookkeeping was unspecified** (Software Architect) — whether a retried hop
  reuses or increments `hop_index` was never stated, risking two different `task_id`s under the same
  `hop_index`. **Fixed**: stated explicitly — a retry of an aborted hop reuses the same `hop_index`; only
  a successfully merged hop advances it.
- **The "current_version re-derivation" rule was mischaracterized as code-enforced in the Consistency
  table** (SRE) — it's a human/Orchestrator-applied convention, same category as hop ordering; it's
  backstopped by the two real code checks (a stale re-derivation still gets caught at Builder dispatch),
  but mislabeling it "Strong, code-enforced" was its own small overclaim. **Fixed**: reworded to state the
  convention/backstop relationship accurately.
- **No stated confirmation that a hop task files no tracker/issue entry** (SRE) — left implicit, inferred
  only by analogy to C1's own silence on the same point. **Fixed**: stated as one explicit sentence.

Both round-1 personas who re-checked round-2 fixes against the real repository independently confirmed
the remaining items (classify_dependency_upgrade's extraction regex, `regression_gate` discovery order,
the `backlog-runner` scope boundary, the test-pass-insufficient residual, field-by-field rigor, the
Epic-C precedent scoping) hold up as specified — not re-litigated here.

A narrow confirmation pass (all three personas in sequence, one agent — not a full fresh round, since
round 2's remaining items were concrete, specifiable corrections rather than open questions) verified all
7 of revision 3's fixes against the real repository and closed 6 outright. **Revision 4** (this revision)
closes the 7th and two cosmetic nits the pass also found: `verify_dependency_hop_precondition`'s
extraction contract didn't cover a non-lockfile exact-pin manifest (e.g. bare `requirements.txt`) or a
monorepo/multi-manifest repo — **fixed** with a stated fallback rule for the exact-pin case, and the
remaining gap (monorepo disambiguation, ecosystems beyond the five listed) honestly disclosed as a new
Open question rather than silently left unaddressed; C1's condition 7 was mischaracterized as a
"rotation-detection clause" (**fixed**, now cites its real text — a live-credential-system scope check
backstopping `classify_security_finding`); `specialist_inputs` was miscounted as five fields when it lists
six (**fixed**).

The second of eight Epic-C "analysis skill → executor" tickets — reuses C1's own just-converged pattern
(legacy-envelope bypass, a real tested classification function, an independent downstream Reviewer
backstop) wherever it applies unmodified, and now backs its one genuinely new piece — a stepwise,
sequentially-dependent multi-task decomposition for a large version gap — with a real, code-enforced
ground-truth precondition check (applied consistently by both the Builder and the Reviewer), not just a
disclosed convention.

## Components

| Component | Responsibility | Boundary / owns | Notes |
|-----------|-----------------|------------------|-------|
| New `cross-skill-escalation.md` row pair (forward 4-column, reverse 3-column) | Declares the handoff: a qualifying `dependency_upgrade_report` → `loop-task-implementer` | Documentation only | Mirrors C1's own just-merged `security-review → loop-task-implementer` row pair exactly |
| New reference doc: `docs/skill-framework/shared/dependency-upgrade-handoff.md` | Holds the selection rule, `classify_dependency_upgrade`'s contract, the envelope-population mapping, the stepwise-decomposition rule, and the CVE-caveat/rollback-note carry-forward text | Linked from the new escalation row, mirroring C1's own `security-review-handoff.md` convention and its real relative-link syntax | Same file-naming/location convention as C1's precedent |
| `classify_dependency_upgrade(verdict: str) -> Literal["QUALIFYING", "NOT_QUALIFYING"]` (new, real, tested function) | A simple, closed-vocabulary classification — no NLP-style heuristic needed, since the input is already a clean 4-state enum, unlike C1's own free-text `Recommendation` column | Lives at `skills/loop-task-implementer/scripts/classify_dependency_upgrade.py`, mirroring C1's exact file-location convention | `QUALIFYING` for `"Safe to upgrade"`/`"Upgrade with mitigations"`; `NOT_QUALIFYING` for `"Do not upgrade yet"`/`"Blocked — insufficient info"`/any unrecognized string (fail-closed) |
| Stepwise-decomposition rule (new — the one genuinely new mechanism this ticket needs) | Decides how a large version gap splits into sequential, single-hop steps, and how step N+1 only gets authored after step N's own PR has actually merged | Documented in the new reference doc; the hop *ordering* is a human/Orchestrator-applied convention, but the hop *precondition* is now code-enforced (see below) | Closes architecture-review Condition 1 concretely — see below |
| `verify_dependency_hop_precondition(manifest_pinned_version: str, expected_current_version: str) -> bool` (new, real, tested function — the second piece of real code this ticket adds) | Builder-side bootstrap check, run before any upgrade work begins: reads the dependency's actual **resolved, lockfile-pinned** version for `dependency_name` and compares it to the task's own `specialist_inputs.expected_current_version`. `False` → Builder stops immediately, reports `BLOCKED` with the mismatch as evidence, never attempts the upgrade | Lives at `skills/loop-task-implementer/scripts/verify_dependency_hop_precondition.py`, invoked from a new named sub-section at the very top of `workflow/builder.md`'s real `## 1. Understand before changing code` step (round-3 fix, pinned to the actual section — see Rollout) | Converts revision 1's disclosed-but-unenforced "git-state would visibly mismatch" claim into an actual, cited, code-backed gate, closing Security Architect's round-1 Finding 1(a) |
| `verify_dependency_hop_precondition`'s extraction contract (round-3 fix, Security Architect finding; round-4 fallback addition, same finding, narrow residual) | `manifest_pinned_version` is **never** read from the manifest's own declared range (e.g. `package.json`'s `^2.1.0`) — manifests typically declare a range, not an exact version. It is read from the ecosystem's real **lockfile**: `package-lock.json`/`yarn.lock`/`pnpm-lock.yaml` (npm/yarn/pnpm), `poetry.lock`/`Pipfile.lock` (Python), `Gemfile.lock` (Ruby), `go.sum` (Go), `Cargo.lock` (Rust) — the resolved, exact version for `dependency_name`, compared by exact string equality. **Fallback (round-4 addition)**: when no ecosystem lockfile exists at all, and the manifest itself declares an exact pin with no range operator (e.g. a bare `requirements.txt` line with `==`, no `^`/`~`/`>=`), treat that exact pin as the resolved version. Any other case — no lockfile and no exact-pin manifest, a dependency absent from wherever is checked, or a monorepo/workspace with multiple manifests and no stated disambiguation rule — fails closed (`False`), same as any other mismatch; this degrades the precondition check to "never passes" for that repo shape rather than silently passing, safe but incomplete, disclosed as an Open question rather than solved here | Whoever implements the Builder-side invocation | Mirrors `regression_gate`'s own ecosystem-discovery treatment — the same rigor, applied to the field this round's central finding depends on. Ecosystems beyond the five listed (PHP/`composer.lock`, Java/Gradle, .NET/`packages.lock.json`, Elixir/`mix.lock`, etc.) are covered by the same fail-closed default, not individually enumerated |
| New Reviewer Blocking-standard **condition 8** (round-3 fix: renumbered — confirmed directly against `origin/main`'s `workflow/reviewer.md` that condition 7 is already real, landed by C1/PR #320, so this cannot reuse that slot) | For any task whose `specialist_inputs.dependency_upgrade_origin` is `true`, the PR's actual dependency-manifest version delta must exactly match `expected_current_version → expected_target_version`, computed from the same lockfile-based extraction rule as the Builder-side check (round-3 fix: stated explicitly, so both checks apply one rule, not two independently-guessable ones); any other delta is blocking regardless of passing tests. Evidence-prefix convention (round-3 fix, mirrors condition 6's `"regression_gate: "`): a finding raised under condition 8 must have its `evidence` field begin with the literal prefix `"dependency_hop: "` | Added to `workflow/reviewer.md`'s shared Blocking standard (no change to the finding output schema itself, same as C1's condition 7) | Independent second check — not a replacement for the Builder-side bootstrap check, a backstop if that check is bypassed or its own code has a bug |
| The envelope population rule (documented in the new reference doc) | Maps a qualifying upgrade (one step) into the real, existing legacy `implementation_task` envelope, mirroring C1's own field-by-field mapping shape | Reuses C1's and B6's "legacy bypass, cite the real 16 fields" precedent | See Data model |

**Confirmed untouched**: `workflow/lifecycle-gate.md`, `scripts/validate_loop_lifecycle.py`,
`reference/state-schema.yaml`, `scripts/registry/composition_contracts.yaml`, `skills.yaml` — this
handoff's mechanism is two new, small, tested functions plus documentation/convention changes and one
shared Blocking-standard condition, the same shape and scale as C1. `workflow/builder.md` gets one new,
small pre-implementation step (invoking `verify_dependency_hop_precondition`); `workflow/reviewer.md` gets
one new Blocking-standard condition — both tracked in Rollout, neither a new workflow phase.

**`workflow/orchestrator.md` is confirmed untouched, and `backlog-runner` is confirmed NOT the dispatch
path for a multi-hop chain** (resolved in revision 2, replacing revision 1's incorrect
cardinality-only citation): `backlog-runner`'s real dependency-ordering mechanism
(`reference/queue-policy.md` §2 rules 3-4) requires a dependent ticket's content — and a declared
`dependencies: []` pointing at a known prior `task_id` — to exist up front, so it can be pulled, deferred,
and re-checked against confirmed-merge state night over night. C2's hop N+1 has no content until hop N's
PR actually merges (its `scope`/`acceptance_criteria` come from a *fresh* `dependency-upgrade-review`
invocation against the post-hop-N manifest state), so there is no ticket to pre-register that dependency
on — the two mechanisms are shaped for different problems, and forcing a fit would be the same kind of
overclaim C1's round-1 made elsewhere. **Explicit scope boundary**: a multi-hop stepwise chain is never
submitted to `backlog-runner`'s automated nightly batch-picking as a pre-declared chain. Each hop is
authored and dispatched as a direct, standalone `loop-task-implementer` invocation once its own fresh
`dependency-upgrade-review` verdict is in hand; nothing new needs to be added to `orchestrator.md` for
this handoff, and `backlog-runner`'s own queue-policy/circuit-breaker machinery is simply not engaged by a
stepwise chain, closing the cross-contamination risk a chain hop's `ESCALATED` outcome would otherwise
pose to unrelated queued tickets.

## APIs

| Field / function | Contract | Consumer(s) | Notes |
|--------------------------|----------|-------------|-------|
| New forward row | `"A dependency upgrade has a Safe-to-upgrade or Upgrade-with-mitigations verdict (per classify_dependency_upgrade — see [dependency-upgrade-handoff.md](dependency-upgrade-handoff.md))"` \| `dependency-upgrade-review → loop-task-implementer` \| `dependency_upgrade_report` (dependency name, version hop, verdict, mitigation text, rollout-risk citation) \| `"Upgrade {dependency} from {current_version} to {target_version} per dependency-upgrade-review's own mitigations"` | Whoever authors the handoff | Mirrors C1's forward row exactly |
| New reverse row | `"dependency-upgrade-review confirms a Safe-to-upgrade or Upgrade-with-mitigations verdict for one version hop"` \| `loop-task-implementer receives the dependency, version hop, verdict, and mitigation/rollback citations` \| `"Upgrade {dependency} from {current_version} to {target_version} per dependency-upgrade-review's own mitigations"` | Whoever authors the handoff | Mirrors C1's reverse row, skill-as-subject phrasing |
| `classify_dependency_upgrade(verdict: str) -> Literal["QUALIFYING", "NOT_QUALIFYING"]` | Pure function, no I/O, no network, no file access. Exact string match against the real report format's own 4-state vocabulary (`"Safe to upgrade"`, `"Upgrade with mitigations"`, `"Do not upgrade yet"`, `"Blocked — insufficient info"`). `QUALIFYING` only for the first two; everything else — including the two non-qualifying real states AND any string that doesn't match any of the four at all (a malformed/future/unrecognized verdict) — is `NOT_QUALIFYING` | Whoever authors the handoff | A simple closed-vocabulary check is genuinely sufficient here — confirmed no NLP-style heuristic is needed, since (unlike C1's free-text `Recommendation` column) the input is already a clean, fixed enum the upstream report's own format spec already enforces |
| `classify_dependency_upgrade`'s extraction step (round-2 fix, SRE finding) | The function's actual input is never a bare string — `report-format.md`'s real verdict line renders as `**Verdict: <state>**` (literal bold markers and prefix). Extraction regex, stated explicitly: `^\*\*Verdict:\s*(.+?)\*\*$`, capture group 1 fed to the exact-match check. One of the four canonical states contains a Unicode em-dash (`"Blocked — insufficient info"`, U+2014) — test fixtures must use the literal em-dash, not a hyphen, or that state silently never matches | Whoever authors the handoff | Closes the same bug class as C1's round-3 `validate_repro_command` fix: a function's exact-match contract is only as good as its never-before-specified extraction step |
| `verify_dependency_hop_precondition(manifest_pinned_version: str, expected_current_version: str) -> bool` | Pure function, no I/O itself — the caller (Builder) reads the lockfile per the stated per-ecosystem extraction contract (see APIs table) and passes the resolved version string in. `True` only on exact match; any mismatch (including the dependency missing from the lockfile entirely) is `False` | Builder, at the new named sub-section in `## 1. Understand before changing code` | Fail-closed: a `False` result stops the task before any upgrade code is written, never proceeds on ambiguity |

## Events

None — same reasoning as C1: no new run-log event, no network, no state. The classification function is
pure and local.

## Data model

| Entity | Key fields | Relationships | Owner |
|--------|-----------|-----------------|-------|
| Legacy `implementation_task` envelope (reused, all 16 real fields addressed individually — round-2 fix, no blanket clause beyond the 3 genuinely generic fields) | See the field-by-field table below | None of these fields ever carry raw, un-redacted `changelog_text`/`manifest_excerpt` excerpts | Whoever authors the handoff |
| Stepwise plan (NOT a new typed entity — no new schema, but now carries a lightweight traceability marker, round-2 fix) | A sequence of `(current_version, next_version)` hops, one major version at a time for a semver-following package (the concrete, simple rule: if `target_version`'s major differs from `current_version`'s major by more than one, the first step targets `current_version`'s next major only, not `target_version` directly) | Tracked as a human/Orchestrator-held plan across multiple separate invocations of this handoff, now identifiable across hops via `specialist_inputs.dependency_chain_id`/`hop_index` (see below) — still never a code-level dependency graph | Human/Orchestrator |

**Field-by-field mapping** (round-2 fix — matches C1's final-revision rigor, no field left to a blanket
"unchanged" clause beyond the 3 genuinely domain-agnostic ones):

- `task_id` — generated per existing convention.
- `scope` — `"{dependency_name} {current_version} → {target_version}"`, one step only, never a multi-hop
  span.
- `acceptance_criteria` — built from named source columns only (round-2 fix, closes the citation
  ambiguity): for a `Breaking changes`-driven mitigation, the table's own `Impact` column; for an `API
  differences`-driven mitigation, the table's own `Caller action` column; for a CVE-driven `Upgrade with
  mitigations` verdict, the mitigation is the upgrade itself — cite the CVE identifier plus the target
  version (round-3 correction: the real CVE table — `CVE | Affects | Fixed in | Severity` — has no
  `Source` column at all, so there is nothing to avoid citing there; the actual rule is simply "cite the
  CVE ID and target version, never the Notes section's own free-text caveat"). The Breaking-changes
  table's own `Source` column, which can quote `changelog_text` directly, is **never** the source for
  this field. Every value copied in is re-redacted per Rule 5 at copy time — explicitly
  restated here for the Rollout-risk paragraph too (round-2 fix: revision 1 only stated this for the
  mitigation text, but `report-format.md` itself instructs the Rollout-risk paragraph to cite the same
  untrusted `manifest_excerpt`/`changelog_text` evidence, so it needs the identical re-redaction, not an
  implied inheritance), PLUS the report's own `Rollout risk` paragraph cited as the required rollback
  note. The CVE-training-cutoff caveat is **no longer here** (round-2 fix, see `specialist_inputs` below).
- `request` — synthesized trigger phrase.
- `repo_root`/`target` — the manifest/lockfile path from the report's own evidence.
- `level_hint` — same default as any legacy-envelope task (round-2: stated individually, not folded into
  a blanket clause, matching C1's own per-field treatment).
- `specialist_inputs` — now carries six fields, individually justified (round-2 fix; round-4 fix:
  corrected count): `dependency_upgrade_origin:
  true` (unchanged, the origin marker); `cve_training_cutoff_caveat` — the literal standing-disclosure
  text (see below), moved out of `acceptance_criteria` because an epistemic disclaimer isn't an
  actionable, testable criterion (round-2 fix, Security Architect finding); `dependency_chain_id`
  (round-3 rename, Software Architect finding: the name `plan_id` collided with the existing, different,
  code-tracked `plan_execution_state.plan_id`/`task.plan_context.plan_id` already load-bearing in this
  same skill at `reference/state-schema.yaml`, derived via `scripts/implementation_plan.py`'s
  `derive_plan_id`) — a stable identifier for the whole stepwise chain, computed once when the plan is
  first decided as `canonical_payload_digest({"dependency_name": ..., "original_current_version": ...,
  "final_target_version": ...})[:16]` (round-3 fix: reuses the codebase's own existing namespaced-digest
  helper instead of raw string concatenation, avoiding the ambiguity that helper exists to prevent;
  truncated to 16 hex characters, distinct from `derive_plan_id`'s own 8-character truncation so the two
  are visually distinguishable), so a human reading any one hop's task can tell it's part of a larger
  chain and find the others; `hop_index` — this hop's 1-based position in the chain, reused (not
  incremented) on a retry of an aborted hop (round-3 fix, see State machines); `expected_current_version`/
  `expected_target_version` — this hop's own machine-readable start/end versions, the exact values
  `verify_dependency_hop_precondition` and the new Reviewer Blocking-standard condition 8 check against
  (round-2 fix, closes Software Architect's no-traceability-marker finding and backs the new
  code-enforced precondition check). **No tracker/issue entry is filed for a hop task** (round-3 fix, SRE
  finding, stated explicitly rather than left implicit): consistent with the whole legacy-envelope-bypass
  family (C1 included), this is ad-hoc, no-tracker-entry dispatch by construction.
- `test_framework_hint` — the test-runner identity discovered for `regression_gate` (see below), not a
  generic unchanged default (round-2 fix: revision 1 declared this "unchanged" while simultaneously
  needing ecosystem detection for `regression_gate` — an internal inconsistency Software Architect
  caught).
- `run_tests` — `true` (round-2: stated individually) — "each PR keeps tests green" is enforced by this
  skill's own existing, unmodified completion-gate discipline, not a new mechanism.
- `deadline`/`session_token_budget`/`output_dir` — same defaults as any legacy-envelope task, unchanged
  (the 3 fields genuinely generic enough for a blanket clause, matching C1's own final convention).
- `app_run` — same default as any legacy-envelope task, unchanged (confirmed real at
  `composition_contracts.yaml` on `origin/main`, 16th field, landed via B7/PR #318).
- `max_files_per_run` — a concrete absolute value of **5**. Justification (round-2 fix, Software
  Architect finding): this does **not** need to scale with hop count, because the
  one-major-version-per-hop granularity rule (Data model, Stepwise plan row) already bounds each hop's own
  footprint to a single major-version jump — file-count risk doesn't compound across hops, only within
  one hop, and 5 is set for that single-hop case (plausibly broader call-site footprint than a single
  security finding, hence higher than C1's 2–3). **Disclosed residual, not fully closed (round-3 fix,
  Software Architect finding)**: hop-count-invariance and absolute sufficiency are different claims, and
  only the first is defended here — a single major-version hop for a large, central, actively-maintained
  framework could plausibly exceed 5 files, while a hop for a small utility library may need far fewer;
  `workflow/builder.md` has no documented overflow-handling convention for `max_files_per_run` at all
  (an inherited gap from C1, not newly introduced by this ticket). Left as an honest Open question rather
  than claimed solved.
- `regression_gate` — populated via a stated discovery order (round-2 fix, closes SRE's under-specified-
  discovery finding): check, in order, the repo's `Makefile` for a `test` target, `package.json`'s
  `scripts.test`, `pytest.ini`/`pyproject.toml`'s test configuration, `tox.ini`, then CI config for an
  explicit test-invocation line. The discovered command is only used if it matches
  `skills/bug-diagnosis/tests/test_repro_command_validation.py`'s real `validate_repro_command` shape
  (`pytest`/`python3 -m pytest`/`make <target>`/`npm test`/`npm run <script>` only) — for a repo whose
  real test command doesn't fit that shape (`tox`, `go test`, `cargo test`, `bundle exec rspec`,
  `./gradlew test`), `regression_gate` falls back to `null` with the gap disclosed, mirroring C1's own
  honest null-path treatment, never asserting a command re-verification will reject.

**Literal CVE-caveat carry-forward text** (quoted verbatim from the report's own real standing disclosure,
closing architecture-review Condition 3, now carried in `specialist_inputs.cve_training_cutoff_caveat`
rather than `acceptance_criteria` — round-2 fix): *"CVE findings are reasoned from the model's
training-time knowledge of public advisories, not a live database (this skill has no CVE/advisory MCP or
external lookup), and may miss advisories disclosed after the training cutoff or for very recent
releases."* (round-3 correction, Security Architect and Software Architect, independently convergent:
revision 2's quoted text dropped the parenthetical clause present in the real source — this is the exact
copy-paste text, not a paraphrase, since it becomes the literal field value).

## State machines

| Entity | States | Transitions | Notes |
|--------|--------|-------------|-------|
| One version-hop step | `NOT_QUALIFYING` (verdict is `Do not upgrade yet`/`Blocked`/unrecognized) → terminal, report-only; `QUALIFYING` → an `implementation_task` is authored for THIS ONE HOP ONLY, then proceeds through the Builder/Reviewer/lifecycle-gate pipeline, now with two additions: the Builder's new `verify_dependency_hop_precondition` bootstrap check (runs first, before any upgrade code is written) and the Reviewer's new version-delta Blocking-standard condition (runs as part of the existing diff review) | Classification happens once per hop, from that hop's own `dependency_upgrade_report` | Unlike C1, there is no merge-group concept here — each hop is always its own, single task |
| The stepwise plan across multiple hops | `PLANNED` (a human/Orchestrator has decided the hop sequence) → `HOP_N_DISPATCHED` → `HOP_N_MERGED` → `HOP_N+1_DISPATCHED` (re-invoking `dependency-upgrade-review` with `current_version` re-derived from the live manifest at the current repo head, never carried forward from the plan's own memory — round-2 fix) → ... → `PLAN_COMPLETE`, OR → `PLAN_ABORTED` (round-2 fix, new transition, closes Software Architect's no-rejection-path finding) | Hop ordering itself remains **convention-level, human/Orchestrator-applied — not code-enforced** (closes architecture-review Condition 4; this design does not repeat C1's round-1/round-2 overclaim). What changed in round 2: the hop *precondition* — whether hop N+1 is being authored against the correct, actual starting state — is now code-enforced twice (Builder bootstrap check, Reviewer Blocking-standard condition), so a premature or mis-ordered hop fails loudly and early rather than silently executing an unintended larger jump. `PLAN_ABORTED`: triggered when a hop's task is `NOT_QUALIFYING`, escalates, or trips a circuit breaker — recovery is an explicit human decision (retry that hop via a fresh `dependency-upgrade-review` invocation, or stop the chain entirely); never a silent/automatic retry. **Retry bookkeeping (round-3 fix, Software Architect finding)**: a retried hop reuses the same `hop_index` — it is still logically the same hop, just a new `task_id` — only a successfully merged hop advances `hop_index` to the next value | `specialist_inputs.dependency_chain_id`/`hop_index` give the plan an identifiable thread across hops (round-2 fix) — still not a code-level dependency graph, just a traceable marker a human can follow |

## Consistency

| Boundary | Model (strong / eventual) | Why |
|----------|-----------------------------|-----|
| Stepwise plan ordering (when to author the next hop) | **Convention-level, human/Orchestrator-applied — not code-enforced** (explicit, honest statement per Condition 4) | Matches the exact honesty discipline C1's own round-3 fix established for its own merge rule — this design does not repeat C1's round-1/round-2 overclaim mistake |
| Stepwise plan precondition (is the next hop's starting state actually real) | **Strong, code-enforced at the two points that matter** (round-2 fix) — `verify_dependency_hop_precondition` at Builder dispatch and the Reviewer's new Blocking-standard condition 8 at review time, both against the lockfile's actual resolved version (round-3 fix, see APIs). "Re-derive `current_version` from the live manifest before re-invoking `dependency-upgrade-review`" itself is **convention-level, not code-enforced** (round-3 correction, SRE finding — revision 2 overstated this one clause as code-enforced): it is backstopped, not replaced, by the two real checks — a forgotten re-derivation either harmlessly matches reality or gets caught at Builder dispatch, never silently proceeds | Two independent, code-backed checkpoints plus one backstopped convention, closing Security Architect's and SRE's round-1 central finding without overclaiming the convention itself is enforced |
| One hop's own classification vs. a later hop's classification | Independent — each hop gets its own fresh `dependency-upgrade-review` invocation and its own fresh verdict; a later hop is NEVER assumed safe because an earlier hop was | Prevents a stale, compounding safety assumption across a multi-hop chain |

## Retries & idempotency

| Operation | Idempotent? | Retry / backoff strategy |
|-----------|-------------|----------------------------|
| `classify_dependency_upgrade` | Yes — pure function, no I/O | N/A, deterministic |
| Authoring an `implementation_task` for one hop | Not automated in the usual sense | N/A — one-time, human-or-Orchestrator-authored action per hop |

## Capacity

| Dimension | Estimate | Basis |
|-----------|----------|-------|
| Hops per stepwise plan | Unbounded in principle, but each hop is independently gated (its own fresh classification, plus the new code-enforced precondition check) — no compounding safety risk from a long chain, just compounding time/review/human-attention cost, which is a real but disclosed operability cost (see Operability and Failure strategy), not a safety concern | One major version per hop is the concrete rule; a 5-major-version gap is 5 independent, fully-reviewed hops, not 5 blindly-chained ones. Dispatched as direct `loop-task-implementer` invocations, never through `backlog-runner`'s nightly batch (round-2 fix) — so a long chain never risks tripping that skill's own unrelated-ticket circuit breakers |
| `max_files_per_run` | 5 (concrete value, higher than C1's 2–3) | Does not need to scale with hop count (round-2 fix, stated explicitly): the one-major-version-per-hop rule already bounds each hop's own footprint, so 5 is sized for a single major-version jump's call-site footprint, plausibly broader than a single security finding's |

## Failure strategy

| Failure mode | Degradation / mitigation |
|--------------|-----------------------------|
| `classify_dependency_upgrade` receives an unrecognized verdict string (e.g. a future report-format change adds a 5th state) | Fails toward `NOT_QUALIFYING` — never assumes an unknown state is safe |
| Hop N+1 is authored before hop N's PR actually merged, or against a stale `current_version` | Code-prevented, round-2 fix: `verify_dependency_hop_precondition` aborts the Builder's task before any upgrade work if the manifest's actual pinned version doesn't match `expected_current_version`; the Reviewer's new Blocking-standard condition independently re-checks the PR's actual version delta. Ordering itself (when a human/Orchestrator chooses to author the next hop) stays a disclosed convention — only the *precondition* is now enforced |
| A transitive-dependency conflict is flagged in the report | Surfaced as report information only — explicitly never auto-escalated into its own recursive upgrade task (closes architecture-review Condition 5) |
| The CVE-training-cutoff caveat is forgotten once reduced to a QUALIFYING/NOT_QUALIFYING bit | Prevented by construction — the caveat's literal text is a required field in the envelope-population mapping (`specialist_inputs.cve_training_cutoff_caveat`, round-2: moved from `acceptance_criteria` to a field meant for non-actionable context), not an optional add-on a human might skip |
| **(Round-2 addition, Security Architect finding)** The upgrade's own existing test suite passes, but the dependency's internal behavior changed in a security-relevant way the app's tests never exercised (a changed default, a loosened validation, a new deserialization path) | **Disclosed residual, not mitigated by this design**: `run_tests: true`/`regression_gate` prove the app's own behavior is unchanged where tests already look, not that the dependency's own security posture is unchanged where they don't. No bespoke negative-test requirement is added here (unlike C1's domain, where the vulnerability category is known upfront); `dependency-upgrade-review`'s own report is the disclosed, upstream mitigation for this risk, not this handoff |
| **(Round-2 addition, SRE finding)** A long stepwise chain stalls because the human forgets to continue it — no code-visible artifact tracks "where the chain is" beyond `specialist_inputs.dependency_chain_id`/`hop_index` on the last-dispatched hop's own task | Disclosed residual — a genuine human-attention-budget risk, not a safety risk (silent abandonment, not silent corruption). No automated reminder/tracking is added in this revision (see Open questions) |

## Observability

| Signal | What's measured |
|--------|-------------------|
| None new | Same reasoning as C1 — the resulting task's own existing completion/review lifecycle is the only observable surface |

## Rollout plan

| Phase | Scope | Feature flag / migration order |
|-------|-------|----------------------------------|
| 1 | New forward + reverse `cross-skill-escalation.md` rows, linking to the new reference doc | Documentation only |
| 2 | New `classify_dependency_upgrade` function at `skills/loop-task-implementer/scripts/classify_dependency_upgrade.py` (with the round-2 extraction-regex fix), with real unit tests including the em-dash literal fixture | New, tested code |
| 3 | New `verify_dependency_hop_precondition` function at `skills/loop-task-implementer/scripts/verify_dependency_hop_precondition.py`, with real unit tests (match/mismatch/missing-from-lockfile cases per the round-3 per-ecosystem lockfile extraction contract) (round-2 addition, round-3 extraction-contract fix) | New, tested code — the hop-precondition gate |
| 4 | `workflow/builder.md` gains a new named sub-section at the top of `## 1. Understand before changing code` invoking `verify_dependency_hop_precondition` when `specialist_inputs.dependency_upgrade_origin` is `true` (round-3 fix: pinned to the real section name); `workflow/reviewer.md` gains the new shared Blocking-standard **condition 8** with its `"dependency_hop: "` evidence-prefix convention (round-3 fix: renumbered from a conflicting "condition 7") | Small, additive workflow-doc changes |
| 5 | New `dependency-upgrade-handoff.md` reference doc: selection rule, envelope-population mapping (field-by-field, round-2 fix), stepwise-decomposition rule (ordering stays convention-level; precondition is code-enforced, round-2 fix), CVE-caveat/rollback-note carry-forward text, `regression_gate` discovery order | Documentation only |
| 6 | **Precedent note for Epic C** (round-2 fix, now explicit about the stepwise mechanism): the matrix-row format, legacy-envelope-bypass convention, and real-tested-classification-function pattern generalize to C3-C8; the specific 4-state-to-2-state mapping, the one-major-version-per-hop rule, and the `max_files_per_run: 5` value are C2-specific. **The stepwise/multi-hop decomposition pattern itself (content-dependent chaining, a code-enforced ground-truth precondition check, dispatch bypassing `backlog-runner`'s batch model) is a candidate pattern for any future Epic-C ticket whose verdict can require sequential, content-dependent steps — but it is this design's first instance, unvalidated, and explicitly NOT assumed to apply uniformly** (round-2 addition, mirrors C1's own "not a literal mirror of B8's shape" disclaimer); future tickets should evaluate their own need for it on its own merits | Documentation only |
| 7 | First real dry-run | **Open question** — see below |

## Open questions

1. **No concrete validation target exists in this session's own immediate work** — mirrors C1/B7/B8's own
   honest disclosure.
2. **The one-major-version-per-hop rule is a simple, conservative default, not validated against every
   real-world package's own versioning convention** — some ecosystems (e.g. packages that don't strictly
   follow semver, or that bundle many breaking changes into minor releases) might need a different hop
   granularity; left for real usage to reveal.
3. **Whether `dependency-upgrade-review`'s own report format should eventually gain an explicit
   `suggested_next_hop` field (rather than this design's own human/Orchestrator-derived hop rule) is a
   reasonable future improvement, out of scope for this ticket.**
4. **The stepwise plan's own hop *ordering* remains convention-level (not code-enforced) — only the hop
   *precondition* is code-enforced as of revision 2.** A careless human/Orchestrator could still choose
   never to author hop N+1 at all (chain abandonment, see Failure strategy) or could re-attempt an already
   `PLAN_ABORTED` chain without a fresh decision; no code prevents either, by design (these are human
   judgment calls, not safety properties).
5. **No automated tracking or reminder exists for a long-running, multi-day stepwise chain** (round-2
   addition, SRE finding) — `dependency_chain_id`/`hop_index` make a chain identifiable when found, but nothing
   surfaces an abandoned chain proactively; left as a disclosed residual, not solved here.
6. **"Tests still pass" is not validated evidence against a security-relevant behavior change inside the
   upgraded dependency itself** (round-2 addition, Security Architect finding) — disclosed in Failure
   strategy, not mitigated by any new mechanism in this ticket; `dependency-upgrade-review`'s own upstream
   analysis is the only disclosed safeguard against this class of risk.
7. **`max_files_per_run: 5` is hop-count-invariant but not validated as absolutely sufficient across
   dependencies of very different footprint size** (round-3 addition, Software Architect finding) — a
   major-version bump of a large, central framework could plausibly exceed 5 files where a small utility
   library's own hop wouldn't; `workflow/builder.md` has no documented overflow-handling convention for
   this field today (inherited from C1, not introduced here). Left for real usage to reveal whether 5
   needs to become a report-evidence-informed range rather than one fixed constant.
8. **`verify_dependency_hop_precondition`'s extraction contract doesn't cover every repo shape**
   (round-4 addition, narrow confirmation-pass finding) — a non-lockfile exact-pin manifest has a stated
   fallback, but a monorepo/workspace repo with multiple manifests, and any ecosystem outside the five
   explicitly listed, both fall back to fail-closed with no disambiguation rule. Safe (the check simply
   never passes for that shape, never silently passes incorrectly), but incomplete — left for real usage
   to reveal which additional shapes need an explicit rule.
