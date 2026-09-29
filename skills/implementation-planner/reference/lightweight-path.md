# Lightweight plan path

For a task the caller (Orchestrator, or a human driving the ticket) asserts is genuinely small,
`implementation-planner` accepts a minimal, non-blocking **stub** for each of the three normally-mandatory
report keys (`system_design_spec`, `architecture_review_report`, `change_impact_report`) instead of real
reports. The stub asserts "no material design/architecture/impact-analysis decision applies to this task" —
a caller-supplied claim, evidence in exactly the same sense as any other caller-supplied report.
`implementation-planner` performs **zero additional judgment of its own** about whether a task actually
qualifies: it accepts the stub as evidence, the same trust model this skill already applies to every other
supplied report. Eligibility is judged entirely by the caller; this document and the code it describes only
check the mechanically-checkable parts of that judgment.

The code-enforced gates below (`scripts/implementation_plan.py`'s `ELIGIBILITY_CATEGORIES` enum, the
`≤3 target_paths` limit, and the path denylist) are the real enforcement. This document restates what the
code already checks; it grants nothing beyond what `_validate_planning_path` accepts.

## Eligibility allowlist

A task must match **exactly one** of the four categories below, plus both blanket gates. Any ambiguity, any
mixed change, or any criterion that cannot be confidently checked defaults to the full chain (fail safe).

**Blanket gates (apply to every category):**
- At most 3 `target_paths` across the whole plan.
- No target path — normalized for `./`-prefixes, doubled separators, backslash separators, and case —
  matches the denylist (CI/permissions/governance files, or a dependency-manifest basename), regardless of
  how small the asserted change looks. A dependency-manifest basename under a `tests/fixtures/` path segment
  is exempted from the manifest check specifically (inert test data, never a real installed dependency).

**Categories:**

1. `CONFIG_VALUE_ONLY` — values inside an already-existing config/registry/data file; no source, script, or
   skill-logic file touched; never a file matching the code-enforced denylist (CI/permissions/governance/
   dependency-manifest), regardless of how "just a config value" it looks.
2. `DOC_ONLY` — every touched path is `.md`; no source, script, or config file touched.
3. `ADDITIVE_TEST_ONLY` — only new test file(s) added; zero existing non-test files modified.
4. `MECHANICAL_PRECEDENT_APPLICATION` — a literal, mechanical application of a mechanism already covered by a
   specific, named, prior `architecture_review_report`/`system_design_spec` pair elsewhere in this
   repository. The caller must cite that prior pair's file paths in `asserted_by`; uncited defaults to full
   chain.

**Doc-only gate, disclosed as a residual, accepted limitation:** the caller self-certifies that no specialist
review would trigger — inherent to how `change_impact_report.review_triggers` has always worked, not unique
to this path. Mitigated by the code-enforced gates above plus `loop-task-implementer`'s unconditional review
lenses as the backstop.

Plan identity has no structural collision mechanism: two different tasks collide only if the caller also
reuses identical `title` text for genuinely different changes — a narrow, self-evident-in-the-emitted-plan
failure mode, not a guaranteed one.

## Stub payload shape

Every stub is wrapped as `{"skill_result": {"status": "SUCCESS"}, "payload": {...}}`, matching this
codebase's real fixture convention. `title` must be a genuinely task-specific one-line description of the
real change (e.g. `"Bump numpy to 1.26.4 in requirements.txt"`), not `eligibility_category` boilerplate, and
must be **identical across all three stubs** for one task — this is the entropy source that gives the plan a
genuine, task-specific identity instead of colliding with another task that happens to touch the same paths.
A legitimate retry of the *same* logical task reuses the *same* title text verbatim (same content → same
digest → same plan identity → safe idempotent resume).

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

Do not add a caller-computed `assessment_target.source_artifact_digest` override to any of the three stubs.
Plan-identity uniqueness comes from the stub payloads' own genuinely task-specific content (`title` and
`target_paths`), never from an override field — this was tried and reverted twice during design review.

## `planning_path` evidence

Pass `repository_evidence.planning_path`:

```json
{
  "mode": "LIGHTWEIGHT",
  "eligibility_category": "<one of CONFIG_VALUE_ONLY, DOC_ONLY, ADDITIVE_TEST_ONLY, MECHANICAL_PRECEDENT_APPLICATION>",
  "asserted_by": "<one-line reason citing the specific target_paths and why the category applies>"
}
```

`asserted_by` must be pure, stable rationale text. It must **never** contain a session ID, run ID, or any
other run-scoped content — doing so would change `canonical_plan_digest` on every resume (a new run ID is
deliberately issued on every resume by this repository's own architecture), breaking execution-state
reconciliation. This was found and reverted during design review; do not reintroduce it.

## Condition 4: "who/what asserted it" is not captured in-band

`eligibility_category` (which criterion applied) and `asserted_by`'s rationale text (why) are captured and
code-enforced by `_validate_planning_path`, durably present in every `LIGHTWEIGHT` plan. **"Who/what asserted
it" is not captured in-band anywhere in this pipeline.** This is not a gap unique to the `LIGHTWEIGHT` path:
no report type this pipeline produces — `architecture_review_report`, `system_design_spec`,
`change_impact_report`, for the `FULL` path either — carries an author/session/human identity field anywhere,
in its own schema or in the shared `skill_result` envelope that wraps every artifact. It is a pre-existing,
structural property of the whole reporting pipeline, not a gap this ticket introduces or could close in
isolation. A genuine fix would be a pipeline-wide addition (an author/session field on the common
`skill_result` envelope, applying to every report type at once) — out of scope for this ticket, and disclosed
here as an accepted residual limitation rather than left as an unstated gap.

Nine rounds of adversarial design review tried to build new machinery to capture this identity — a
caller-computed digest formula, a `plan_execution_state` field, a PR-description requirement, a
completion-report requirement, git commit provenance — and each attempt broke something real (see the design
doc's Revision History). The converged answer is: disclose the limitation plainly, write zero code for it.
