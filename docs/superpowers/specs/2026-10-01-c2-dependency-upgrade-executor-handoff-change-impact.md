# Change Impact Report — C2: dependency-upgrade-review → executor handoff

**Coverage status: COMPLETE** (repository read available; target repo `luckyrjain/software-builder`,
assessed against `origin/main`, which includes C1/#320, B8/#319, B7/#318 — local `main` is behind but a
clean ancestor, not diverged)

## Assessment target

`docs/superpowers/specs/2026-10-01-c2-dependency-upgrade-executor-handoff-design.md` (revision 4, "Ready
with open questions") — 3 adversarial rounds + 1 narrow confirmation pass across Security Architect, SRE,
Software Architect, fully converged. Artifact state: `proposed_state`.

## Criticality

**Medium-high.** Touches `skills/loop-task-implementer/workflow/reviewer.md`'s shared Blocking standard
(consumed by every task this skill ever dispatches, not just dependency-upgrade-origin ones) and
`workflow/builder.md`'s step-1 entry point (same universality). Mitigated: both changes are additive
(a new condition number, a new named sub-section gated on a field that's only ever `true` for this one
handoff's own tasks) — no existing behavior for non-dependency-upgrade tasks changes.

## Change classes

- **New code** (2 files): `classify_dependency_upgrade.py`, `verify_dependency_hop_precondition.py` —
  both pure or near-pure, no network, no mutation of shared state.
- **New tests** (2 files): one per new function, mirroring C1's `test_classify_security_finding.py`
  precedent exactly (confirmed real on `origin/main`).
- **New documentation** (1 file): `dependency-upgrade-handoff.md`, mirroring C1's
  `security-review-handoff.md` precedent exactly (confirmed real on `origin/main`).
- **Additive doc/workflow edits** (3 files): a new row pair in `cross-skill-escalation.md`; a new named
  sub-section in `builder.md`; a new Blocking-standard condition + evidence-prefix convention in
  `reviewer.md`.
- **No schema/registry change**: `state-schema.yaml`, `composition_contracts.yaml`, `skills.yaml` all
  confirmed untouched by the design — this handoff reuses the legacy `implementation_task` envelope
  bypass, the same shape as C1, B6, B8.

## Impacted services / components

| Component | Impact | Evidence |
|---|---|---|
| `skills/loop-task-implementer` (Builder role) | New step-1 sub-section, gated on `specialist_inputs.dependency_upgrade_origin`; every other task type's own step-1 flow is unaffected | `builder.md:71` confirmed real heading `## 1. Understand before changing code` on `origin/main` |
| `skills/loop-task-implementer` (Reviewer role) | New Blocking-standard condition 8, applies only to tasks with `dependency_upgrade_origin: true`; conditions 1-7 unchanged | `reviewer.md` confirmed real on `origin/main`: conditions 1-7 exist (7 is C1's own, landed via PR #320), 8 is free |
| `skills/dependency-upgrade-review` | Gains a documented downstream consumer; the skill itself (report format, verdict vocabulary) is unmodified | `report-format.md`'s 4-state verdict, CVE table (`CVE|Affects|Fixed in|Severity`, no `Source` column), and CVE-caveat text all confirmed read, not edited |
| `docs/skill-framework/shared/cross-skill-escalation.md` | New row pair; no existing row edited | Confirmed via direct read: only `security-review ↔ dependency-upgrade-review` rows exist today, no `dependency-upgrade-review → loop-task-implementer` row |
| `skills/backlog-runner` | **Explicitly not integrated** — design's own scope boundary keeps multi-hop chains out of backlog-runner's automated batch-picking entirely (confirmed against `queue-policy.md` §2 rules 3-4: backlog-runner's dependency gate requires a dependent ticket's content to pre-exist with a declared `dependencies:[]`, which a hop whose content comes from a fresh `dependency-upgrade-review` re-invocation cannot satisfy) | No file in this skill is touched; zero coupling introduced |

## Impacted contracts

- `implementation_task` (legacy envelope, 16 real fields confirmed at `composition_contracts.yaml` on
  `origin/main`) — **no schema change**; `specialist_inputs` gains new *keys* within its existing
  freeform-dict contract (`dependency_upgrade_origin`, `cve_training_cutoff_caveat`,
  `dependency_chain_id`, `hop_index`, `expected_current_version`, `expected_target_version`) — the same
  pattern C1 used for `security_origin`, not a contract-breaking change.
- `reviewer.md`'s finding output schema — **unchanged**, confirmed by the design explicitly (new condition
  8 and its evidence-prefix convention are content-only, the same discipline as condition 6/7).
- `dependency_upgrade_report` (from `dependency-upgrade-review`) — consumed, not modified; its 4-state
  verdict vocabulary and table structures are read-only inputs to this handoff.

## Impacted data

None — no new persisted state. `dependency_chain_id`/`hop_index` live only inside a given hop's own
`implementation_task.specialist_inputs`, never in `state-schema.yaml` or any durable composition artifact
(confirmed: the design explicitly keeps `reference/state-schema.yaml` untouched).

## Impacted dependencies

None external. Internal: the design's `canonical_payload_digest()` reuse (confirmed real at
`scripts/registry/assessment_target.py:13`) is a read-only call into existing code, not a new dependency
edge requiring its own review.

## Impacted owners

Single repo, single maintainer (per CODEOWNERS: `/scripts/` → `@luckyrjain`; no narrower CODEOWNERS entry
for `skills/loop-task-implementer/` itself, consistent with every prior ticket this session). No new
CODEOWNERS entry needed, mirroring the established pattern.

## Required tests

1. **`test_classify_dependency_upgrade.py`** (new) — exact-match positive cases for both qualifying
   states, exact-match negative cases for both non-qualifying states, fail-closed case for an unrecognized
   string, and the extraction-regex contract itself: the real rendered `**Verdict: <state>**` line for
   all four states, with the em-dash (U+2014) literal required for `"Blocked — insufficient info"`.
2. **`test_verify_dependency_hop_precondition.py`** (new) — match case, mismatch case, dependency-absent-
   from-lockfile case (fail-closed), and the design's own round-4 fallback case (no lockfile, exact-pin
   manifest).
3. **Explicit diff-review confirmation** (mirrors this session's own established "confirm the did-not-
   touch list" convention from B3/C1) that `workflow/orchestrator.md`, `workflow/lifecycle-gate.md`,
   `scripts/validate_loop_lifecycle.py`, `reference/state-schema.yaml`,
   `scripts/registry/composition_contracts.yaml`, `skills.yaml`, and every file under
   `skills/backlog-runner/` are unchanged by the implementing PR.
4. **Existing parity tests must still pass unmodified**: `test_packaged_runtime_isolation.py` (confirms
   `scripts/` packages wholesale — no new per-file registration needed, consistent with C1's own
   `classify_security_finding.py` requiring none) and any existing `reviewer.md` Blocking-standard parity
   test, if one enumerates condition count/text (none found referencing a fixed condition count during
   this analysis — flagged as a material unknown below, not assumed absent).

## Operational impacts

- **None at runtime** for any task not originating from this handoff — both new workflow-doc changes are
  conditionally gated.
- **Human/Orchestrator-paced operability cost** for a multi-hop chain (disclosed in the design's own
  Capacity/Failure-strategy sections) — each hop is a separate, manually-dispatched
  `loop-task-implementer` invocation; no automated scheduling or reminder exists.
- **Blocking-standard numbering is now sequential, cross-ticket state** (C1 claimed 7, this design claims
  8) — confirmed real and correct as of this analysis, but **any future Epic-C ticket (C3-C8) that also
  needs a new Blocking-standard condition must re-check the real current max in `reviewer.md` at design
  time, not assume a number from a design doc alone** — this design doc itself only discovered its
  original "mirrors condition 7" claim was wrong through round-2 adversarial review, not by first-pass
  convention; flagged here so the next ticket doesn't repeat that discovery cost.

## Review triggers

**None required beyond this design's own already-completed adversarial history.** Reasoned explicitly,
not silently omitted: the security-relevant surface of this change (citation-by-reference discipline for
untrusted `changelog_text`/`manifest_excerpt`, fail-closed classification, fail-closed lockfile-extraction
default, the CVE-caveat carry-forward) was already covered across 3 full adversarial rounds plus a
dedicated Security Architect pass each round, substantially exceeding this skill's own
`security-review` trigger bar for a change of this size and shape (two small, mostly-pure functions and
three additive documentation edits). No new trust boundary, new external I/O, or new persisted state is
introduced. A fresh `security-review` of the implemented diff is still advisable at ordinary
Reviewer-lens depth (Lens A already covers this), but is not called out here as a mandatory specialist
trigger beyond that.

## Unknowns / material unknowns

1. **Whether `reviewer.md` has an existing parity test enumerating the Blocking-standard's condition
   count or exact text** (e.g. the way `run-log.md`'s event/reason-code enumeration has a wired parity
   test per this session's own B3/B5 history) — not found during this analysis within the read budget;
   if one exists, it must be updated in the same PR or it will fail, the same risk class B3/B5's own
   change-impact reports flagged for their own target files.
2. **The design's own disclosed residuals** (lockfile-extraction gap for monorepo/non-listed ecosystems,
   `max_files_per_run:5`'s unvalidated absolute sufficiency, hop-ordering convention-not-code-enforced,
   no automated chain-abandonment tracking, "tests pass" not evidence against dependency-internal
   security regressions) are carried forward here as known, accepted risk — not blocking, not silently
   dropped, each already honestly disclosed in the design's own Open questions.
3. **Whether any other skill's own documentation references `reviewer.md`'s Blocking standard by a fixed
   condition count** (e.g. a tutorial or onboarding doc stating "7 conditions") was not exhaustively
   grepped across the full repository within this analysis's bounded scope; a targeted grep for a literal
   count during implementation is recommended.

## Evidence refs

- `docs/superpowers/specs/2026-10-01-c2-dependency-upgrade-executor-handoff-design.md` (revision 4)
- `docs/superpowers/specs/2026-10-01-c2-dependency-upgrade-executor-handoff-architecture-review.md`
- `origin/main`: `skills/loop-task-implementer/workflow/reviewer.md` (conditions 1-7 confirmed, 8 free),
  `skills/loop-task-implementer/workflow/builder.md:71` (`## 1. Understand before changing code`
  confirmed real), `skills/loop-task-implementer/scripts/classify_security_finding.py` +
  `tests/test_classify_security_finding.py` (C1's precedent, confirmed real),
  `docs/skill-framework/shared/security-review-handoff.md` (C1's reference-doc precedent, confirmed real),
  `docs/skill-framework/shared/cross-skill-escalation.md` (confirmed no existing target row),
  `scripts/registry/composition_contracts.yaml` (16-field `implementation_task` confirmed),
  `skills/backlog-runner/reference/queue-policy.md` §2 rules 3-4 (dependency-gate shape confirmed),
  `skills/dependency-upgrade-review/reference/report-format.md` (verdict/CVE-table/caveat text confirmed),
  `scripts/registry/assessment_target.py:13` (`canonical_payload_digest` confirmed),
  `skills/loop-task-implementer/tests/test_packaged_runtime_isolation.py` (packaging-wholesale confirmed)
- `git log origin/main` — confirmed C1 (`d435b24`/#320) did not touch `builder.md`; the commits that did
  (`d74b3fd` B7, `b7f8714` B3, `627a0fa` A5, the run-log-hardening commit, the skills-move commit) are all
  unrelated to this ticket — C2 is the first ticket to insert content at the top of builder.md's step 1.
