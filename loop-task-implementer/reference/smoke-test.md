# Smoke test — expected minimal output

Run after install **and** after any edit to this skill (SKILL.md, workflow/*.md,
reference/state-schema.yaml, or `scripts/validate_loop_lifecycle.py`). Use a small repo with at least one
open, well-scoped task and repository write access.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> Use loop-task-implementer to implement `<task>` and open a PR.

Example: `Use loop-task-implementer to implement issue 42, review it deeply, fix findings, and open a PR.`

## A correct minimal run contains

1. **Policy discovery** — Orchestrator states default/protected branch, required checks, required
   approvals, and whether autonomous merge is authorized (default `false` unless explicitly granted).
2. **Fresh Builder dispatch** — a new/updated branch and pull request exist; Builder report includes
   `head_commit` and `changed_files`.
3. **Current change identity** — after independently verifying the Builder result, the Orchestrator
   rebuilds and validates the shared `change_identity` from the current base/head/merge-base, normalized
   effective patch, generated paths, dependency changes, and config changes. A legacy
   `diff_fingerprint` alone is not enough.
4. **Current requirements + branch-change state** — `task.requirements_ref` is an object or explicit
   `null`; `workspace.third_party_change_detected` is an explicit boolean from a fresh check and
   `workspace.third_party_change_checked_head` equals the exact current head.
5. **Two isolated Reviewer lenses** — Lens A (Safety and State) and Lens B (Contracts and Operations)
   each run in a fresh context and return a `lens_verdict` of `CLEAN` or `FINDINGS`. Record the actual
   isolation status rather than assuming it.
6. **Adjudication before portable evidence** — each proposed finding is marked `ACCEPTED` / `REJECTED`
   / `NEEDS_EVIDENCE` / `CONTESTED` with rationale, then each lens is normalized into shared
   `review_evidence` bound to its exact `reviewed_change_identity`. Lifecycle `CLEAN` requires complete
   inspection, no unavailable surfaces, and zero portable defects.
7. **Freshness reruns** — any content, requirements, conflict-resolution, or accepted third-party
   branch change invalidates affected evidence; rerun every invalidated lens until both are clean for
   the same current identity. A degraded-isolation exception, when used, is explicit, has non-empty
   provenance, and is bound to that exact reviewed identity.
8. **Authoritative current-head CI** — required CI is green and `ci.commit` equals
   `workspace.current_head_commit`; an older green pipeline does not count.
9. **Executable lifecycle gate** — resolve the actual skill root (source or installed), serialize the
   official state as JSON, and run
   `python <skill_root>/scripts/validate_loop_lifecycle.py --state <state.json>`. Only exit code `0`
   establishes verified readiness; exit `1` is lifecycle errors and exit `2` is fail-closed
   input/runtime inability. Running from an installed skill while the current working directory is the
   target repo must still reach the packaged validator.
10. **Completion response** — final report follows [report-template.md](../report-template.md): current
    identity/freshness, both lens evidence/isolation states, third-party check, authoritative current-head
    checks, lifecycle gate result, merge authority, completion state, and any exact human action required.
11. **No unauthorized merge** — when `autonomous_merge_authorized` or merge action authority is false,
    the run stops at verified readiness rather than merging.

## Degraded path

When the host agent has no subagent/worktree/fresh-session primitive, role simulation falls back to
sequential context resets (`SKILL.md` § Platform behavior). Preserve the actual resulting
`isolation_status`; if a lens is `NOT_ISOLATED`, readiness remains blocked unless an authorized human
exception with non-empty provenance is recorded and bound to the exact `reviewed_change_identity`.

## Deep edge cases

See [pressure-tests.md](pressure-tests.md) for stale-head CI, stale third-party checks, exception reuse,
validator fail-closed behavior, conflict transitions, and report-rendering attacks in addition to the
legacy reviewer/remediation cases.

## Pass criteria

- `change_identity`, requirements, both lens evidence envelopes, branch-change evidence, and CI all
  describe the same current change/head.
- The lifecycle validator was actually executed from the resolved skill root and returned exit `0` for
  the official state immediately before verified readiness/completion.
- No merge occurred without explicit authorization.
- Reviewer sessions performed zero commits/pushes/PR edits.
- Every accepted finding has a `FIXED` / `REBUTTED` / `BLOCKED` response with evidence.
- No stale review, isolation exception, third-party check, requirements surface, or old-head CI was
  reused to claim readiness.
