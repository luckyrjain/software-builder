# Change impact report — C1: security-review → executor handoff

**Coverage status: COMPLETE**

## Assessment target

Proposed state. Repo: `luckyrjain/software-builder`, main, head includes merged PR #319 (B8). Sources:
`docs/superpowers/specs/2026-10-01-c1-security-review-executor-handoff-design.md` (revision 3, converged
across 2 full adversarial review rounds plus 1 narrow confirmation-and-patch pass) and
`docs/superpowers/specs/2026-10-01-c1-security-review-executor-handoff-architecture-review.md` (Approved
with conditions, 6 conditions, all addressed).

## Criticality: High

Not for code size — this is a small ticket (one new Python function, three documentation/convention
changes) — but for review-history density and the fact that this is the FIRST of eight Epic-C
"analysis skill → executor" tickets, whose conventions are explicitly intended to generalize to C2-C8.
The design's own central defect — a classification boundary deciding whether a security finding can
become an autonomous task, versus must stop at a human — was claimed solved by prose alone in revision
1 (found false, independently, by two personas), fixed with real code in revision 2, and then the
**identical underlying bug class recurred in a different mechanism** (the same-file/same-symbol merge
rule, described as "structural"/"by construction" while being a human-applied convention with zero code
behind it) — found independently by the same two personas reviewing their own prior fix. This recurrence
is the single most important fact a human reviewing the actual implementation diff should carry forward:
**any new mechanism in this PR described as "structural," "by construction," or "guaranteed" must be
checked for whether it is actually backed by code, not merely by a documentation convention.**

## Change classes

- `new-capability-declaration` (one new `cross-skill-escalation.md` row pair — `security-review →
  loop-task-implementer`, the first such handoff for this analysis skill)
- `new-validation-logic` (`classify_security_finding` — the one piece of real code this ticket adds)
- `workflow-policy-extension` (`reviewer.md`'s Blocking standard gains condition 7, confirmed to land in
  the real, single, shared list — not a lens-exclusive structure that doesn't exist)
- `documentation-only` (Lens A text extension in both `SKILL.md` and `reviewer.md`; the new
  `security-review-handoff.md` reference doc)

## Impacted services / files

| Path | Nature of change | Risk |
|------|-------------------|------|
| **`docs/skill-framework/shared/cross-skill-escalation.md`** | New forward row (4 real columns, confirmed against the file's own header) and new reverse row (3 real columns), mirroring the real `bug-diagnosis → loop-task-implementer` row pair exactly. The forward row's Handoff-artifact column embeds a relative markdown link to the new reference doc, matching the real `skill-routing.md`/`confidence-bands.md` link convention (confirmed via direct read — the `RISK_MAP.md`-style rows the design's own round-1 draft mistakenly cited contain no links at all) | Low — purely additive documentation, correctly scoped against the real file structure |
| **`docs/skill-framework/shared/security-review-handoff.md`** (new) | Holds the selection bar, `classify_security_finding`'s documented contract, the envelope-population mapping (including the precise merge-trigger/composition algorithm and the `regression_gate`-tied-to-negative-test rule), and the gitleaks-reuse disclosure | Low — a new, self-contained reference doc; its proposed location/naming fits this directory's existing flat, topic-named file convention (e.g. `prompt-injection.md`, `safe-output.md`, `skill-routing.md` are all siblings at this same level) |
| **`skills/loop-task-implementer/scripts/classify_security_finding.py`** (new) | A small, pure, no-I/O function: `(recommendation_text, severity) -> QUALIFYING \| ROTATION_REQUIRED \| NOT_QUALIFYING`, fail-closed toward `ROTATION_REQUIRED` on ambiguous input | **High-scrutiny file** — this is the one piece of real code in the ticket, and the design's own review history shows this exact classification boundary was the hardest thing to get right across 2 rounds. A human must independently re-verify the function actually implements the final, converged keyword/severity rule exactly as specified (fail-closed on ambiguity, never fail-open toward `QUALIFYING`) |
| **`skills/loop-task-implementer/tests/test_classify_security_finding.py`** (new, not explicitly named by the design but required — see Required tests) | Unit tests for the classification function, following this skill's own established test-location convention (matches B7's `test_app_run.py`, B8's `test_tracker_write_back.py` precedent — a new script gets a same-named sibling test file in `tests/`) | High — this is the direct regression test for the ticket's one security-sensitive mechanism |
| **`skills/loop-task-implementer/workflow/reviewer.md`** | (a) Lens A text extension naming injection/SSRF/cryptographic-weaknesses/data-leakage, with SSRF explicitly scoped to diff-pattern-level only plus a `NEEDS_EVIDENCE` escalation note; (b) new Blocking-standard **condition 7** | **The second-most-important file to review carefully.** Confirmed directly against the real file: the Blocking standard (`## Blocking standard`, line 162) is a single, shared, numbered list — conditions 1-6 today (condition 6 added by B3's own regression_gate work). Condition 7 must land in THIS list, applicable to both lenses — there is no separate "Lens A's own Blocking standard" structure anywhere in the real file (Lens A/Lens B, lines ~192+/211+, are only priority-focus bullet lists, not independent enforcement structures). A human must confirm the actual diff adds condition 7 to the one real shared list, not creates a new, lens-scoped structure that doesn't match this file's existing architecture |
| **`skills/loop-task-implementer/SKILL.md`** | The SAME Lens A text extension as `reviewer.md` | Low, but a confirmed-necessary duplicate edit — the design's own round-2 review found and fixed exactly this "touched one file, missed the duplicate" gap once already; a human should confirm both files are actually touched in the real diff, not just one |

**Confirmed untouched**: `workflow/builder.md`, `workflow/orchestrator.md`, `workflow/lifecycle-gate.md`,
`scripts/validate_loop_lifecycle.py`, `reference/state-schema.yaml`, `scripts/registry/
composition_contracts.yaml`, `skills.yaml` — this design's entire mechanism is a new standalone function
plus documentation/convention changes; the legacy `implementation_task` envelope bypass needs zero schema
registration (mirrors B6's own confirmed precedent for `task.requirements_ref`-style fields, verified
directly in round 2's own review against the real `composition_contracts.yaml`).

## Impacted contracts

- `reviewer.md`'s Blocking standard — extended from 6 to 7 conditions, additive, no restructuring of the
  existing 6.
- No `implementation_task`/`plan_execution_state` schema change — the legacy envelope bypass is purely a
  population convention, not a new typed field.
- No finding-output schema change.

## Impacted data

None — no new persistent store, no new run-log event (the classification function is pure, no-I/O,
no-event; confirmed consistent with this session's own established "no new event for advisory/
documentation-level mechanisms" pattern from B6/B7/B8).

## Impacted dependencies

None new — `classify_security_finding` is pure Python, no new library, no new capability declaration in
`mcp-capabilities.md` (this ticket adds no new host-capability requirement at all, unlike B7/B8).

## Impacted owners

Single owner (CODEOWNERS root wildcard). No CODEOWNERS change needed.

## Required tests

1. **`classify_security_finding` unit tests — the single highest-priority test in this PR**: every
   boundary the design's own review history found real bugs around — a severity below the floor (Low) →
   `NOT_QUALIFYING`; a `Recommendation` containing an exact keyword match (`rotate`/`revoke`/`reissue`/
   `regenerate`/`re-issue` near `credential`/`secret`/`key`/`token`/`password`) → `ROTATION_REQUIRED`; the
   specific round-1-identified paraphrase-evasion case ("Request a new value from the identity provider
   and update the config") — this is explicitly disclosed as a case the keyword rule alone does NOT catch
   (Open Question 2), so this test should assert the function's own documented, honest behavior for this
   input (likely `QUALIFYING`, relying on Blocking-standard condition 7 as the disclosed backstop), not a
   false claim that the function itself closes this gap; ambiguous/malformed input → `ROTATION_REQUIRED`
   (fail-closed), never `QUALIFYING`.
2. **Blocking-standard condition 7 — a durable regression test**: construct a task whose `scope`/
   `acceptance_criteria` describes contacting/authenticating against/modifying a live external credential
   system, and confirm this is flagged as Blocking regardless of (a) which lens dispatches it (both
   Lens-A-only and Lens-B-only dispatch scenarios, since this condition lives in the one shared list) and
   (b) whether `classify_security_finding` was ever called at all for that task — this directly tests the
   "independent downstream backstop" property the design claims.
3. **`cross-skill-escalation.md` row structure test** (or manual verification, matching this file's own
   lint convention if one exists): confirm the new forward/reverse rows parse as valid rows in the real
   table structure (correct column count for each table) and the embedded link resolves to the real
   `security-review-handoff.md` path.
4. **`regression_gate.command` shape test**: for any test fixture exercising the envelope-population
   mapping, confirm a populated `regression_gate.command` value is genuinely a `pytest`/`npm`/`make`-shaped
   invocation (matching `validate_repro_command`'s real regex), never a raw `curl`/HTTP-client line — this
   is the direct regression test for a demonstrated, real correctness bug found in an earlier revision of
   this design.
5. **Merge-rule precision test**: two findings in the same large file but with non-overlapping,
   non-adjacent line ranges and no shared symbol must NOT be merged into one task (the specific
   over-merging failure mode the design's own round-3 fix closed); two findings genuinely sharing a
   symbol across different files MUST be merged, with the composition algorithm (bulleted per-`finding_id`
   entries, independently Rule-5-redacted) producing a well-formed result.

## Operational impacts

1. **First handoff this session has built where the "human gate" side has no grant mechanism at all** —
   unlike B8's two independently-autonomously-grantable classes, rotation-requiring findings here have no
   path to autonomy under any authorization configuration. This is a deliberate, disclosed departure from
   B8's own shape (the design's own round-2 fix corrects an earlier overclaimed "mirrors B8" framing) —
   worth the Orchestrator/human's own awareness that future Epic-C tickets should evaluate their own
   action split on its own merits, not assume B8's shape applies uniformly.
2. **The security-specific negative-test requirement in `acceptance_criteria` has no enforcement beyond
   the Reviewer's own judgment** (design's own Open Question 4, honestly disclosed, not silently dropped)
   — a second real validator (checking an actual new test file/case exists in the diff) was explicitly
   considered and deferred as out of scope for this revision, not attempted.
3. **This is the template for C2-C8** — the "Precedent for Epic C" note (Rollout phase 5) names what
   generalizes (matrix-row format, legacy-envelope-bypass convention, the real-tested-classification-
   function pattern) versus what's C1-specific (exact keyword table, severity floor, category-coverage
   gap) at a reasonable level of detail for a future design pass to build from — but it is a single
   paragraph, not a worked example; a C2 design pass should expect to do its own category-by-category
   comparison and its own classification-function design from scratch, using C1's *pattern*, not copying
   C1's *literal content*.

## Review triggers

**None required.** This design underwent 2 full rounds of dedicated adversarial multi-persona review
(Security Architect, SRE, Software Architect) plus a narrow, targeted confirmation-and-patch pass — the
central security-sensitive finding (the rotation/fix classification boundary) was independently
discovered as unenforced in round 1 by two personas, fixed with real code in round 2, and then the exact
same underlying bug class was independently re-discovered in a DIFFERENT mechanism by the same two
personas reviewing their own fix — a materially deeper, self-correcting adversarial process than a
standard `security-review` pass would independently produce on this one surface. Matches this session's
own established reasoning for B3/B4/B6/B7/B8 not re-triggering a fresh security-review pass after
comparable adversarial depth.

## Material unknowns

1. **No concrete validation target exists in this session's own immediate work** (design's own Open
   Question 1) — mirrors B7/B8's own honest "no dry-run target" disclosure.
2. **`classify_security_finding`'s keyword/severity table remains an unvalidated heuristic against
   real-world phrasing** (design's own Open Question 2) — Blocking-standard condition 7 is the disclosed
   backstop for this, not a claim the function itself is complete.
3. **Whether `security-review`'s own report format should eventually gain a structured
   `remediation_type` field is a reasonable future improvement, explicitly out of scope** (design's own
   Open Question 3).
4. **The security-specific negative-test requirement has no enforcement beyond Reviewer judgment**
   (design's own Open Question 4) — a second validator function was considered and deliberately deferred,
   not built, in this revision.

## Unknowns

None beyond the material unknowns above — repository read was available throughout, and all referenced
real files (`reviewer.md`'s actual Blocking-standard structure and condition count, `cross-skill-
escalation.md`'s real table column structures and link convention, `composition_contracts.yaml`'s real
`task.requirements_ref` no-registration precedent, `validate_repro_command`'s real regex) were directly
verified across this ticket's own 2+1 review rounds, not taken on the design document's word alone.

## Evidence refs

- `docs/superpowers/specs/2026-10-01-c1-security-review-executor-handoff-architecture-review.md`
- `docs/superpowers/specs/2026-10-01-c1-security-review-executor-handoff-design.md` (revision 3)
- Direct repository verification: `skills/loop-task-implementer/workflow/reviewer.md` (the real,
  single, shared Blocking standard, line 162, conditions 1-6 confirmed, condition 7 would be additive);
  `skills/security-review/reference/report-format.md` (the real 8 categories and the real Evidence-only
  Rule 5 scope); `docs/skill-framework/shared/cross-skill-escalation.md` (the real bug-diagnosis row
  pair and the real `skill-routing.md`/`confidence-bands.md` link convention); `scripts/registry/
  composition_contracts.yaml` (the real 15-field legacy envelope and the `task.requirements_ref`
  no-registration precedent); `skills/bug-diagnosis/tests/test_repro_command_validation.py` (the real
  `validate_repro_command` regex); confirmed no `workflow/builder.md`/`workflow/orchestrator.md`/
  `workflow/lifecycle-gate.md`/`scripts/validate_loop_lifecycle.py`/`reference/state-schema.yaml`/
  `composition_contracts.yaml`/`skills.yaml` changes anywhere in the converged design.
