# Smoke test — expected minimal output

Run after install **and** after any edit to this skill (SKILL.md, workflow/*.md, or
state-schema.yaml). Use a small repo with at least one open, well-scoped task and repository write
access.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> Use loop-task-implementer to implement `<task>` and open a PR.

Example: `Use loop-task-implementer to implement issue 42, review it deeply, fix findings, and open a PR.`

## A correct minimal run contains

1. **Policy discovery** — Orchestrator states default/protected branch, required checks, required
   approvals, and whether autonomous merge is authorized (default `false` unless explicitly granted).
2. **Fresh Builder dispatch** — a new/updated branch and pull request exist; Builder report includes
   `head_commit` and `changed_files`.
3. **Independent verification** — Orchestrator re-derives `head_commit`/`diff_fingerprint` itself
   rather than trusting the Builder report verbatim.
4. **Two isolated Reviewer lenses** — Lens A (Safety and State) and Lens B (Contracts and
   Operations) each run in a fresh context and return a `lens_verdict` of `CLEAN` or `FINDINGS`.
5. **Adjudication** — any `PROPOSED_BLOCKING` finding is marked `ACCEPTED` / `REJECTED` /
   `NEEDS_EVIDENCE` / `CONTESTED` with rationale, not blindly implemented.
6. **Completion response** — final report follows [report-template.md](../report-template.md):
   task/repo, branch/PR, head commit + fingerprint, both lens statuses, findings, authoritative
   checks, completion state, and any exact human action required.
7. **No unauthorized merge** — when `autonomous_merge_authorized` is `false`, the run stops at
   verified readiness rather than merging.

## Degraded path

When the host agent has no subagent/worktree/fresh-session primitive, role simulation falls back to
sequential context resets (`SKILL.md` § Platform behavior) — the smoke test still requires evidence
that Builder and Reviewer context was actually reset, not merely narrated.

## Deep edge cases

See [pressure-tests.md](pressure-tests.md) — e.g. "Reviewer asked to fix its own finding" and "same
finding contested twice with no new evidence."

## Pass criteria

- No merge occurred without explicit authorization.
- Reviewer sessions performed zero commits/pushes/PR edits.
- Every accepted finding has a `FIXED` / `REBUTTED` / `BLOCKED` response with evidence.
