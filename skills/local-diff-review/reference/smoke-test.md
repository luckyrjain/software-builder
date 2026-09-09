# Smoke test — local-diff-review

Run after install or any substantive edit. Use a real repository with a small local branch containing
at least one change that violates a documented convention (Standards finding), and optionally an issue/ticket
description (spec_context). The skill remains read-only: inspect and emit a report; do not modify source,
tests, configuration, or any other repository state.

Conventions: [smoke-test-conventions](../../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> `diff_scope: <fixed point: commit, branch, tag, or merge-base>` `spec_context: <optional issue/ticket text>`

Example: `diff_scope: main` where the current branch has 1–2 commits with at least one Standards-worthy
finding (e.g., violates a documented naming convention, missing tests, undocumented API change).

## A correct minimal output contains

1. A HARD STOP if `diff_scope` is absent.
2. The resolved `diff_scope` (commit SHA, branch, tag, merge-base) stated in the Scope section.
3. At least one Standards finding, or an explicit "No Standards findings."
4. Spec findings populated if `spec_context` supplied, or "Not applicable — no spec_context given."
5. A plain-language Recommendation summarizing what stands out on each axis.
6. `LOCAL_DIFF_REVIEW.md` / `local_diff_review` emitted as a report only — no repository write, no
   comment posted, and no automatic downstream invocation.

## Degraded paths

| Condition | Expected behavior |
|-----------|---------------------|
| No `diff_scope` named | HARD STOP — ask what commit, branch, tag, or merge-base to diff against |
| No Standards violations found | Proceed; Standards section states "No Standards findings" explicitly |
| `spec_context` absent | Spec section states "Not applicable — no spec_context given"; do not infer a spec |
| Diff does not match `spec_context` requirements | Name the unaddressed or contradicted requirements explicitly in Spec findings |
| Caller asks the skill to open a PR or post a comment | Reject; report-only; emit the report, never write or post anywhere |
| A Standards finding is security-sensitive | Offer `security-review` escalation |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
