---
workflow_version: 1.6
phase: orchestrator-lifecycle
produces:
  change_identity: object
  lens_a_review_evidence: object
  lens_b_review_evidence: object
  lifecycle_validation: object
consumes:
  required:
    task_state: object
    repository_policy: object
  optional: {}
  conditional: {}
---

# Orchestrator lifecycle overlay

This file is a **mandatory normative overlay** for `workflow/orchestrator.md`. Load it with the Orchestrator from task initialization through completion. For lifecycle freshness, readiness, and completion semantics, this overlay is authoritative wherever it conflicts with legacy Orchestrator text — including change-identity freshness, review-isolation exceptions, and the separation of verified readiness from merge authority. Legacy instructions that do not conflict with this overlay remain in force.

## After Builder result verification

Rebuild the current shared `change_identity` from a fresh provider/Git snapshot using the canonical shared contract. Persist it as `workspace.change_identity` together with `workspace.current_head_commit`. Preserve legacy fingerprint fields only as diagnostics; they are not sufficient review or completion proof.

Normalize the current authoritative task/issue requirements surface into `task.requirements_ref` (object or explicit `null`). A missing field is not equivalent to no requirements.

Before every reviewer dispatch, adjudication, CI observation, and completion action, re-read the branch head and classify any third-party branch update. `workspace.third_party_change_detected` must be an explicit boolean produced by that refresh, and persist the exact head inspected as `workspace.third_party_change_checked_head`. A missing check head, or a check head different from `workspace.current_head_commit`, is stale evidence and blocks readiness even when `third_party_change_detected` still says `false`. An unresolved third-party change invalidates lifecycle readiness and any evidence that predates the new content.

## After each Reviewer returns

For every returned reviewer result, increment that lens's positive integer `review_generation` exactly once, even if the code identity is unchanged. First perform the normal Orchestrator adjudication against the reviewer report and persist the rich audit result. **Then** apply `workflow/reviewer-evidence.md` to the adjudicated lens outcome before recording that lens as lifecycle `CLEAN`. The Orchestrator—not the Reviewer—binds the result to the exact supplied current `change_identity`, normalizes the closed shared `review_evidence` v1 envelope, validates it with the packaged shared runtime, and persists `review_generation`, `reviewed_change_identity`, and `review_evidence` in official lens state.

Portable classification is post-adjudication: accepted/open blocking findings become `defect`; evidence-backed non-blocking improvements become `suggestion`; unresolved evidence requests become `question`. A `PROPOSED_BLOCKING` item adjudicated `REJECTED` remains in the rich audit trail but is not a portable defect and does not require a redundant reviewer rerun merely to clear a rejected proposal.

A lifecycle-clean lens requires all of the following:

- lens status `CLEAN` after adjudication;
- positive integer `review_generation`;
- `review_evidence.inspection_status: complete`;
- no `unable_to_inspect` entries;
- zero `findings.defect` entries;
- fresh evidence for the current `change_identity` and current `requirements_ref`;
- `isolation_status: ISOLATED`, unless a human explicitly accepted degraded isolation in the current authorized context. Preserve the actual `NOT_ISOLATED` status and record that exception separately as `isolation_exception_authorized: true` plus non-empty `isolation_exception_provenance`; never relabel the review as isolated. Bind that exception both to this exact reviewed identity in `isolation_exception_change_identity` and to this exact integer lens generation in `isolation_exception_review_generation`. An exception from another identity or an earlier review generation is stale and must not carry forward.

For every security-sensitive `NEEDS_EVIDENCE` item from the legacy Orchestrator rules, populate `merge_readiness.security_sensitive_needs_evidence_unresolved`. It must be integer `0` before readiness. A human residual-risk acceptance resolves the item only when the decision/provenance is recorded in official escalation/adjudication state; do not silently decrement the counter.

If content changes, requirements change, a third-party change is accepted into the task, conflict resolution occurs after a lens produced evidence, **or a lens reruns on the same unchanged identity**, invalidate/replace that lens evidence and clear all associated isolation-exception fields. A reviewer rerun increments `review_generation`; a new `NOT_ISOLATED` result requires a new exception bound to its `reviewed_change_identity` and current `review_generation`. A conflict that happened **before** a rerun does not permanently poison new evidence already bound to the current identity.

## Base/merge-base transitions

When a stored lens evidence identity and the freshly rebuilt current identity differ in any of `base_sha`, `head_sha`, or `merge_base_sha`, establish both:

- `workspace.conflict_resolution_occurred`: explicit `true` or `false`;
- `workspace.conflict_resolution_provenance`: non-empty provider/Git evidence supporting that value.

Never infer `false` from silence. Unknown status or missing provenance fails closed. Pass `conflict_resolution_occurred=true` to shared freshness validation only for evidence that predates that conflict-bearing identity transition; fresh evidence already bound to the post-conflict current identity validates normally.

## CI and completion

Required CI is authoritative only when `ci.required_checks_green: true` and `ci.commit` equals the exact `workspace.current_head_commit`. Green CI for an older commit never satisfies readiness.

Before setting task status `READY`, before setting `COMPLETE`, and immediately before any authorized merge/completion action:

1. refresh current `change_identity`, current `requirements_ref`, branch-actor/third-party state plus `third_party_change_checked_head`, reviewer generation/isolation/exception state, unresolved security-sensitive evidence, approvals/threads/integration state, and required CI;
2. populate the existing merge-readiness gates from authoritative repository state;
3. resolve `skill_root` to the directory containing this skill's `SKILL.md`, select a Python 3 interpreter available on the host (`python3` on the supported Unix/macOS setup, or the configured equivalent elsewhere), serialize the official state as JSON, and run `python3 "<skill_root>/scripts/validate_loop_lifecycle.py" --state "<state.json>"` on the documented Unix/macOS setup (or pass `--state -` and provide JSON on stdin); do not assume the current working directory is the software-builder source checkout;
4. require process exit code `0`. Failure to locate a Python 3 interpreter or validator is a fail-closed inability to validate, not a pass. Exit `1` means lifecycle validation errors; exit `2` means the input/runtime could not be validated and therefore fails closed.

The validator must prove, independent of the current `ready` flag:

- acceptance criteria complete;
- Lens A and Lens B lifecycle-clean for the same current identity, with positive integer review generations;
- reviewer isolation gate satisfied or explicit human exception recorded with provenance and bound to the same reviewed identity **and current integer review generation**;
- zero unresolved security-sensitive `NEEDS_EVIDENCE` items;
- no accepted blocking finding open;
- required approvals satisfied;
- zero blocking review threads;
- valid integration state;
- circuit breaker explicitly inactive;
- `third_party_change_detected: false` from a refresh bound to the exact current head;
- required checks green for the exact current head;
- current identity/requirements freshness, including conflict provenance when SHAs transitioned.

Only after this zero-error gate may the Orchestrator set `merge_readiness.ready: true` or task status `READY`/`COMPLETE`.

Verified readiness is separate from merge authority. If `autonomous_merge_authorized` or `allowed_actions.merge` is false, stop at verified readiness and report the exact human action required. If merge is authorized, rerun the lifecycle validator immediately before the merge write; a head/base/requirements/approval/thread/isolation/evidence/CI change after the previous validation blocks the write.
