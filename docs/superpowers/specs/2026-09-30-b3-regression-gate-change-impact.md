# Change Impact Report — B3: bug-diagnosis → loop-task-implementer fail-before/pass-after regression gate

**Assessment target:** `luckyrjain/software-builder`, proposed state (design revision 6, "Ready with open
questions")
**Coverage status:** COMPLETE
**Criticality:** High

Not because the code surface is large — after 6 rounds of review it's genuinely small (two optional
schema fields, prose-only changes to three workflow docs, one literal validator function) — but because
this touches `loop-task-implementer`'s Reviewer role and Blocking-standard vocabulary directly, the same
class of shared-contract change B2 made to `implementation-planner`'s evidence contract, and because the
command-validator function alone needed 4 rounds of adversarial security review to close real,
distinct file-write/injection bypasses before converging.

## Change classes

- `contract-change` — `reviewer.md`'s Blocking standard gains a 6th condition and a formal treatment for
  gate-related `NEEDS_EVIDENCE` outcomes; `orchestrator.md`'s response-wait-budget sentence gains a second
  extension (its first was B1's clarify sub-step).
- `schema-addition` — two new optional fields, on two different artifact types, following B2's own
  recently-established pattern for this exact repository (skills.yaml `fields` + `payload_types`
  registration surfaces).
- `new-validation-logic` — the `repro_command` validator (delimiter-agnostic substring search) is new,
  non-trivial security-relevant code with no precedent elsewhere in this repo.
- `documentation-only` — Builder/bug-diagnosis consuming-behavior additions, cross-skill-escalation row
  updates.

## Impacted repositories

`luckyrjain/software-builder` only. Single-repository change.

## Impacted services / components

| Component | Impact | Notes |
|-----------|--------|-------|
| `skills.yaml` / `scripts/registry/composition_contracts.yaml` | Direct, additive | `bug_diagnosis_report` gains `repro_command` on both `fields` and `payload_types` (it's `mode: canonical`, confirmed durable, needs both surfaces per the same equality check B2's design already traced in `artifact_contracts.py`); `implementation_task` gains `regression_gate` on `fields` only (confirmed `mode: external`, exempt from the two-surface check). |
| `skills/loop-task-implementer/workflow/reviewer.md` | Direct | New procedure subsection, Blocking-standard condition 6, the inconclusive-`NEEDS_EVIDENCE` convention, the `"regression_gate: "` evidence-prefix requirement on both finding classes. **No change to the finding output schema itself** — this was tried three times across the review (a `source` field, then reusing `category`, then dropped entirely) and the final design deliberately routes through the *existing*, unmodified schema. |
| `skills/loop-task-implementer/workflow/orchestrator.md` | Direct, narrowly additive | One sentence extending the existing response-wait-budget bullet (§3) — the same sentence B1 already extended once. This is the *second* extension of that one sentence across two consecutive gap-backlog tickets; confirm at implementation time that both clauses (B1's and B3's) coexist grammatically in one sentence, not two competing edits. |
| `skills/loop-task-implementer/workflow/builder.md` | Direct, additive | New consuming behavior for `regression_gate.command` — advisory-only, explicitly does not replace or get replaced by the Reviewer's independent execution. |
| `skills/loop-task-implementer/reference/state-schema.yaml`, `scripts/validate_loop_lifecycle.py` | **None** — confirmed, not assumed | Three consecutive review rounds tried to add state here (a cross-check validator function, a persisted `regression_gate_result` field) and each attempt was found broken against real code; the final design deliberately touches neither file. This is the single most important negative-impact confirmation for this ticket — verify at implementation time that no stray edit reintroduces either. |
| `skills/bug-diagnosis/workflow/repro.md`, `reference/report-format.md` | Direct, additive | New field + the validator function, used verbatim from the design (already through 4 rounds of adversarial security review — do not re-derive). |
| `docs/skill-framework/shared/cross-skill-escalation.md` (rows ~138, ~199) | Direct, additive | Text-only update to two existing rows; per this file's own stated convention, the matrix documents an optional handoff, never the enforcement mechanism itself. |
| `implementation-planner`, `implementation_plan` schema (B2's own recent surface) | **None** | Confirmed orthogonal: B2 touched `implementation-planner`'s evidence contract and the `implementation_plan` v1 schema; B3 touches `implementation_task` (the pre-existing, structurally separate "legacy" envelope B2's own design explicitly confirmed is a different capability from `implementation_plan`) and the Reviewer/Builder/Orchestrator roles directly. No shared file, no shared schema, no shared validator function between the two tickets' changes. |
| Every other one-hop consumer of `bug_diagnosis_report`/`implementation_task` (e.g. `incident-rca`, `codebase-architecture-review` per the escalation matrix's other bug-diagnosis rows; the 5 test-creator skills with `consume_fields` allowlists for `implementation_task`) | None observed | Both new fields are optional/additive; no existing `consume_fields` allowlist needs the new field (none of those skills need `regression_gate`), and nothing existing reads either field structurally. |

## Impacted contracts

| Contract | Before | After | Compatibility |
|----------|--------|-------|---------------|
| `bug_diagnosis_report` v1 schema | 12 fields | 13 fields (`repro_command: str \| null`) | Backward compatible — optional, additive |
| `implementation_task` schema | 14 fields | 15 fields (`regression_gate: {...} \| null`) | Backward compatible — optional, additive; external/exempt from the stricter two-surface registry check |
| `reviewer.md`'s Blocking standard | 5 conditions | 6 conditions | Additive; the 5 existing conditions are textually unchanged |
| `reviewer.md`'s finding output schema | Unchanged | **Unchanged** | Deliberate, confirmed by the design's own revision history — the "no new field" property is itself load-bearing (it's what makes the mechanism deployable without touching the closed portable-evidence schema in `docs/skill-framework/shared/review_contract_runtime.py`) |
| `orchestrator.md`'s response-wait-budget sentence | Carries B1's one prior extension | Carries a second extension (B3's) | Additive; every other dispatch keeps the unmodified 30-minute default |

## Impacted data

None. No schema/table/persisted-record change beyond the two artifact schemas above. No PII, no secrets
touched directly — though the *validator function itself* is security-relevant precisely because it's the
only thing standing between an untrusted-adjacent `repro_command` value and code execution at a historical
commit (see Review triggers, below).

## Impacted dependencies

None new. No new third-party package. The design's `git worktree add`-based second-worktree mechanism uses
only `git` capability the Reviewer already exercises today for its primary worktree.

## Impacted owners

`CODEOWNERS` already covers every touched path via the existing root wildcard (`* @luckyrjain`, confirmed
by direct read — the file has no `skills/`-scoped rows at all). No `CODEOWNERS` edit needed.

## Required tests

1. **Command-validator regression suite** (the single most load-bearing test given this function's own
   4-round review history): every bypass found across rounds 3–5 must have a dedicated, named test case
   asserting rejection — `--junitxml=/etc/cron.d/x`, `--cov-report=html:/home/user/.ssh/authorized_keys`,
   `--cov-report=xml:/etc/cron.d/evil`, `--basetemp=/some/dir`, bare `pytest /etc/passwd`,
   `pytest tests/../../etc/passwd`, `--cov-report=html:../etc/passwd`, `--x=y=/etc/passwd` — plus positive
   cases confirming legitimate commands (`pytest tests/test_foo.py::test_bar`, `make test`,
   `npm run test:unit`) still validate. This is not optional coverage — it is the direct regression test
   for a real, previously-exploitable vulnerability class that took 4 rounds to close.
2. **Registry schema regeneration check**: both new fields present in `skills.yaml`'s `fields` list(s);
   `bug_diagnosis_report`'s `payload_types` entry added and matching; `make generate --check` (or this
   repo's equivalent generated-file-drift lint) clean against `composition_contracts.yaml`; any pinned
   contract-field test updated.
3. **`orchestrator.md`'s extended budget sentence**: confirm the sentence, after a *second* mid-sentence
   clause insertion (B1's existing one plus B3's new one), still parses as one coherent, unambiguous rule
   — not two overlapping or contradictory clauses. This is a documentation-correctness check, not a code
   test, but worth an explicit reviewer verification step given it's editing a sentence already modified
   once.
4. **`reviewer.md`'s Blocking standard / evidence-prefix conventions**: a fixture-level check (or, at
   minimum, explicit reviewer verification) that a finding raised under condition 6 and a finding raised
   under the inconclusive path both carry the `"regression_gate: "` evidence prefix — the one convention
   this design relies on for human/audit traceability, given no schema field enforces it.
5. **Confirm no `state-schema.yaml`/`validate_loop_lifecycle.py` drift**: an explicit negative check (diff
   review) that neither file was touched — three prior review rounds each proposed and then reverted a
   change here; a careless implementation could reintroduce one by habit.

## Operational impacts

| Impact | Detail |
|--------|--------|
| **~4x Reviewer-dispatch cost for every regression-gate-carrying task** | By deliberate design, after three consecutive attempts to cache the deterministic base-commit half each failed against this skill's own Reviewer-isolation architecture. Both lenses (Lens A, Lens B) independently run the full dual-worktree, dual-dependency-install procedure on every dispatch, every generation, including every dirty-review rerun. Disclosed worst case: ~600 minutes across a task's full lifecycle (30 min initial Builder dispatch + 4 generations × 120 min Reviewer time + 3 × 30 min Builder remediation), against the skill's own 180-minute default per-task ceiling — hence the design's explicit recommendation to raise `max_task_elapsed_minutes` to ≥630 for any task carrying this field. This is a real, load-bearing operability change to how expensive a bug-diagnosis-originated fix task becomes, not a cosmetic addition, and should be communicated to whoever operates this pipeline day-to-day. |
| Second mid-sentence extension of the same `orchestrator.md` budget bullet | Documentation-maintainability note: this exact sentence has now been extended twice (B1, then B3) for two unrelated sub-steps. A third future extension should consider whether the sentence has become unwieldy enough to warrant restructuring into a small table instead of continued inline clauses — not blocking for this ticket, but worth flagging for whoever maintains this file next. |
| Historical-commit execution surface increases | Every regression-gate-carrying task now executes test-runner code at a historical commit up to 8 times (2 lenses × 4 generations, no caching) instead of never. This is the design's own honestly-disclosed residual risk (no documented sandboxing exists for Reviewer execution at base or head) — an operational fact worth the repo owner's awareness, not a defect in this design specifically. |
| No rollback complexity | Purely additive at every layer; a clean revert with no data migration in either direction. |

## Review triggers

**`security`: recommended, non-blocking, given a specific residual concern the design itself discloses
but doesn't fully close.** The command validator alone went through 4 rounds of dedicated adversarial
Security Architect review across this design's revision history, each round finding and closing a real,
distinct file-write/injection bypass (wrong regex capture group, incomplete `=`-splitting, missed
colon-delimiter syntax) before converging on a delimiter-agnostic substring-search approach, independently
re-verified by direct execution in round 6. This is a materially higher bar than this session's own
change-impact analyses typically apply for "was security already covered" (compare B2's reasoning, which
similarly declined a fresh `security-review` dispatch on the strength of its own adversarial rounds) — the
same logic applies here with, if anything, stronger grounding, since this exact function's real,
demonstrated exploitability (not hypothetical) was found and fixed 4 separate times by that same review
process. **Recommendation: do not re-trigger a fresh, independent `security-review` pass** — it would
re-litigate ground this design's own review process already covered at higher intensity and with more
concrete, executed proof-of-bypass evidence than a standard specialist pass typically produces. The one
disclosed, NOT-closed residual (test-runner extensibility via `conftest.py`/Makefile recipes/npm lifecycle
hooks, and no sandboxing at all for historical-commit execution) is structural — no command-validator
design can close it, and a specialist security-review pass would reach the identical conclusion this
design's own six rounds already reached. Recorded here explicitly so the decision not to re-trigger is a
reasoned one, not an omission.

No other specialist category (`api`, `database`, `performance`, `capacity`, `observability`, `resilience`,
`dependency_upgrade`) is triggered — this change has no API surface, no schema/database change, no runtime
capacity/observability/resilience/dependency-manifest surface.

## Unknowns

1. **The 60-minute doubled budget figure and the ≥630-minute per-task-ceiling recommendation are both
   estimates**, not measured against this repository's actual dependency-install/test-suite runtime —
   explicitly disclosed as such in the design's own Open Questions, not resolved by this analysis.
2. **The exact literal content of `reference/lightweight-path.md`-equivalent doc edits** (the specific
   prose for `reviewer.md`'s new subsection, `builder.md`'s new subsection, `bug-diagnosis`'s doc updates)
   is specified in shape by the design but not written verbatim here — normal for a change-impact
   analysis, produced during implementation from the design's own literal templates.
3. **Whether `orchestrator.md`'s twice-extended budget sentence remains grammatically coherent** after
   both insertions — flagged as Required test 3 above rather than assumed either way.

## Evidence refs

- `docs/superpowers/specs/2026-09-29-b3-regression-gate-architecture-review.md`
- `docs/superpowers/specs/2026-09-29-b3-regression-gate-design.md` (revision 6, full 6-round revision
  history)
- `skills/loop-task-implementer/workflow/{reviewer,orchestrator,builder}.md` (direct reads across all 6
  review rounds)
- `skills/loop-task-implementer/reference/state-schema.yaml`, `scripts/validate_loop_lifecycle.py`
  (confirmed untouched by the final design)
- `skills.yaml` (confirmed exact field/registration-surface locations for both new fields)
- `docs/skill-framework/shared/cross-skill-escalation.md` (existing rows 138, 199)
- `CODEOWNERS` (confirms existing root-wildcard coverage)
- `docs/superpowers/specs/2026-09-29-b2-lightweight-plan-path-*.md` (B2's own precedent for the
  registry two-surface pattern and the "already reviewed adversarially, don't re-trigger security-review"
  reasoning this report reuses)
