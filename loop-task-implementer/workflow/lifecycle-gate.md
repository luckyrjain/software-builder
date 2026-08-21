---
workflow_version: 1.3
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

Run this gate before setting task status to `READY`, before setting `COMPLETE`, and immediately before any authorized
merge or other repository-completion action. The Orchestrator owns this gate; Builder and Reviewer claims are advisory.

First rebuild the current `change_identity` from a fresh read-only provider/Git snapshot using the shared canonical
change-identity procedure. Include current base/head/merge-base SHAs, normalized effective-patch fingerprint,
changed/generated paths, dependency changes, and config changes. Never reuse a previously stored identity merely
because the source branch name or current head appears unchanged.

For each lens whose stored evidence identity has different base/head/merge-base SHAs from the freshly rebuilt current
identity, establish both `conflict_resolution_occurred` and non-empty `conflict_resolution_provenance` from provider/Git
history. Record `true` when merge/rebase conflict resolution occurred and `false` only when the provenance proves the
transition was conflict-free. Unknown status or missing provenance fails closed; do not assume false. A conflict that
occurred before a lens was rerun does not permanently poison fresh evidence already bound to the current identity;
only evidence that predates the conflict/identity transition is invalidated.

Refresh the authoritative requirements surface and persist it as `task.requirements_ref`: the normalized requirements
object when one exists, otherwise explicit `null`. A missing requirements field is not equivalent to no requirements.
Refresh branch-actor/third-party-change state and persist the exact inspected head as
`workspace.third_party_change_checked_head`; `third_party_change_detected: false` is acceptable only when that checked
head equals `workspace.current_head_commit`.

For any `NOT_ISOLATED` lens that relies on an authorized human exception, require both non-empty authorization provenance
and `isolation_exception_change_identity` exactly equal to that lens's `reviewed_change_identity`. Clear the exception
when the lens is invalidated or rerun; an exception accepted for an earlier review identity is not portable authorization
for a later change.

Serialize the official state as JSON and run:

```text
python loop-task-implementer/scripts/validate_loop_lifecycle.py --state <state.json>
```

Use `--state -` to supply the JSON on stdin. Only process exit code `0` may set readiness or permit completion. Exit
code `1` reports lifecycle validation errors; exit code `2` means the state/runtime could not be validated and therefore
fails closed.

The validator must prove all of the following on the same current change:

- Lens A and Lens B are CLEAN and each has valid shared `review_evidence` bound to the current `change_identity`.
- Both lenses reviewed the same shared identity; a content change or conflict resolution after a lens review invalidates that evidence until the lens reruns.
- Each lens satisfies the review-isolation gate. Preserve a real `NOT_ISOLATED` result; it blocks readiness unless an
  authorized human exception is recorded separately with non-empty provenance and bound to the exact reviewed identity.
  Never relabel degraded review as `ISOLATED` merely because the residual risk was accepted.
- `merge_readiness.security_sensitive_needs_evidence_unresolved` is integer `0`; authentication, authorization,
  secrets/credential, and trust-boundary evidence gaps must be resolved or explicitly accepted with recorded human
  decision provenance before lifecycle readiness.
- `third_party_change_detected` is false and the branch-change check was performed against the exact current head. Any
  unrecognized branch update blocks readiness until the Orchestrator re-baselines the state and reruns every invalidated lens.
- Authoritative required checks are green for the exact current head: `ci.commit` equals the current head and
  `ci.required_checks_green` is true. Builder-reported/local checks do not satisfy this gate when authoritative CI is
  required.
- No accepted blocking finding, required approval, blocking thread, integration-state, or circuit-breaker gate is
  outstanding under the existing completion policy.

A prior CLEAN lens, a matching head SHA alone, green required checks for an older commit, stale third-party-check state,
or a human exception bound to an older review is insufficient. If the current identity or requirements cannot be
re-established, if conflict status/provenance is unknown after a SHA transition, or if the validator cannot run, stop and
escalate rather than setting `ready: true`.

Record the validation errors/evidence in official Orchestrator state. `ready: true`, `COMPLETE`, or merge is forbidden
while any lifecycle error exists.
