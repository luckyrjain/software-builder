# Smoke test — merge-conflict-analysis

Run after install or any substantive edit. Use a real repository with an in-progress merge or
rebase carrying at least 2 conflicted files: one hunk resolvable by preserving both intents (two
additive changes to different parts of the same function), and one hunk with genuinely
incompatible intents (one side removes what the other side modifies). The skill remains
read-only: inspect and emit a report; do not stage, commit, or continue/abort the merge or rebase,
and do not modify any conflicted file.

Conventions: [smoke-test-conventions](../../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> Ambient — ``conflict_state`` is detected from `.git/MERGE_HEAD` / `.git/rebase-merge` /
> `.git/rebase-apply` in the current repository; no caller-supplied field is required.

Example: a repository mid-merge with two conflicted files — `src/config.py` (one hunk where both
sides add unrelated config keys to the same dict, safely combinable) and `src/pricing.py` (one
hunk where one side removes a discount branch the other side just modified).

## A correct minimal output contains

1. A HARD STOP if no `.git/MERGE_HEAD`, `.git/rebase-merge`, or `.git/rebase-apply` is present.
2. Which mode is active (merge vs. rebase) and which side is "ours" vs. "theirs", stated
   explicitly.
3. Every conflicted file and every hunk within it accounted for — none silently skipped.
4. At least one hunk resolved by preserving both intents, with both intents cited from commit
   history.
5. At least one hunk with a named trade-off where the two intents are genuinely incompatible.
6. `MERGE_CONFLICT_ANALYSIS.md` / `merge_conflict_analysis` emitted as a report only — no
   `checkout --ours/--theirs`, `add`, `commit`, `rebase --continue`/`--abort`, or `merge --abort`,
   and no automatic downstream invocation.

## Degraded paths

| Condition | Expected behavior |
|-----------|---------------------|
| No merge or rebase in progress | HARD STOP — state plainly; no "describe a hypothetical conflict" mode |
| A hunk's originating commit message is a bare "fix" with no further context | Recorded as an unresolved question, never a guessed resolution |
| No PR/issue text discoverable anywhere in-repo for a referenced ticket | Bare reference only — never fabricated ticket content |
| Two sides' intents are genuinely incompatible and no merge/PR goal is discoverable | Recommend the more specific, more recently-authored intent, explicitly flagged as a judgment call |
| Caller asks the skill to just resolve the conflict and commit | Reject the direct action; emit the recommendation in the report instead |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
