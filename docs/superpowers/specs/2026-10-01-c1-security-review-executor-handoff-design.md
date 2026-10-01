# System Design Spec — C1: security-review → executor handoff

**Readiness: Ready with open questions**

## Revision history

**Revision 1** (initial): a near-zero-code design — a new `cross-skill-escalation.md` row, a one-sentence
Lens A extension, and a prose-only "rotation-detection rule" and "selection bar" documented in the row's
own notes, claimed to make rotation-requiring findings "structurally impossible" to convert into an
autonomous task.

Round 1 adversarial review (Security Architect, SRE, Software Architect — all three, fresh, in parallel)
converged hard on one central contradiction, found independently from two different angles, plus three
more real gaps from SRE. Fixed in **revision 2** (this revision):

- **"Structural impossibility" was false — this was a documented convention with zero code enforcement,
  and the design simultaneously claimed "near-zero new code"** (Security Architect AND Software
  Architect, independently convergent — the central finding). Nothing in `composition_contracts.yaml`'s
  real, untyped `implementation_task` fields, nor anywhere else in the repository, stops a human or
  Orchestrator from hand-authoring a rotation-shaped task anyway. The design asserted a property the
  artifact didn't provide. **Fixed**: the classification (qualifying / rotation-required / not-qualifying)
  is now a real, tested Python function (`classify_security_finding`), not prose a reader applies by eye
  — closing the "near-zero-code vs. structural impossibility" contradiction by making the gate real code,
  mirroring B3's own `validate_repro_command` precedent for exactly this class of problem (a
  safety-critical classification that shouldn't be left to prose judgment). The **true** structural
  backstop — correctly identified by SRE as already existing, independent of this ticket — is
  cross-referenced explicitly: the Builder has no code path to any live external credential-management
  system, full stop, today, regardless of what an envelope's own text says. That absence of capability,
  not an absence of a classification function, is the real "structural impossibility" Condition 2 asked
  for; this revision stops overclaiming the classification function itself provides it, and instead
  states plainly what it actually is — a strong, code-backed, fail-closed first gate, with the Builder's
  own capability absence as the real backstop behind it.
- **The rotation-detection keyword rule is trivially evaded by ordinary paraphrase, with no downstream
  backstop** (Security Architect): a Recommendation reading "Request a new value from the identity
  provider and update the config" describes rotation with zero keyword overlap. **Fixed**: a second,
  independent downstream check added to Lens A's own Blocking standard — a task whose `scope`/
  `acceptance_criteria` appears to require contacting a live external credential/identity system is
  itself a Blocking finding, regardless of whether the authoring-time keyword check caught it.
- **The Recommendation-text redaction assumption had no basis in `report-format.md`'s own real rules**
  (Security Architect, confirmed independently by SRE): that file's Rule 5 redaction obligation is scoped
  explicitly to the Evidence column, not Recommendation. **Fixed**: the envelope-population step now
  re-runs Rule 5 redaction on the `Recommendation` text at copy time, rather than assuming it's already
  clean.
- **Lens A's SSRF coverage needs more than a vocabulary addition** (Security Architect): confirming SSRF
  exploitability typically needs network-topology/reachability information outside a diff's own content,
  and Lens A's Blocking standard has no stated escape valve for "pattern suggests risk, can't confirm
  exploitability from the diff alone" the way `security-review`'s own report format has an explicit
  `Unknowns` state. **Fixed**: Lens A's SSRF coverage is now explicitly scoped as diff-pattern-level only
  (a user-controlled URL reaching an outbound call), with an explicit `NEEDS_EVIDENCE` escalation path
  mirroring the existing convention, rather than a silent all-or-nothing Blocking determination.
- **`cross-skill-escalation.md` has no "notes column" — "the row's own notes" was not a real destination**
  (Software Architect): the real forward table is exactly 4 columns, the reverse table exactly 3; neither
  has room for the selection bar/rotation rule's own text. **Fixed**: a new, small reference doc
  (`docs/skill-framework/shared/security-review-handoff.md`) holds this content, linked from the new row,
  mirroring this file's own established "link out to a referenced doc" convention (the same shape already
  used for `RISK_MAP.md`/`BUSINESS_FLOWS.md`/`API_CATALOG.md` anchors).
- **The reverse-table row was never drafted, only the forward row** (Software Architect): **Fixed**, both
  are now given literal text.
- **Lens A's text is defined independently and non-identically in `SKILL.md` and `workflow/reviewer.md`,
  and Rollout only updated one** (Software Architect): **Fixed**: both files' update is now stated
  explicitly in Rollout, and the category comparison below is re-run against `reviewer.md`'s own richer,
  actually-operative text (the file the Reviewer role actually loads), not just `SKILL.md`'s one-liner.
- **Multi-finding fan-out (N findings → N tasks) left a real same-file/same-symbol collision risk
  unaddressed** (SRE, and independently flagged by the architecture review itself as unresolved
  territory): the legacy envelope has no `dependencies` field, so two tasks from the same report touching
  overlapping lines have no cross-task awareness. **Fixed**: findings sharing a file or symbol are merged
  into one task's `scope`, closing the race by construction rather than relying on a human to manually
  serialize dispatches.
- **The design cited the existing Reviewer "every dispatch, from scratch" discipline to close Condition
  6, while its own `regression_gate` population rule defaulted to null for nearly all security findings —
  silently disabling the one mechanism actually built to re-verify a claimed defect at base commit** (SRE):
  **Fixed**: `regression_gate` is now populated whenever a finding's evidence supports an automatable
  check (common for SSRF/injection/authZ-bypass findings — a crafted request or `curl`), mirroring
  `bug-diagnosis`'s own real, already-documented "optional, populated when the repro is automatable"
  convention exactly, rather than defaulting to null. For the genuinely non-automatable case (null),
  Condition 6 is now honestly stated as resting on Lens A's own fresh diff review alone — a partial, not
  total, closure.
- **8 of the legacy envelope's 15 fields were hand-waved with a single blanket clause** (SRE): **Fixed**:
  each field now gets a concrete default or an explicit security-specific rule (`run_tests`/
  `test_framework_hint` now require a vulnerability-specific negative test, not just "existing suite
  green"; `max_files_per_run` gets a note for multi-file secret patterns; `specialist_inputs` carries an
  explicit security-origin marker).
- **The claimed mirror of B8's "two independently-gated action classes" precedent overclaimed a literal
  match** (SRE): B8's two classes are both independently autonomously-grantable via separate flags; C1's
  split is different in kind — one class has no grant mechanism at all, by design. **Fixed**: stated as an
  explicit, deliberate departure, not a literal mirror — this won't generalize to every future
  "human-only" class in C2-C8 the same way.

**Round 2** adversarial review (same three personas, fresh, re-reviewing revision 2) confirmed 4 of the
above 8 fixes genuinely closed, re-ran the Lens A category comparison against the correct file (no new
defect, a legitimate refinement), and found 6 concrete residual gaps — two of them real recurrences of
the exact round-1 "claimed structural, actually just a convention" pattern in a different mechanism, and
one a demonstrable correctness bug. Fixed in **revision 3** (this revision):

- **The Lens A second gate was placed under "Lens A's own Blocking standard," which doesn't exist as a
  separate structure** (Security Architect): `reviewer.md` has exactly ONE shared Blocking standard used
  by both lenses; "Lens A"/"Lens B" are only priority-focus bullet lists. As worded, a Lens-B-only
  dispatch (a real, documented override this file supports) could skip the new check entirely. **Fixed**:
  reworded as Blocking-standard condition 7 (shared across both lenses), with Lens A named only as the
  lens primed to prioritize looking for it.
- **The "link out to a referenced doc" precedent citation was wrong, and no actual link was embedded in
  the drafted row text** (Software Architect): the cited `RISK_MAP.md`/`BUSINESS_FLOWS.md`/`API_CATALOG.md`
  rows contain zero markdown links — the real anchor-link convention lives in different rows
  (`skill-routing.md`, `confidence-bands.md` — same-directory sibling docs referenced with a simple
  relative link). **Fixed**: corrected the cited precedent, and the forward row's own Handoff-artifact
  column now embeds an actual relative link to `security-review-handoff.md`.
- **The same-file/same-symbol merge rule repeated the exact round-1 "claimed structural, actually just an
  unenforced convention" pattern, just relocated** (Software Architect, independently confirmed
  underspecified by SRE): described as "Strong, by construction" and "closes the race risk by
  construction," but it is applied manually ("whoever authors the handoff"), has no code, and the trigger
  itself was ambiguous (same file regardless of symbol distance? same symbol across files?) with no
  stated composition algorithm for a merged task's `scope`/`acceptance_criteria`. **Fixed**: the trigger
  is now precise (same file AND overlapping/adjacent line ranges, OR the same named symbol across files —
  not bare file co-membership), the composition algorithm is stated explicitly (per-sub-finding bulleted
  entries tagged by `finding_id`, each independently Rule-5-redacted, with the negative-test requirement
  unioned across any qualifying category in the group), and the "by construction" language is corrected
  to state plainly this is a human/Orchestrator-applied convention, not code-enforced — matching the
  honest framing already used for the `regression_gate` null case, not the overclaim the rotation gate
  itself had before round 2's fix.
- **`regression_gate.command`'s own cited "common case" (a crafted request or `curl`) would be rejected by
  the real `validate_repro_command` validator and silently downgraded to the weaker null-closure path —
  the opposite of the intended fix** (SRE — a demonstrable correctness bug, not just vagueness): the real
  validator's regex only accepts `pytest`/`npm`/`make`-shaped test-runner invocations, never a raw `curl`
  or HTTP-client line. **Fixed**: `regression_gate.command` is now tied explicitly to the already-required
  security-specific negative test — it must be the `pytest`/`npm`/`make` invocation of that same test
  (which performs the crafted request/curl internally), never a raw request line, precisely because only
  that shape survives re-validation.
- **`max_files_per_run`'s "+1 from the ordinary default" rule assumed a fixed baseline that doesn't exist
  on the legacy-envelope-bypass path** (SRE): the real default is planning-derived (`estimated_scope`-based),
  and the legacy bypass this design relies on explicitly skips that step. **Fixed**: states a concrete
  absolute value instead of a relative bump.
- **`classify_security_finding` had no stated file/module location**, which matters for "reusable by
  C2-C8" to mean anything concrete (SRE): **Fixed**, named in Rollout.

## Components

| Component | Responsibility | Boundary / owns | Notes |
|-----------|-----------------|------------------|-------|
| New `cross-skill-escalation.md` row (forward table, 4 real columns) | Declares the handoff: a qualifying `security_review_report` finding → `loop-task-implementer` | Documentation only | Mirrors the real `bug-diagnosis → loop-task-implementer` row's exact 4-column shape |
| New `cross-skill-escalation.md` row (reverse table, 3 real columns) | The matching "upstream finding → downstream receives" entry | Documentation only | Now drafted with literal text (round-2 fix), mirroring the real reverse entry for the same bug-diagnosis pair |
| New reference doc: `docs/skill-framework/shared/security-review-handoff.md` (round-2 fix — replaces the non-existent "row's own notes") | Holds the selection bar, the classification function's own documented contract, the envelope-population mapping, and the gitleaks-reuse disclosure | Linked from the new escalation row's Handoff-artifact column (round-3 fix: an actual relative markdown link now appears in the row text itself, not just surrounding prose) | Mirrors `skill-routing.md`/`confidence-bands.md`'s own real relative-link convention (round-3 correction — `RISK_MAP.md`-style rows contain no links at all, were the wrong precedent) |
| `classify_security_finding(recommendation_text, severity) -> QUALIFYING \| ROTATION_REQUIRED \| NOT_QUALIFYING` (new, real, tested function — round-2 fix, closes the central contradiction; location pinned in round 3) | The one, single, consistently-applied classification mechanism — replaces the round-1 prose-only keyword rule | Lives at `skills/loop-task-implementer/scripts/classify_security_finding.py` (round-3 addition — a concrete, reusable location for C2-C8 to actually import or copy from, not just a named pattern) | Mirrors B3's `validate_repro_command` precedent: safety-critical classification belongs in tested code, not prose a human re-derives by eye every time |
| Blocking standard condition 7, shared across both lenses (round-3 correction of round-2's "Lens A's own Blocking standard," which doesn't exist as a separate structure) | A second, independent downstream check: a task whose scope/acceptance_criteria appears to require contacting a live external credential/identity system is itself Blocking-standard condition 7 | Reviewer role, both lenses — Lens A is merely the lens primed to prioritize looking for it | Catches a classification-function false negative regardless of which lens(es) a given dispatch actually runs (`reviewer.md` documents real single-lens-only overrides) |
| Lens A SSRF-coverage scoping note (new — round-2 fix) | States explicitly that Lens A's SSRF coverage is diff-pattern-level only, with a `NEEDS_EVIDENCE` escalation path for unconfirmable reachability | Reviewer role, Lens A | Mirrors `security-review`'s own `Unknowns` escape-valve convention |
| `workflow/reviewer.md` **and** `SKILL.md` Lens A text (both modified — round-2 fix closes the duplication gap) | Explicitly names the security-review categories Lens A's current text doesn't already cover, in **both** files where Lens A is defined | Reviewer role only | See the re-run category comparison below, now checked against `reviewer.md`'s own richer text |
| The envelope population rule (documented in the new reference doc) | Maps a qualifying finding's own fields into the real, existing legacy `implementation_task` envelope, now with all 15 fields addressed concretely | Reuses B6's own "legacy bypass, cite the real 15 fields" precedent — no new typed artifact | See Data model |
| Merge rule for colliding findings (round-2 fix, closes SRE's collision finding; precision-corrected in round 3) | Findings are merged into one task when EITHER (a) same file AND overlapping/adjacent line ranges, OR (b) the same named symbol across different files — never on bare file co-membership alone (round-3 fix; round-2's "sharing a file or symbol" wording would have over-merged unrelated findings that merely share a large file) | Applied manually by whoever authors the handoff, same actor as the classification function — **stated honestly as a human/Orchestrator-applied convention, not code-enforced** (round-3 correction: round 2's "by construction"/"Strong" language repeated the exact overclaim pattern round 1 found and fixed for the rotation gate, just relocated to this mechanism) | Composition algorithm for a merged task (round-3 addition, previously unstated): `scope`/`acceptance_criteria` become a bulleted list, one entry per sub-finding, each tagged by its own `finding_id` and independently Rule-5-redacted; the security-specific negative-test requirement is unioned across the group — present if ANY sub-finding's category requires it |

**Confirmed untouched**: `workflow/builder.md`, `workflow/orchestrator.md`, `workflow/lifecycle-gate.md`,
`scripts/validate_loop_lifecycle.py`, `reference/state-schema.yaml` — still true after round 2's fixes;
the new classification function and Lens A additions are additive to existing files/scripts, not new
workflow steps for the Orchestrator or Builder. The legacy envelope bypass still means zero
`composition_contracts.yaml`/`skills.yaml` registration is needed, matching B6's own confirmed precedent.
**The real structural backstop for rotation** (round-2 addition, replacing the overclaimed "zero code
needed" framing for this one piece): the Builder has no code path to any live external
credential-management system anywhere in this framework, today, independent of this ticket — this is a
true capability absence, not a convention, and is the actual property Condition 2 was asking for. The new
classification function is a strong, fail-closed first gate on top of that real backstop, not a
substitute for it.

## APIs

Not a network-facing feature — "API surface" here is the escalation row's own literal contract, plus the
new classification function's signature:

| Field / function | Contract | Consumer(s) | Notes |
|--------------------------|----------|-------------|-------|
| New forward row | `"A vulnerability finding has a concrete, fixable code-level remediation and is not rotation-requiring (per classify_security_finding — see [security-review-handoff.md](security-review-handoff.md))"` \| `security-review → loop-task-implementer` \| `security_review_report` (finding category, severity, evidence refs — file:line citations only) \| `"Fix the {category} finding in {file/symbol} per security-review's own recommendation"` | Whoever authors the handoff | Mirrors the real bug-diagnosis row's four-column shape; round-3 fix embeds the actual relative link in the Handoff-artifact column text itself, not just surrounding prose |
| New reverse row | `"security-review confirms a finding with a concrete, non-rotation-requiring code-level fix"` \| `loop-task-implementer receives the finding's category, severity, and evidence refs` \| `"Fix the {category} finding in {file/symbol} per security-review's own recommendation"` | Whoever authors the handoff | Round-2 addition, round-3 wording fix (Software Architect: the real reverse-table convention phrases column 1 with the skill as subject — "`<skill>` confirms/finds/flags...", matching `bug-diagnosis`'s own real row) |
| `classify_security_finding(recommendation_text: str, severity: str) -> Literal["QUALIFYING", "ROTATION_REQUIRED", "NOT_QUALIFYING"]` | Pure function, no I/O: `severity` not in `{Critical, High, Medium}` → `NOT_QUALIFYING`; else, rotation-keyword-proximity check (`rotate\|revoke\|reissue\|regenerate\|re-issue` near `credential\|secret\|key\|token\|password`, case-insensitive) on `recommendation_text` → `ROTATION_REQUIRED` if matched; else → `QUALIFYING`. Any ambiguous/unparseable input fails toward `ROTATION_REQUIRED`, never `QUALIFYING` | Whoever authors the handoff, invoked as a real function call, not applied by eye | The ONE consistently-applied classification mechanism — same function every time, for this ticket and reusable (with a different keyword/severity table) by C2-C8. Lives at `skills/loop-task-implementer/scripts/classify_security_finding.py` (round-3 location fix) |
| Blocking standard condition 7 (shared, not lens-exclusive — round-3 wording fix) | "A task whose own `scope`/`acceptance_criteria` describes contacting, authenticating against, or modifying a live external credential/identity/secrets-management system is itself Blocking-standard condition 7, regardless of how the task was authored or classified upstream, and regardless of which lens(es) this dispatch actually runs" | Reviewer, both lenses (Lens A primed to prioritize checking it) | Independent of `classify_security_finding` — catches a false negative at authoring time even on a Lens-B-only dispatch |

## Events

Still none for the escalation/classification pieces — reuses the Orchestrator's own existing
completion-report channel for the resulting task, same as every legacy-envelope task. The classification
function itself is a pure, local, no-I/O call — no event, no network, no state.

## Data model

| Entity | Key fields | Relationships | Owner |
|--------|-----------|-----------------|-------|
| Legacy `implementation_task` envelope (reused, confirmed at `composition_contracts.yaml`'s real 15-field list) — **all 15 fields now addressed concretely (round-2 fix)** | `task_id` — generated per existing convention; `scope` — the finding's category + file/symbol citation, **merged across all findings in the same collision group** (same file AND overlapping/adjacent lines, OR same symbol across files — never bare file co-membership alone; round-3 precision fix, closes the collision risk without over-merging unrelated findings in a large shared file); `acceptance_criteria` — the finding's `Recommendation` text, **re-redacted per Rule 5 at copy time** (round-2 fix, not assumed already clean), PLUS for a qualifying finding whose category is Injection/SSRF/AuthZ-bypass, an explicit requirement that the fix include a negative test proving the specific vulnerability is closed (round-2 addition, not just "existing suite green"); `request` — synthesized trigger phrase; `repo_root`/`target` — file/symbol path from Evidence; `level_hint` — same default as any legacy-envelope task; `specialist_inputs` — now explicitly carries a `security_origin: true` marker (round-2 fix) so a human/Orchestrator reading the task later knows it came from this handoff; `test_framework_hint`/`run_tests` — `run_tests: true` by default (same as any code-change task), with the security-specific negative-test requirement folded into `acceptance_criteria` rather than a separate field; `max_files_per_run` — a concrete absolute value of **3** for a Secrets finding whose evidence suggests a pattern recurring across files, **2** otherwise (round-3 correction: round 2's "+1 from the ordinary default" assumed a fixed baseline that doesn't exist on the legacy-envelope-bypass path, which skips `implementation_plan.py`'s own planning-derived `estimated_scope` computation entirely); `deadline`/`session_token_budget`/`output_dir` — same defaults as any legacy-envelope task, unchanged; `regression_gate` — **populated whenever the finding's required security-specific negative test (see `acceptance_criteria` above) has its own `pytest`/`npm`/`make` invocation command** — `regression_gate.command` is set to that exact invocation, **never** a raw `curl`/HTTP-client line (round-3 correctness fix: the real `validate_repro_command` validator's regex only accepts `pytest`/`npm`/`make`-shaped test-runner invocations; a raw crafted-request/curl line, round 2's own cited "common case," would be rejected by re-validation and silently downgraded to the null path — the opposite of the intended fix). Null only when the finding's category doesn't require a negative test at all (i.e., genuinely non-automatable, no scriptable repro of any kind) | None of these fields ever carry the raw, un-redacted `review_target` excerpt | Whoever authors the handoff |
| (No entity for rotation-requiring findings) | N/A — `classify_security_finding` never returns a value that maps to an envelope-population path | A rotation-requiring finding only ever reaches a human, via the report's own existing rendering | — |

## State machines

| Entity | States | Transitions | Notes |
|--------|--------|-------------|-------|
| A single security-review finding | `NOT_QUALIFYING` → terminal, report-only; `ROTATION_REQUIRED` → terminal, human-action-required, no task authored; `QUALIFYING` → an `implementation_task` is authored, with findings in the same collision group (same file AND overlapping/adjacent lines, OR same symbol across files — round-3 precision fix) merged into one task, then proceeds through the completely unmodified Builder/Reviewer/lifecycle-gate pipeline, with Blocking-standard condition 7 (above) as an independent downstream check | The classification is now a real function call, not a documented convention a reader applies — closes the central round-1 contradiction | The real structural backstop is the Builder's own capability absence (no code path to any live credential system), not this state machine alone — stated honestly, not overclaimed |

## Consistency

| Boundary | Model (strong / eventual) | Why |
|----------|-----------------------------|-----|
| Finding freshness vs. task dispatch (Condition 6) | **Partially closed, stated honestly (round-2 correction of an overclaim)**: for findings with a populated `regression_gate` (now the common case per the round-2 fix), the existing dual-worktree regression-gate re-execution directly re-verifies the claimed defect at base commit — a real, strong closure. For the genuinely non-automatable null case, closure rests on Lens A's own fresh, every-dispatch-from-scratch diff review alone — a real but partial mechanism, not a full guarantee the finding was still accurate at dispatch time | Round 1 claimed full closure from Lens A alone while its own population rule disabled the stronger mechanism by defaulting to null; round 2 fixes the default and states the remaining gap honestly |
| Colliding findings (same file + overlapping lines, or same symbol across files) across one report | **Convention-level, human/Orchestrator-applied — not code-enforced** (round-3 correction of round 2's overclaimed "Strong, by construction") | Merged into one task at authoring time per the precise trigger and composition algorithm above — a real mitigation, but as honestly disclosed a limitation as the `regression_gate` null case, not a structural guarantee |

## Retries & idempotency

| Operation | Idempotent? | Retry / backoff strategy |
|-----------|-------------|----------------------------|
| `classify_security_finding` | Yes — pure function, no I/O | N/A, deterministic |
| Authoring an `implementation_task` from a qualifying finding | Not automated in the usual sense | N/A — one-time, human-or-Orchestrator-authored action per (merged) finding group |

## Capacity

| Dimension | Estimate | Basis |
|-----------|----------|-------|
| Findings-to-tasks ratio | **One task per qualifying finding GROUP, where a group is all findings meeting the precise merge trigger above** (same file + overlapping/adjacent lines, or same symbol across files — round-3 precision fix; not bare file co-membership) | Matches this skill's own scope-discipline convention (a task covers one coherent unit of work) while closing the collision risk SRE identified; findings that don't meet the trigger remain independent tasks, matching round 1's own correct reasoning for that case |

## Failure strategy

| Failure mode | Degradation / mitigation |
|--------------|-----------------------------|
| `classify_security_finding` receives ambiguous/unparseable input | Fails toward `ROTATION_REQUIRED` — a false positive costs one human review; a false negative would be the real failure |
| A `classify_security_finding` call is skipped entirely (someone hand-authors an envelope without calling it) | Caught by Blocking-standard condition 7 (round-3 reworded, shared across both lenses) — an independent, downstream check that doesn't rely on the authoring-time call having happened at all, and fires regardless of which lens(es) the dispatch actually runs |
| A security-removal fix is merged but the secret remains in git history | Explicitly disclosed, NOT closed (Condition 1): the existing, already-active `gitleaks` CI gate is the ongoing, reused protection; full history-scrubbing is an explicit, named, human-only residual |
| A qualifying finding's underlying code changed before dispatch, `regression_gate` populated | Covered by the dual-worktree regression-gate re-execution (round-2 fix) |
| Same as above, `regression_gate` null (non-automatable) | Covered only by Lens A's own fresh diff review — a partial, disclosed closure (round-2 honesty correction) |
| SSRF finding whose exploitability can't be confirmed from the diff alone | Lens A escalates `NEEDS_EVIDENCE`, never silently clears or silently blocks (round-2 addition, mirrors `security-review`'s own Unknowns convention) |

## Observability

| Signal | What's measured |
|--------|-------------------|
| None new beyond the resulting task's own existing completion/review lifecycle | Unchanged from round 1 |

## Rollout plan

| Phase | Scope | Feature flag / migration order |
|-------|-------|----------------------------------|
| 1 | New forward + reverse `cross-skill-escalation.md` rows (both now drafted, round-2 fix), linking to the new `docs/skill-framework/shared/security-review-handoff.md` reference doc (round-2 fix, replaces the non-existent "row's own notes") | Documentation only |
| 2 | New `classify_security_finding` function at `skills/loop-task-implementer/scripts/classify_security_finding.py` (round-3 location fix), with real unit tests covering the known-paraphrase-evasion cases Security Architect found (e.g. "request a new value from the identity provider") | New, tested code — the one piece of real code this ticket adds |
| 3 | Lens A text extension in **both** `workflow/reviewer.md` and `SKILL.md` (round-2 fix — both named explicitly now), plus Blocking-standard **condition 7** (round-3 wording fix — shared across both lenses, not "Lens A's own Blocking standard") and the SSRF `NEEDS_EVIDENCE` scoping note, all in `reviewer.md` | Documentation + one new, shared Blocking-standard condition, strictly additive |
| 4 | gitleaks-reuse disclosure, in the new reference doc | Documentation only |
| 5 | **Precedent note for Epic C** (Condition 5): the matrix-row format, the legacy-envelope-bypass population convention, the real-tested-classification-function pattern (round-2 addition to what generalizes), and the autonomous/human-gate action-split shape are intended to generalize to C2-C8. The exact selection bar, keyword table, and category-coverage gap closed in Lens A are C1-specific. **Explicitly NOT a literal mirror of B8's two-independently-grantable-classes shape** (round-2 correction) — C1's split has one side with no grant mechanism at all, by design; future Epic-C tickets should evaluate their own action split on its own merits, not assume B8's shape applies uniformly | Documentation only |
| 6 | First real dry-run | **Open question** — see below |

## Lens A category-by-category comparison (closes architecture-review Condition 4, re-run in round 2 against the correct file)

Round 1 compared only `SKILL.md`'s one-line summary. Round 2 (Software Architect's finding) re-runs this
against `workflow/reviewer.md`'s own fuller, actually-operative Lens A text, which already includes
"Input validation with security impact" — partially, not fully, covering Injection.

| Category | Covered by `reviewer.md`'s current text? | Verdict |
|----------|-----------------------------------|---------|
| AuthN | Yes — "authentication" | Covered |
| AuthZ (incl. tenant isolation) | Yes — "authorization" | Covered |
| Secrets | Yes — "secrets" | Covered |
| Injection | **Partially** — "Input validation with security impact" covers the input-validation half but doesn't name injection (SQL/command/template injection) explicitly | **Gap, narrower than round 1 found** |
| SSRF | No — "trust boundaries" is a loose umbrella, not a named coverage | **Gap** (now explicitly scoped to diff-pattern-level, see above) |
| Data leakage | No — "data integrity" is correctness, not confidentiality | **Gap** |
| Cryptography | No | **Gap** |
| Dependency exposure | Not named, reasonably excluded (owned by `dependency-upgrade-review`) | Reasonably out of scope |

**Literal fix**, applied to **both** `reviewer.md` and `SKILL.md` (round-2 fix — both files, not one):
extend the existing bullet to read *"...security-relevant failure handling, injection (including where
input validation already partially applies), SSRF (diff-pattern-level — see the NEEDS_EVIDENCE
escalation note), cryptographic weaknesses, data leakage/exposure."*

## Open questions

1. **No concrete validation target exists in this session's own immediate work** — unchanged from
   revision 1's honest disclosure.
2. **`classify_security_finding`'s keyword/severity table is a deliberately simple, conservative
   heuristic, now at least applied consistently via real code, but its precision/recall against
   real-world `Recommendation` phrasing is still unvalidated** — the Lens A second gate (round-2 addition)
   is the disclosed backstop for this, not a claim that the function itself is perfect.
3. **Whether `security-review`'s own report format should eventually gain a structured
   `remediation_type` field (rather than this design's own text-classified free text) remains a
   reasonable future improvement, out of scope for this ticket** — unchanged from revision 1.
4. **The security-specific negative-test requirement in `acceptance_criteria` (round-2 addition) has no
   enforcement beyond the Reviewer's own judgment that it was actually satisfied** — this is the same
   class of "prose requirement, human/Reviewer-applied" limitation the rotation split itself had before
   round 2's fix, but closing it with a second real function (a test-presence validator) is left as a
   genuinely open question for a future revision, not attempted here, since it would require either
   parsing the actual diff for a new test file/case (a nontrivial check) or trusting the Reviewer's own
   existing Blocking-standard judgment (test sufficiency is already one of Lens B's stated priorities).
