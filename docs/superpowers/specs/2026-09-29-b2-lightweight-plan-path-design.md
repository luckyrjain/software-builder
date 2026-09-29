# System Design Spec — B2: lightweight ticket → plan path for small tasks

**Readiness: Ready with open questions**

## Revision history

- **Revision 1**: closed all 5 architecture-review conditions on paper. Round 1 (3 personas) returned
  NEEDS REVISION x3 — 7 blocking findings (registry schema omission, resume-time backward-compat break,
  broken stub wrapper shape + wrong `target_paths` location, eligibility vocabulary not code-enforced,
  `CONFIG_VALUE_ONLY` CI/permissions gap, circular "no specialist trigger" self-cert, weak `asserted_by`).
- **Revision 2**: fixed all 7. Round 2 found 4 new ones introduced by revision 2 itself: denylist omitted
  dependency manifests; `build_implementation_plan`'s wiring was asserted in prose only, no real code;
  **plan-identity collision** — stub templates had zero per-invocation entropy, so two distinct
  `LIGHTWEIGHT` tasks sharing category/paths silently collided on `plan_set_id`/`plan_id`; denylist
  bypassable via `./`-prefixed/doubled-separator paths.
- **Revision 3**: fixed the wiring and denylist findings with real code; attempted to fix the collision
  with a caller-computed `sha256(task_id|category|asserted_by|target_paths)` digest override. Round 3 (3
  fresh personas, told to re-verify everything, not trust the "fixed" framing) found this attempted fix
  was **broken on two independent grounds**:
  1. **[Security Architect]** Circular — `task_id` doesn't exist until *after* the digest that determines
     `plan_id`/`task_id` is computed (`task_id` is derived from `plan_id`, `implementation_plan.py:582`).
     Also unenforced in code — nothing checks a caller actually followed the formula.
  2. **[SRE, most serious]** Even a well-formed version would break legitimate crash-and-resume: Fix 5
     required embedding a session/run-id inside `asserted_by`, and Fix 4 hashed `asserted_by` into the
     identity-bearing digest — but this repo's own architecture (`plan_state_store.py`, `run-log.md`)
     deliberately issues a *new* run-id on every resume, specifically so `plan_id`-keyed durable state
     survives that boundary. Embedding run-id in the digest defeats the exact mechanism
     `plan_state_store.py` exists to provide.
  Round 3 also found (both Software Architect and SRE, independently) that the `validate_implementation_plan`
  backward-compat carve-out — described in revision 2 with real code — had its literal code **dropped**
  when revision 3 renumbered the fixes, while the call site still referenced the now-undefined
  `effective_plan` variable. A real regression introduced by the rewrite itself, not a design flaw.
  Suggestions: dependency-manifest basename matching would false-positive on this repo's own legitimate
  test fixtures; case-sensitive basename comparison could be evaded on a case-insensitive filesystem;
  backslash-separated paths weren't normalized; Fix 8's cited precedent needed a more precise citation.
- **Revision 4**: replaced the sha256-formula approach with natural content entropy in the stub payloads
  (no caller-computed digest at all) and restored the backward-compat carve-out as real code. Round 4 (3
  fresh personas) returned CLEAN from Security Architect and Software Architect, but SRE found one more
  real bug in the identical failure family:
  - **[SRE]** `canonical_plan_digest(plan)` (`implementation_plan.py:149-151`) hashes the *entire* plan
    dict, no exclusions — confirmed by direct read. Fix 4 correctly kept `asserted_by` out of
    `plan_id`/`plan_set_id` derivation, but `planning_path` (including `asserted_by`) is still a top-level
    key of `plan` itself, so it flows into `canonical_plan_digest` — the digest
    `skills/implementation-planner/SKILL.md:45-46` names as part of the resume contract, and the one
    `validate_plan_execution_state`/`reconcile_plan_state` compare against the durable checkpoint. Since
    Fix 5 still required `asserted_by` to carry a session/run-id, and this repo deliberately issues a new
    run-id on every resume, a genuine crash-and-resume would still change `canonical_plan_digest`, breaking
    execution-state reconciliation and — via `execution_identity`, which also consumes this digest — risking
    a silently duplicated branch/PR per resume. Round 3's bug, recurring one layer down, in a place none of
    the first three rounds were positioned to catch (they weren't yet exercising `LIGHTWEIGHT`'s
    `asserted_by` shape against the resume/execution-identity chain specifically).
- **Revision 5**: removed the session/run-id from `asserted_by` entirely, making it pure stable rationale
  text so `canonical_plan_digest` is stable across resume by construction. Round 5 (SRE) confirmed the
  digest-stability fix genuinely holds, but found the compensating claim in that revision — "session/run-id
  audit tracking already exists via `run_log.py`" — was **factually wrong**: `implementation-planner` has
  zero integration with `run_log.py` (confirmed by grep, zero hits), and `run_log.py`'s tracked run only
  begins later, at `loop-task-implementer`'s task-selection step, strictly after the plan (with its
  `planning_path` already fixed) already exists as a *consumed input* to that orchestrator run. So
  stripping the session-id from `asserted_by` left the architecture review's Condition 4 ("who/what
  asserted it") genuinely unsatisfied, not satisfied-elsewhere as claimed — a real regression introduced by
  revision 5's own fix, not a re-litigation of anything closed in rounds 1-4.
- **Revision 6**: attempted to restore "who/what asserted it" via a new `plan_execution_state` field
  (`planning_session_id`), reasoning that the mutable runtime checkpoint is structurally separate from the
  digest-hashed `plan` document. Round 6 (SRE) found this **broke LIGHTWEIGHT plans outright** — two
  compounding blocking defects:
  1. The new parameter was only added to `initial_plan_execution_state`, but the actual sole durable write
     entry point is `plan_state_store.cas_advance` (its own docstring: "the only write entry point"), which
     calls `initial_plan_execution_state` internally with no way to pass the new value through — so the
     field would always be `None` in practice, and the paired validator (requiring it non-empty for
     `LIGHTWEIGHT`) would then reject every `LIGHTWEIGHT` plan's very first checkpoint write.
  2. Adding a *required* member to `EXECUTION_STATE_FIELDS` with no backward-compat carve-out reintroduced
     round 1's original bug class one structure over — every already-in-flight `plan_execution_state`
     checkpoint on disk at deploy time (`FULL` mode too, not just `LIGHTWEIGHT`) would fail both
     `validate_plan_execution_state`'s and `plan_state_store._parse_state_file`'s strict field-set checks.
  Six rounds of attempting to embed this identity into structured, digest-hashed, or CAS-validated state
  (the plan itself, then its resume digest, then the execution-state checkpoint) each broke something new.
- **Revision 7**: stopped trying to store "who/what asserted it" in any machine-validated structure —
  moved it to the PR description instead, zero new code, zero interaction with
  `canonical_plan_digest`/`EXECUTION_STATE_FIELDS`/CAS. Round 7 (SRE) found this picked an artifact that
  isn't actually guaranteed to exist: `orchestrator.md:162-190`/`builder.md:184-189` confirm
  `allowed_actions.create_pr` **defaults to `false`**, and when it's false the Builder stops after
  producing a diff and never opens a PR at all — so on the fail-safe default path, the record wouldn't
  just be unenforced, it would have no home whatsoever. `report-template.md`, by contrast, is produced
  unconditionally for every task "whether it completes, stops at verified readiness, or escalates" —
  confirmed by direct read.
- **Revision 8**: moved the requirement from the PR description to the universal completion report instead
  — same zero-code property, but on an artifact that's never conditional on repository-write authorization.
  Round 8 (SRE) found the completion-report line has no data to draw on: Fix 5 (still in force) deliberately
  strips all session/run-id content out of `asserted_by` to keep `canonical_plan_digest` stable across
  resume, so nothing in the plan artifact carries planning-time identity forward. Worse in the confirmed
  cross-session case (`implementation-planner`'s own `SKILL.md:44`, "the executor is always
  loop-task-implementer" — planning and execution are separable steps, routinely different sessions per
  this repo's own fresh-context convention): the *executing* session writing the completion report has no
  way to know who made the *planning-time* judgment, so a filled-in line would report its own identity as
  if it were the planner's — a false record, worse than an absent one.
- **Revision 9**: tried to capture identity *at the moment of assertion* via git commit provenance on the
  plan document, reasoning this repo's own practice already commits every design/architecture-review
  artifact. Round 9 (SRE) found this conflated *this authoring session's own manual habit* of committing
  its spec docs with *the skill pipeline's actual, documented contract* — `implementation-planner`'s
  `workflow/plan.md` §4 says only "pass `implementation_plan` to `loop-task-implementer`," the whole
  producer→consumer chain is in-memory and digest-addressed (`source_refs` are `name:digest` pairs, not
  file paths), and `implementation-planner` has no repository-write capability at all to perform a commit
  even if the design wanted it to. Worse: nothing would link a specific commit back to a specific
  execution, and unlike every other disclosed residual risk in this design, a skipped commit would have
  **no backstop** — `loop-task-implementer`'s review lenses examine the diff, never planning provenance.
- **Revision 10** (this version, final): stops inventing new machinery for this one field. Checked whether
  *any* report type in this pipeline captures author/session identity in-band — grepped
  `composition_contracts.yaml`'s full field lists for `architecture_review_report`, `system_design_spec`,
  `change_impact_report`: none of them do, for the `FULL` path or otherwise. "Who/what asserted it" is not
  a gap B2 introduces; it's a pre-existing, systemic property of this entire reporting pipeline, which never
  tracked report authorship in-band for any artifact type. Nine rounds tried to build new machinery to make
  the `LIGHTWEIGHT` path stronger on this one axis than the `FULL` path already is — each attempt broke
  something real. The honest fix is to stop, and disclose the limitation plainly rather than keep inventing
  a tenth mechanism. Detailed below.

## Grounding note

`scripts/implementation_plan.py` **already** has a caller-supplied, planning-time size-estimate channel
(`repository_evidence.estimated_scope`) and **already** enforces the exact `orchestrator.md:319-322`
hard-stop numbers (`LOOP_TASK_MAX_FILES = 40`, `LOOP_TASK_MAX_LINES = 1500`) against a caller-declared
known estimate at plan-build time (`_validate_estimate`, `implementation_plan.py:664-701`). Conditions 3
and 5 close via this existing mechanism, unchanged across every revision. Conditions 1, 2, and 4 required
the fixes below.

## Components

| Component | Responsibility | Boundary / owns | Notes |
|-----------|-----------------|------------------|-------|
| `implementation-planner` (unchanged code path) | Accepts caller-supplied stub or real reports with zero added judgment logic | Stays a read-only leaf | |
| `implementation_plan.py` (new: `planning_path` field + `_validate_planning_path` + `build_implementation_plan` wiring) | Records, on every freshly-built plan, whether `FULL` or `LIGHTWEIGHT` evidence produced it, enforces the mechanically-checkable eligibility gates | New constants + validator + builder wiring | Addresses Conditions 1, 4 |
| Caller (Orchestrator / human driving the ticket) | Judges eligibility, builds genuinely task-specific stub payloads, supplies a known `estimated_scope` | Sole owner of the eligibility *judgment* | Addresses Conditions 1, 2, 5 |
| `skills/implementation-planner/reference/lightweight-path.md` (new doc) | Eligibility allowlist prose, exact stub payload shape, code-enforced gates | Kept in sync with code by a new parity test | Addresses Conditions 1, 2, 3 |
| `loop-task-implementer`'s review lenses (unchanged) | Independently review the resulting diff regardless of planning path | Unaffected — backstop for the disclosed circularity residual risk | |

## APIs

### Fix 1 (unchanged since revision 2) — registry schema

`skills.yaml`'s `implementation_plan` artifact schema gains `planning_path` in both its `fields` list and
its `payload_types` map (a second, independently-enforced registration surface —
`artifact_contracts.py:141-150` requires `set(payload_types[artifact]) == set(fields)`). Regenerated via
`make generate`. `test_implementation_plan_v1_contract_fields` gets its expected list updated. Confirmed
(round 2, SRE, ran it directly): no lint/drift job re-validates historical plan JSON against this schema —
safe as scoped.

### Fix 2 (unchanged since revision 3, re-confirmed round 3) — `build_implementation_plan` wiring

```python
# build_implementation_plan, near the existing `estimate = evidence.get("estimated_scope")...` block
# (implementation_plan.py:561-563):
caller_planning_path = evidence.get("planning_path")
planning_path = (
    caller_planning_path if isinstance(caller_planning_path, Mapping)
    else {"mode": "FULL", "eligibility_category": None, "asserted_by": None}
)
```

```python
# inside the `plan = {...}` literal (implementation_plan.py:631-647), one new key:
plan = {
    "plan_set_id": plan_set_id, "plan_id": plan_id, "title": ..., "readiness": readiness,
    "assessment_target": {...}, "target_repo": normalized_repo,
    "external_dependencies": copy.deepcopy(external_dependencies), "source_refs": source_refs,
    "tasks": tasks, "execution_waves": waves, "sequencing_constraints": [...],
    "verification_gates": [...], "traceability": traceability,
    "planning_path": planning_path,   # <-- new
}
```

`build_implementation_plan` has no early-return path anywhere in its body (confirmed by direct read,
`implementation_plan.py:422-657`), so this assignment executes unconditionally, `FULL` or `LIGHTWEIGHT`.
Lands in the same atomic commit/PR as Fix 1 — no window where the registry requires the field before the
code produces it (confirmed round 3, Software Architect: no separate deploy step in this repo's release
tooling could apply them out of order).

### Fix 3 (unchanged since revision 2, re-confirmed twice) — corrected stub payload wrapper shape

Every stub is wrapped as `{"skill_result": {"status": "SUCCESS"}, "payload": {...}}`, matching this
codebase's real fixture convention. `change_impact_report`'s `payload` carries `target_paths` at the top
level and `coverage_status: "COMPLETE"`. See Fix 4 below for the current literal templates.

### Fix 4 (revision 4, replaces revision 3's broken sha256-digest approach) — plan-identity uniqueness via natural content entropy, not a caller-computed formula

**Why the digest-formula approach is abandoned:** round 3 found it circular (referenced `task_id`, which
doesn't exist until after the digest that determines `plan_id`/`task_id` is computed) and, even fixed,
run-boundary-fragile (embedding a session/run-id — required by Fix 5 — inside the identity-bearing digest
broke legitimate crash-and-resume, since this repo's own architecture deliberately issues a new run-id on
every resume). Both problems trace to the same root mistake: trying to manufacture uniqueness via an
artificial, caller-computed override, instead of letting the plan's **real content** vary the way a
genuine (non-stub) `system_design_spec`/`architecture_review_report` naturally would.

**The actual fix:** stop overriding `assessment_target.source_artifact_digest` entirely. `_source_digest`
(`implementation_plan.py:344-358`) already falls back to `canonical_payload_digest(payload)` — a hash of
the payload's own real content — whenever no override is supplied. Round 2's original bug was that the
`system_design_spec`/`architecture_review_report` stub payloads carried zero task-specific content (only a
category-boilerplate `title`, no `target_paths`), so that fallback hash was identical across every task in
a category. The fix is to give those payloads genuine content instead of inventing a parallel identity
mechanism:

- **Embed the actual `target_paths` list** in all three stub payloads (previously only `change_impact_report`
  had it) — this alone distinguishes any two invocations touching different files.
- **Require `title` to be a genuinely task-specific one-line description of the real change** (e.g. `"Bump
  numpy to 1.26.4 in requirements.txt"`), not `eligibility_category` boilerplate — this is the entropy
  source for the case round 2 actually found: two *different* tasks touching the *same* file(s). A
  legitimate retry of the *same* logical task reuses the *same* description verbatim (same content → same
  digest → same plan identity → safe idempotent CAS resume, with **no run-id anywhere in the hashed
  content**, so it survives exactly the resume-after-new-run-id scenario Fix 4's prior version broke).

This is deliberately *not* code-enforced beyond `non_empty_str` (whether a `title` is genuinely accurate,
task-specific text can't be machine-verified any more than `eligibility_category`'s semantic truth can) —
disclosed as an accepted residual limitation, same bucket as the "no specialist trigger" self-cert. What it
does guarantee, unconditionally: no *structural* collision mechanism exists anymore (revision 3's bug was
that two different tasks were **guaranteed** to collide whenever paths matched; under this fix, collision
requires the caller to *also* reuse identical description text for a genuinely different task — a much
narrower, self-evident-in-the-emitted-plan failure mode, and the same kind of trust the `FULL` path has
always placed in real report authors).

### Fix 5 (revision 5, closes round-4 SRE's finding) — `asserted_by` carries no run-scoped content at all

Revision 4 kept `asserted_by` out of `plan_id`/`plan_set_id` derivation but still required it to embed a
session/run-id, and `asserted_by` lives inside `planning_path`, a top-level key of `plan` itself —
`canonical_plan_digest(plan)` (`implementation_plan.py:149-151`) hashes the *entire* plan dict, no
exclusions, so the run-id still reached the resume-matching digest one layer down. Rather than teach
`canonical_plan_digest` (a small, shared, already-heavily-used function) a new exclusion — which would need
to be kept in lockstep with `plan_id`'s own separate exclusion forever, the same duplication risk that
caused this bug in the first place — **`asserted_by` simply never contains run-scoped content**:

`asserted_by` is now purely stable rationale text: `"<one-line reason citing the specific target_paths and
why the category applies>"` — no session/run-id component. This makes `planning_path` as a whole
content-stable across any resume of the same logical task, so `canonical_plan_digest` is stable by
construction, with no new code needed to make it so and no exclusion logic to keep in sync with anything
else.

`asserted_by` doesn't need to carry a session/run-id itself; doing so is exactly what created this bug
(round 4). **Correction, round 5→10:** the claim that once stood here — that `run_log.py` independently
covers planning-time session/run-id audit tracking — was found factually wrong in round 5
(`implementation-planner` has zero integration with `run_log.py`) and is not resurrected by any later
revision. See Fix 11 for where "who/what asserted it" actually ends up: disclosed as not captured in-band
anywhere in this pipeline, not silently covered elsewhere.

### Fix 6 (revision 4) — corrected stub templates

```json
// system_design_spec stub
{
  "skill_result": { "status": "SUCCESS" },
  "payload": {
    "title": "<genuine one-line description of the real change, e.g. \"Bump numpy to 1.26.4 in requirements.txt\">",
    "readiness": "ready",
    "assessment_target": { "repo": "<owner/repo>", "target_paths": ["<path1>", "..."] },
    "normalized_decision": { "status": "READY" },
    "findings": [], "conditions": [], "required_actions": [],
    "evidence_refs": ["lightweight-plan-path:v1", "eligibility:<eligibility_category>"]
  }
}
```

```json
// architecture_review_report stub — same shape, "decision" in place of "readiness", SAME title text
{
  "skill_result": { "status": "SUCCESS" },
  "payload": {
    "title": "<identical to the system_design_spec stub's title>",
    "decision": "Approved",
    "assessment_target": { "repo": "<owner/repo>", "target_paths": ["<path1>", "..."] },
    "normalized_decision": { "status": "READY" },
    "findings": [], "conditions": [], "required_actions": [],
    "evidence_refs": ["lightweight-plan-path:v1", "eligibility:<eligibility_category>"]
  }
}
```

```json
// change_impact_report stub — SAME title text; top-level target_paths; coverage_status MUST be "COMPLETE"
{
  "skill_result": { "status": "SUCCESS" },
  "payload": {
    "title": "<identical to the other two stubs' title>",
    "assessment_target": { "repo": "<owner/repo>" },
    "coverage_status": "COMPLETE",
    "material_unknowns": [],
    "impacted_repositories": ["<owner/repo>"],
    "criticality": "Low",
    "change_classes": ["<eligibility_category>"],
    "impacted_services": [], "impacted_contracts": [], "impacted_data": [],
    "impacted_dependencies": [], "impacted_owners": [],
    "target_paths": ["<path1>", "..."],
    "required_tests": ["<any test the caller already knows must pass>"],
    "operational_impacts": [],
    "review_triggers": [],
    "unknowns": [],
    "evidence_refs": ["lightweight-plan-path:v1", "eligibility:<eligibility_category>"]
  }
}
```

Re-traced end to end: `_payload(source)` returns `source["payload"]` for all three. `change_impact_report`
resolves non-blocking status via `execution_status = "SUCCESS"` (no `normalized_decision`/`readiness` in
its real schema). The other two resolve via `execution_status = "SUCCESS"` too (`_source_status`'s own
priority order returns `execution_status` once `decision_status` isn't blocking). None of the three declare
`assessment_target.source_artifact_digest`, so `_source_digest` falls through to `canonical_payload_digest`
on each payload's real content — which now varies by `title` and `target_paths`, both genuinely
task-specific.

### Fix 7 (revision 4, closes both round-3 findings on the denylist) — path normalization and denylist, hardened

```python
ELIGIBILITY_CATEGORIES = {
    "CONFIG_VALUE_ONLY", "DOC_ONLY", "ADDITIVE_TEST_ONLY", "MECHANICAL_PRECEDENT_APPLICATION",
}
PLANNING_PATH_MODES = {"FULL", "LIGHTWEIGHT"}
PLANNING_PATH_FIELDS = {"mode", "eligibility_category", "asserted_by"}

_LIGHTWEIGHT_DENYLIST_PREFIXES = (".github/workflows/", ".claude/")
_LIGHTWEIGHT_DENYLIST_EXACT = {
    "CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS",
    "docs/github-ruleset-main.json", ".github/dependabot.yml",
}
_DEPENDENCY_MANIFEST_BASENAMES = {
    "requirements.txt", "requirements.lock", "pyproject.toml",
    "package.json", "package-lock.json",
    "cargo.toml", "cargo.lock", "go.mod", "go.sum", "gemfile.lock",   # compared lower-cased
}
_TEST_FIXTURE_SEGMENT = "tests/fixtures/"

def _normalize_lightweight_path(path: str) -> str:
    # Round 3, SRE: backslash-separated paths are valid caller input (_validate_task itself
    # normalizes them for its own shape check) — convert first, then strip "./" and collapse "//",
    # matching in a single canonical forward-slash form before any denylist/basename check.
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized

def _matches_lightweight_denylist(path: str) -> bool:
    normalized = _normalize_lightweight_path(path)
    basename = normalized.rsplit("/", 1)[-1]
    if normalized in _LIGHTWEIGHT_DENYLIST_EXACT or normalized.startswith(_LIGHTWEIGHT_DENYLIST_PREFIXES):
        return True
    # Round 3, Security Architect: a manifest basename under a tests/fixtures/ directory is inert
    # test data, never installed/executed as a real dependency declaration for this repo — exempt
    # it from the manifest check specifically (not from the CI/permissions checks above, which stay
    # absolute regardless of directory).
    if _TEST_FIXTURE_SEGMENT in normalized:
        return False
    # Round 3, SRE: compare case-insensitively -- a case-insensitive-but-preserving filesystem
    # (e.g. default macOS APFS) would otherwise let "Requirements.txt" evade a lower-cased list.
    return basename.lower() in _DEPENDENCY_MANIFEST_BASENAMES
```

```python
def _validate_planning_path(value, plan, errors):
    if not isinstance(value, Mapping):
        errors.append("error: planning_path must be a mapping"); return
    unknown = _safe_sorted(set(value) - PLANNING_PATH_FIELDS)
    missing = _safe_sorted(PLANNING_PATH_FIELDS - set(value))
    if unknown: errors.append(f"error: planning_path contains undeclared fields: {', '.join(unknown)}")
    if missing: errors.append(f"error: planning_path missing fields: {', '.join(missing)}")
    mode = value.get("mode")
    if mode not in PLANNING_PATH_MODES:
        errors.append("error: planning_path.mode must be FULL or LIGHTWEIGHT"); return
    if mode == "FULL":
        if value.get("eligibility_category") is not None or value.get("asserted_by") is not None:
            errors.append("error: FULL planning_path must have null eligibility_category and asserted_by")
        return
    category = value.get("eligibility_category")
    if category not in ELIGIBILITY_CATEGORIES:
        errors.append(f"error: planning_path.eligibility_category must be one of {sorted(ELIGIBILITY_CATEGORIES)}")
    if not non_empty_str(value.get("asserted_by")):
        errors.append("error: planning_path.asserted_by must be a non-empty string")
    all_paths = {path for task in plan.get("tasks", []) if isinstance(task, Mapping)
                 for path in task.get("target_paths", []) if isinstance(path, str)}
    if len(all_paths) > 3:
        errors.append(f"error: LIGHTWEIGHT planning_path allows at most 3 target_paths, found {len(all_paths)}")
    for path in all_paths:
        if _matches_lightweight_denylist(path):
            errors.append(f"error: {path} is never eligible for the LIGHTWEIGHT planning path (CI/permissions/governance/dependency-manifest)")
```

### Fix 8 (revision 4, closes both round-3 findings on this section) — the actual backward-compatibility carve-out, restored as real code, and its call site

Round 3 (Software Architect and SRE, independently) caught that revision 3's own rewrite dropped this
code while continuing to reference an undefined `effective_plan` variable at the call site — the exact
"named but not shown" defect this document has been correcting in other sections since round 1. Restored
here in full, using a simpler mechanism than either prior revision (adjusting only the *field-set used for
the unknown/missing diff*, never constructing a parallel plan dict):

```python
# validate_implementation_plan, replacing the existing unconditional two lines:
#   unknown = _safe_sorted(set(plan) - PLAN_FIELDS)
#   missing = _safe_sorted(PLAN_FIELDS - set(plan))
_DEFAULT_PLANNING_PATH = {"mode": "FULL", "eligibility_category": None, "asserted_by": None}
# planning_path is optional for backward compatibility with plans built before this field existed:
# absence is treated as implicit FULL for field-set validation only. This never mutates `plan` --
# only the SET of field names considered "present" is adjusted for this one diff.
present_fields = set(plan) if "planning_path" in plan else set(plan) | {"planning_path"}
unknown = _safe_sorted(present_fields - PLAN_FIELDS)
missing = _safe_sorted(PLAN_FIELDS - present_fields)
# ...rest of the function is completely unchanged, reading `plan` directly as it always has --
# confirmed (round 2, SRE) that no other check in this function reads planning_path...
```

```python
# near the end of validate_implementation_plan, alongside the existing _validate_source_readiness call:
_validate_planning_path(plan.get("planning_path", _DEFAULT_PLANNING_PATH), plan, errors)
```

A plan already on disk with no `planning_path` key validates exactly as before this change — `present_fields`
supplies the implicit default for the field-set diff, and `plan.get("planning_path", _DEFAULT_PLANNING_PATH)`
supplies the same default directly to `_validate_planning_path`, both without ever touching the caller's
`plan` mapping. No `effective_plan` variable is introduced anywhere, eliminating the class of bug round 3
found.

### Fix 11 (revision 10, final) — "who/what asserted it" is disclosed as not captured in-band, a pre-existing property of this entire pipeline, not a gap B2 introduces

Round 9 found that git commit provenance doesn't match how this pipeline actually moves an
`implementation_plan`: `implementation-planner`'s own `workflow/plan.md` §4 says only "pass
`implementation_plan` to `loop-task-implementer`" — the whole producer→consumer chain is in-memory and
content-digest-addressed (`source_refs` are `name:digest` pairs, never file paths), and
`implementation-planner` has no repository-write capability to perform a commit even in principle. Worse,
nothing would link a specific commit to a specific execution, and — unlike this design's other disclosed
residual risks, each backstopped by something (the code-enforced denylist, the unconditional review
lenses) — a skipped commit would have had zero backstop at all.

**Rather than invent a tenth mechanism, the actual, verified fact changes the requirement itself.** Grepped
`scripts/registry/composition_contracts.yaml`'s complete field lists for `architecture_review_report`,
`system_design_spec`, and `change_impact_report` — the three reports the `FULL` path already runs through
today: **none of them carry an author/session/human identity field.** `title`, `decision`/`readiness`,
`assessment_target`, `normalized_decision`, `findings`, `conditions`, `required_actions`, `evidence_refs` —
that is the complete set, for every one of them. This repo's reporting pipeline has never tracked "who
produced this report" in-band, for any artifact type, `FULL` path included. Nine rounds of this review were
spent trying to make the `LIGHTWEIGHT` path capture something *stronger* on this one axis than the `FULL`
path already provides — every attempt broke something real, because the pipeline genuinely has no such
mechanism to hook into.

**What Condition 4 actually gets, honestly stated:**
- **"Which eligibility criterion applied"** — fully closed, code-enforced: `eligibility_category` is a
  member of the fixed `ELIGIBILITY_CATEGORIES` enum (Fix 4/7), durably present in every `LIGHTWEIGHT` plan,
  checked by `_validate_planning_path`.
- **"Why"** — closed: `asserted_by`'s rationale text (Fix 5), stable and present in every `LIGHTWEIGHT`
  plan, citing the specific target paths and category justification.
- **"Who/what asserted it"** — **disclosed as not captured in-band**, consistent with (not a regression
  from) how this entire pipeline already treats every other report's authorship today. `run_log.py`'s
  `run_id` tracks *execution-time* identity once `loop-task-implementer` starts (confirmed, round 5); no
  mechanism tracks *planning-time* identity for any report type, and building one is a pipeline-wide
  enhancement — extending the common `skill_result` envelope with an author/session field for every report
  type this pipeline produces — genuinely out of scope for a single ticket narrowly about
  `implementation-planner`'s evidence requirements. Named here as a specific, addressable follow-up, not
  left as an unstated gap.

This is honest where every prior revision of this fix overclaimed: `eligibility_category`'s enum membership
and `asserted_by`'s rationale text are real, code-enforced, durable, and audit-useful on their own — a
later reader can already tell *what* was fast-tracked and *why*. Only the specific "which session/human"
detail is unavailable, and it is unavailable for the exact same reason it's unavailable for a `FULL`-path
architecture review today: this pipeline was never built to track it.

### Fix 9 (revision 4, closes round-3 SRE finding) — reworded Consistency claim, and Retries & idempotency correction

`planning_path` never participates in `plan_id`/`plan_set_id` derivation (that comes solely from the three
source digests and `target_repo`); it only participates in `canonical_plan_digest`, used for resume-state
matching. Plan identity itself is now governed by the stub payloads' real content (Fix 4), not by
`planning_path` or any caller-computed override.

## Events

None — no new `run_log.py` event or reason code.

## Data model

| Entity | Key fields | Relationships | Owner |
|--------|-----------|-----------------|-------|
| `implementation_plan.planning_path` | `mode`, `eligibility_category`, `asserted_by` | One per plan; absent on any plan built before this change (implicit `FULL`), always present after | `implementation_plan.py` |
| `ELIGIBILITY_CATEGORIES` (code-enforced) | 4 fixed values | Checked by `_validate_planning_path`; restated in `reference/lightweight-path.md`, kept in sync by Fix 10's parity test | `implementation_plan.py` is the source of truth |
| `asserted_by` | `"<reason citing target_paths and category rationale>"` — no session/run-id component (Fix 5, revision 5) | Pure stable rationale text. Session/run-id identity is *not* covered elsewhere in this pipeline (round 5 corrected a false claim that `run_log.py` did) — see Fix 11 | `reference/lightweight-path.md` |
| Stub payloads (Fix 6 shape) | Genuinely task-specific `title` + `target_paths`, shared across all three | Their natural content, not any override field, determines plan identity uniqueness (Fix 4) | Caller-constructed |

### Fix 10 (revision 4, Software Architect suggestion, citation corrected) — `ELIGIBILITY_CATEGORIES` doc-parity test

Round 3 corrected the precedent citation: `test_plan_execution_state.py:237-241`'s
`EXECUTION_STATE_FIELDS`-vs-`state-schema.yaml` check is a **structured** YAML-set-equality assertion, not
applicable here since `reference/lightweight-path.md` is prose. The actual matching precedent is
`test_run_log.py`'s `test_reference_documents_every_event_actor_outcome_reason_and_exit_code`, which does
**literal-text containment, each name backtick-wrapped** (`f"`{name}`" in text`). New test follows that
exact convention: assert `` f"`{category}`" `` appears in `reference/lightweight-path.md` for every value
in `ELIGIBILITY_CATEGORIES`.

### Eligibility allowlist (Condition 1) — closed, four categories, conjunctive with two blanket gates

**Code-enforced gates:**
- `len(target_paths) <= 3` across the whole plan.
- No target path (normalized, backslash- and case-insensitive-aware, with a narrow `tests/fixtures/`
  exemption for the dependency-manifest check only) matches the denylist, regardless of asserted category.
- `eligibility_category` must be one of the four registered values.
- Plan identity has no structural collision mechanism: two different tasks collide only if the caller also
  reuses identical `title` text for genuinely different changes (Fix 4) — a narrow, self-evident-in-the-plan
  failure mode, not a guaranteed collision the way revision 2/3 had it.

**Doc-only gate, disclosed as a residual, accepted limitation** (unchanged framing from revision 2): the
caller self-certifies that no specialist review would trigger — inherent to how
`change_impact_report.review_triggers` has always worked, not unique to this path. Mitigated by the
code-enforced gates above plus `loop-task-implementer`'s unconditional review lenses as the backstop.

**Categories (task must match exactly one):**
1. `CONFIG_VALUE_ONLY` — values inside an already-existing config/registry/data file; no source, script,
   or skill-logic file touched; never a file matching the code-enforced denylist (CI/permissions/
   governance/dependency-manifest), regardless of how "just a config value" it looks.
2. `DOC_ONLY` — every touched path is `.md`; no source, script, or config file touched.
3. `ADDITIVE_TEST_ONLY` — only new test file(s) added; zero existing non-test files modified.
4. `MECHANICAL_PRECEDENT_APPLICATION` — a literal, mechanical application of a mechanism already covered
   by a specific, named, prior `architecture_review_report`/`system_design_spec` pair elsewhere in this
   repository. The caller must cite that prior pair's file paths in `asserted_by`; uncited defaults to
   full chain.

Any ambiguity, any mixed change, or any criterion that can't be confidently checked defaults to the full
chain.

## State machines

None new. `planning_path.mode` is set once at plan-build time and is immutable thereafter.

## Consistency

| Boundary | Model (strong / eventual) | Why |
|----------|-----------------------------|-----|
| `planning_path` field vs. the rest of the plan | Strong | Computed once inside `build_implementation_plan`, part of the same deterministic output |
| `planning_path` vs. `plan_id`/`plan_set_id` identity | **Not** derived from `planning_path` at all (Fix 9) — identity derives from the three source digests' natural content (Fix 4) and `target_repo` |
| `planning_path` vs. `canonical_plan_digest` (resume-state matching) | **Stable across resume by construction** (Fix 5, revision 5) — `canonical_plan_digest` hashes the whole `plan` dict including `planning_path`, with no exclusion, but `planning_path` now contains no run-scoped content anywhere (`asserted_by` is pure stable rationale text), so a resume that rebuilds or reloads the same logical task's plan produces the same digest regardless of the new session/run-id issued for that resume |
| `planning_path` presence vs. plans built before this change | N/A by design | Absence is treated as implicit `FULL` for all validation purposes (Fix 8) |

## Retries & idempotency

| Operation | Idempotent? | Retry / backoff strategy |
|-----------|-------------|----------------------------|
| `build_implementation_plan` with a stub-bearing `sources` mapping | Yes — a retry that reuses the same `title`/`target_paths`/`asserted_by` content (the natural way to describe re-attempting the same task) produces the same `plan_id` (Fix 4) **and** the same `canonical_plan_digest` (Fix 5, revision 5), surviving a run-id change across resume since no run-scoped content exists anywhere in the plan | No new retry logic |

## Capacity

| Dimension | Estimate | Basis |
|-----------|----------|-------|
| Additional code surface | ~130–160 new lines in `implementation_plan.py` (3 constants, path-normalization helper with fixture/case handling, denylist-match helper, `_validate_planning_path`, `PLAN_FIELDS` entry, `validate_implementation_plan`'s restored carve-out, `build_implementation_plan` wiring) | Back down to revision 4's size — Fix 11's audit-trail requirement (revision 7) is documentation-only, no code, after rounds 4-6 each found a real bug in a structured/code-based attempt |
| Additional registry surface | `skills.yaml`'s `implementation_plan` schema `fields` + `payload_types` entries + `make generate` + pinned test update | Fix 1, landed atomically with the code (Fix 2) |
| Additional doc surface | 1 new reference file (with Fix 11's disclosed-limitation statement), 2 small amendments (`SKILL.md`, `workflow/plan.md`), 1 additive `orchestrator.md` note, 1 new doc-parity test (Fix 10), 1 new lazy-load-index.md row (round 3, Software Architect minor finding) | |

## Failure strategy

| Failure mode | Degradation / mitigation |
|--------------|-----------------------------|
| Caller mis-asserts eligibility (task is actually not small) | Both pre-existing size safety nets remain fully in force, unconditionally |
| Caller asserts `CONFIG_VALUE_ONLY` for a CI/permissions/governance/dependency-manifest file, including a `./`-prefixed, backslash-separated, or case-varied path | Code-enforced, fully normalized denylist rejects the plan outright (Fix 7) |
| Two distinct `LIGHTWEIGHT` invocations share category and target paths | No longer a structural collision — natural content (`title`) must also match for a collision to occur, a narrow and self-evident failure mode, not a guaranteed one (Fix 4) |
| A legitimate crash-and-resume issues a new run-id | Both `plan_id`/`plan_set_id` (Fix 4) and `canonical_plan_digest` (Fix 5, revision 5) survive — `asserted_by` carries no run-scoped content anywhere, so nothing about the plan changes when only the resuming session's run-id changes |
| Registry requires `planning_path` before code produces it | Not possible — Fix 1 and Fix 2 land in the same atomic change |
| A plan built before this change is resumed after deploy | Validates successfully — `present_fields`/`.get(..., default)` treat absence as implicit `FULL`, no migration needed, no `effective_plan`-style undefined-variable bug (Fix 8) |
| Caller mis-asserts "no specialist trigger" | Disclosed, accepted residual risk — mitigated by code-enforced gates plus the unconditional review-lens backstop |
| No confident size estimate available at planning time | Existing behavior (`implementation_plan.py:619`, unchanged): caps `readiness` at `PARTIAL` |
| `planning_path.mode == "LIGHTWEIGHT"` with invalid category, missing `asserted_by`, >3 paths, or a denylisted path | `_validate_planning_path` rejects the plan |
| `MECHANICAL_PRECEDENT_APPLICATION` cites a precedent that doesn't actually cover the change | No automatic detection — disclosed, not solved |
| A test-fixture file literally named `requirements.txt` is added under `ADDITIVE_TEST_ONLY` | Exempted from the dependency-manifest check specifically when under a `tests/fixtures/` path segment — inert test data, never a real installed dependency for this repo (Fix 7) |
| A later audit needs to know which session/human asserted a `LIGHTWEIGHT` eligibility judgment | Not captured in-band — disclosed limitation (Fix 11), consistent with how no report type in this pipeline (`FULL` path included) tracks author/session identity today; `eligibility_category` (which criterion) and `asserted_by` (why) remain durably captured and code-enforced |

## Observability

| Signal | What's measured |
|--------|-------------------|
| `implementation_plan.planning_path.mode` | Queryable on any plan built after this change |
| `asserted_by` | Human-readable rationale text, stable across resume |
| `implementation_plan.planning_path.eligibility_category`/`asserted_by` (Fix 4/5/7) | "Which criterion" and "why," Condition 4's two capturable halves — durably present, code-enforced. "Who/what asserted it" is explicitly not captured (Fix 11) — see Failure strategy |

## Rollout plan

| Phase | Scope | Feature flag / migration order |
|-------|-------|----------------------------------|
| 0 | **Atomic**: `skills.yaml` schema (`fields` + `payload_types`) + `make generate` + pinned-test update (Fix 1) **together with** `scripts/implementation_plan.py`'s constants, normalization/denylist helpers, `_validate_planning_path`, `PLAN_FIELDS` entry, `validate_implementation_plan`'s restored carve-out, and `build_implementation_plan` wiring (Fixes 2, 4, 5, 7, 8) — one commit/PR; companion tests: resume-compatibility against a real historical plan JSON missing `planning_path`, `LIGHTWEIGHT` positive/negative cases (valid/invalid category, >3 paths, denylisted path incl. `./`-prefixed/backslash/case-varied variants, dependency-manifest path, `tests/fixtures/`-exempted manifest path, missing `asserted_by`), plan-identity test (two `LIGHTWEIGHT` builds sharing category/paths but different `title` → different `plan_id`), **resume-digest stability test**: two `build_implementation_plan` calls with byte-identical `title`/`target_paths`/`asserted_by`/`eligibility_category` produce the same `canonical_plan_digest` (the direct regression test for round 4's finding), `FULL`-mode default-seeding parity test — **no `plan_state_store.py`/`EXECUTION_STATE_FIELDS` changes of any kind**, per Fix 11's revision-7 correction | None — additive |
| 1 | New `skills/implementation-planner/reference/lightweight-path.md` (allowlist + corrected stub template + code-enforced-gates restatement + Fix 11's disclosed-limitation statement on report authorship) + its doc-parity test (Fix 10) + a new row in `reference/lazy-load-index.md`; amend `SKILL.md` "Required evidence" and `workflow/plan.md` §1 | None — documentation only |
| 2 | Additive `orchestrator.md` note (existing size gates apply unconditionally) plus a precedence sentence versus the legacy `implementation_task` bypass, explicitly noting the architecture review's own "ungoverned" characterization of that bypass | None — additive |

No feature flag: the mechanism is opt-in by construction.

## Open questions

**Accepted residual risk — Condition 4's "who/what asserted it" is not captured in-band.** Confirmed
(direct grep of `composition_contracts.yaml` and `skills.yaml`, independently re-verified twice): no report
type this pipeline produces — `architecture_review_report`, `system_design_spec`, `change_impact_report`,
the `FULL` path's own existing evidence — carries an author/session/human identity field anywhere, in its
own schema or in the shared `skill_result`/`authority` envelope that wraps every artifact. This is a
pre-existing, structural property of the whole reporting pipeline, not a gap this ticket introduces or
could close in isolation. Building new machinery to make the `LIGHTWEIGHT` path capture something the
`FULL` path has never captured is out of scope for `implementation-planner`'s own evidence-requirement
change; a genuine fix would be a pipeline-wide addition (an author/session field on the common
`skill_result` envelope, applying to every report type at once), tracked as a separate, addressable
follow-up rather than solved narrowly here. What Condition 4's *other* two halves get, fully closed and
code-enforced: `eligibility_category` ("which criterion") and `asserted_by`'s rationale text ("why"), both
durably present in every `LIGHTWEIGHT` plan (Fix 4/5/7).

Four of the five architecture-review conditions are closed without qualification. Every review finding
across nine rounds (19 blocking, 6 suggestions) has a stated, specific resolution. The audit-trail
mechanism went through seven restructurings, each triggered by a fresh, independent re-read of the actual
code/docs finding the prior attempt incomplete: a caller-computed digest formula (round 3: circular, and
run-boundary-fragile) → natural content entropy plus a session/run-id-bearing `asserted_by` (round 4: the
run-id still reached `canonical_plan_digest` one layer down) → `asserted_by` stripped of all run-scoped
content (round 5: fixed digest stability, but silently dropped Condition 4's "who/what asserted it") → a
new `plan_execution_state` field (round 6: unreachable through the real write path, and itself missing a
backward-compat carve-out) → the identity moved into the PR description (round 7: not universally
produced, since `create_pr` defaults to `false`) → the identity moved into `report-template.md`'s
completion report (round 8: no session ever had the planning-time identity data to put there, and a
cross-session executor would have had to fabricate it) → git commit provenance on the plan document
(round 9: doesn't match how this pipeline actually moves an `implementation_plan` — in-memory,
digest-addressed, no repository-write capability to perform the commit — and had no backstop if skipped)
→ this accepted-residual-risk disclosure (round 10 fixed two leftover inconsistencies: a stale, debunked
claim still standing as current truth in Fix 5's own text and the Data model table, and this verdict/Open
Questions framing, both corrected to match this repo's own precedent for the same category of disclosure,
e.g. `2026-09-25-a5-durable-state-checkpoint-design.md` and `2026-09-25-f1-condition1-lock-safety-classifier-design.md`,
both "Ready with open questions" for the same shape of permanent, structural limitation). Nine attempts at
new machinery for one field each broke something real; the conclusion is that no new machinery was the
answer — and that this repo's own report-format rules already have the right label for that conclusion.
