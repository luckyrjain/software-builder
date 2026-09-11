# Smoke test — merge-conflict-analysis

Run after install or any substantive edit. Use a real repository with an in-progress merge or
rebase carrying at least 2 conflicted files: one hunk resolvable by preserving both intents (two
additive changes to different parts of the same function), and one hunk with genuinely
incompatible intents (one side removes what the other side modifies). The skill remains
read-only: inspect and emit a report; do not stage, commit, or continue/abort the merge or rebase,
and do not modify any conflicted file.

Conventions: [smoke-test-conventions](../../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> Ambient — ``conflict_state`` is detected by asking git, never by testing a hardcoded `.git/...`
> path: `git rev-parse -q --verify MERGE_HEAD` / `CHERRY_PICK_HEAD` / `REVERT_HEAD`, plus
> `git rev-parse --git-path rebase-merge` / `rebase-apply` for a rebase, falling back to unmerged
> paths in `git status --porcelain`. No caller-supplied field is required.

**Run the smoke test at least once inside a linked worktree** (`git worktree add`), where `.git` is
a file rather than a directory — that is exactly the layout a hardcoded `.git/MERGE_HEAD` check
silently fails in.

Example: a repository mid-merge with two conflicted files — `src/config.py` (one hunk where both
sides add unrelated config keys to the same dict, safely combinable) and `src/pricing.py` (one
hunk where one side removes a discount branch the other side just modified).

## A correct minimal output contains

1. A HARD STOP when no ref-based check fires *and* `git status --porcelain` reports no unmerged
   path.
2. A `## Mode` section stating which operation is active (merge / rebase / cherry-pick / revert /
   undetermined), what detected it, and which side is "ours" vs. "theirs".
3. A stable `id` (`H1`, `H2`, …) on every hunk, referenced by the Unresolved questions and
   Recommendation sections.
4. Every conflicted file and every hunk within it accounted for — none silently skipped.
5. At least one hunk resolved by preserving both intents, with both intents cited from commit
   history.
6. At least one hunk with a named trade-off where the two intents are genuinely incompatible.
7. `MERGE_CONFLICT_ANALYSIS.md` / `merge_conflict_analysis` emitted as a report only — no
   `checkout --ours/--theirs`, `add`, `commit`, `rebase --continue`/`--abort`, or `merge --abort`,
   and no automatic downstream invocation.

## Degraded paths

| Condition | Expected behavior |
|-----------|---------------------|
| No conflicting operation and no unmerged path | HARD STOP — state plainly; no "describe a hypothetical conflict" mode |
| Running inside a linked worktree (`git worktree add`), mid-merge | Detected normally — `git rev-parse -q --verify MERGE_HEAD` succeeds even though `.git/MERGE_HEAD` does not exist |
| A squash-merge or `git stash pop` left unmerged paths and no ref | Analyzed, with the operation recorded as `undetermined` and ours/theirs stated as unconfirmed — never guessed |
| An operation is in progress but zero paths are unmerged | "Conflict markers already resolved; nothing to analyze" plus the **mode-correct** finisher — `git commit` for a merge, `git rebase --continue` / `git cherry-pick --continue` / `git revert --continue` / `git am --continue` for the others, never a bare commit for those — and never an empty hunks list |
| A multi-commit `git cherry-pick A..B` or `git revert X Y` is mid-sequence | The advice states that `--continue` advances the sequencer and that more commits remain — a bare `git commit` strands them with the operation still reported in progress |
| An `edit`/`break` pause, or a `rebase-apply` / `git am` stop | `MERGE_MSG` is only a conflict-stop marker for the `rebase-merge` backend; under `rebase-apply` and `git am` it is always absent, so it is never read there |
| A conflicted `git am` (a `rebase-apply` directory holding `applying`) | Reported as an `am` session, not a rebase; the finisher named is `git am --continue` |
| A conflicted rebase | "theirs" is read via `git show REBASE_HEAD`, not by branch name |
| A conflicted `git revert` | "theirs" is `REVERT_HEAD^` (or stage 3), never `REVERT_HEAD` — the reverted commit is the merge base |
| A hunk's originating commit message is a bare "fix" with no further context | Recorded as an unresolved question, never a guessed resolution |
| No PR/issue text discoverable anywhere in-repo for a referenced ticket | Bare reference only — never fabricated ticket content |
| Two sides' intents are genuinely incompatible and no merge/PR goal is discoverable | Recommend the more specific, more recently-authored intent, explicitly flagged as a judgment call |
| Caller asks the skill to just resolve the conflict and commit | Reject the direct action; emit the recommendation in the report instead |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
