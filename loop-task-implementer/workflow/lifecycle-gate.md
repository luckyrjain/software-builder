---
workflow_version: 1.7
phase: lifecycle-gate
produces:
  lifecycle_validation: object
consumes:
  required:
    task_state: object
    change_identity: object
    lens_a_review_evidence: object
    lens_b_review_evidence: object
    ci_state: object
  optional:
    requirements_ref: object
  conditional: {}
---

# Lifecycle readiness gate

Run this gate before setting task status to `READY`, before setting `COMPLETE`, and immediately before any authorized merge or other repository-completion action. The Orchestrator owns this gate; Builder and Reviewer claims are advisory.

First rebuild the current `change_identity` from a fresh read-only provider/Git snapshot using the shared canonical change-identity procedure. Include current base/head/merge-base SHAs, normalized effective-patch fingerprint, changed/generated paths, dependency changes, and config changes. Never reuse a previously stored identity merely because the source branch name or current head appears unchanged.

For each lens whose stored evidence identity has different base/head/merge-base SHAs from the freshly rebuilt current identity, establish both `conflict_resolution_occurred` and non-empty `conflict_resolution_provenance` from provider/Git history. Record `true` when merge/rebase conflict resolution occurred and `false` only when the provenance proves the transition was conflict-free. Unknown status or missing provenance fails closed; do not assume false. A conflict that occurred before a lens was rerun does not permanently poison fresh evidence already bound to the current identity; only evidence that predates the conflict/identity transition is invalidated.

Refresh the authoritative requirements surface and persist it as `task.requirements_ref`: the normalized requirements object when one exists, otherwise explicit `null`. A missing requirements field is not equivalent to no requirements. Refresh branch-actor/third-party-change state and persist the exact inspected head as `workspace.third_party_change_checked_head`; `third_party_change_detected: false` is acceptable only when that checked head equals `workspace.current_head_commit`.

For each CLEAN lens, require `review_generation` to be a positive integer and `review_evidence_generation` to equal that exact generation. A generation increment without matching newly persisted evidence is deliberately stale and blocks readiness, including crash/resume during adjudication. For any `NOT_ISOLATED` lens that relies on an authorized human exception, require non-empty authorization provenance, `isolation_exception_change_identity` exactly equal to that lens's `reviewed_change_identity`, and `isolation_exception_review_generation` exactly equal to that lens's current integer `review_generation`.

Resolve `skill_root` to the directory containing this skill's `SKILL.md`, independent of the current working directory. Invoke the validator with a Python 3 interpreter available on the host (`python3` on the supported Unix/macOS setup, or the host's configured equivalent). On the documented Unix/macOS setup:

```text
python3 "<skill_root>/scripts/validate_loop_lifecycle.py" --state "<state.json>"
```

Use `--state -` to supply JSON on stdin. Do not treat failure to locate a Python 3 interpreter or validator path as a pass. Only process exit code `0` may set readiness or permit completion. Exit code `1` reports lifecycle validation errors; exit code `2` means the state/runtime could not be validated and therefore fails closed.

The validator must prove all of the following on the same current change:

- Lens A and Lens B are CLEAN, each has a positive integer `review_generation`, `review_evidence_generation == review_generation`, and valid shared `review_evidence` bound to the current `change_identity`.
- Both lenses reviewed the same shared identity; a content change or conflict resolution after a lens review invalidates that evidence until the lens reruns.
- Each lens satisfies the review-isolation gate. Preserve a real `NOT_ISOLATED` result; it blocks readiness unless an authorized human exception is recorded separately with non-empty provenance and bound to the exact reviewed identity and current integer review generation.
- `merge_readiness.security_sensitive_needs_evidence_unresolved` is integer `0`.
- `third_party_change_detected` is false and the branch-change check was performed against the exact current head.
- Authoritative required checks are green for the exact current head: `ci.commit` equals the current head and `ci.required_checks_green` is true.
- No accepted blocking finding, required approval, blocking thread, integration-state, or circuit-breaker gate is outstanding under the existing completion policy.

A prior CLEAN lens, a generation advanced without matching evidence, a matching head SHA alone, green required checks for an older commit, stale third-party-check state, or a human exception bound to an older identity/review generation is insufficient. If current identity/requirements cannot be re-established, conflict status/provenance is unknown after a SHA transition, or the validator cannot run, stop and escalate rather than setting `ready: true`.

Record validation errors/evidence in official Orchestrator state. `ready: true`, `COMPLETE`, or merge is forbidden while any lifecycle error exists.
