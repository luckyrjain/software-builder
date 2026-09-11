# Changelog — merge-conflict-analysis

## 1.0.0 — 2026-09-11

### Added

- Initial ambient, read-only merge-conflict-analysis skill: detects an in-progress git conflict,
  cites both sides' intent from commit messages and (where discoverable) originating PR/issue
  text, and recommends a per-hunk resolution — preserving both intents where possible, naming the
  trade-off explicitly where genuinely incompatible — as report-only
  `MERGE_CONFLICT_ANALYSIS.md` / `merge_conflict_analysis` output. Never resolves a hunk, stages,
  commits, or continues/aborts the operation.
- Detection asks git to resolve refs and paths (`git rev-parse -q --verify MERGE_HEAD` /
  `CHERRY_PICK_HEAD` / `REVERT_HEAD`, `git rev-parse --git-path rebase-merge` / `rebase-apply`)
  rather than testing a hardcoded `.git/...` path, which is absent in a linked worktree
  (`git worktree add` makes `.git` a file) or a submodule. Squash-merge and `git stash pop`
  conflicts, which set no ref at all, are picked up from unmerged paths in `git status
  --porcelain` and reported with the operation recorded as `undetermined`.
- The report states the detected mode and what "ours"/"theirs" mean for it (`mode`,
  `ours_theirs_note`), gives every hunk a stable `id` (`H1`, `H2`, …), reads a rebase's "theirs"
  side via `git show REBASE_HEAD`, and says plainly when an operation is in progress but every
  marker is already resolved instead of emitting an empty hunks list.
- A revert's "theirs" is `REVERT_HEAD^`, not `REVERT_HEAD` — a revert runs the merge with the
  roles swapped, so the reverted commit is the merge base (stage 1) and git labels the incoming
  side `parent of <sha>`. Reverified against a live conflicted `git revert`; cherry-pick keeps the
  straightforward reading (`CHERRY_PICK_HEAD` *is* stage 3).
- The "already resolved, nothing to analyze" statement is mode-correct: `git commit` finishes a
  merge only. Cherry-pick and revert are sequencer operations like rebase — a bare commit there
  lands one commit, clears the head ref, and leaves the remaining range unapplied with the
  sequencer still active, so the advice names `git cherry-pick --continue` / `git revert
  --continue` and says more commits may remain.
- `MERGE_MSG` is used as a conflict-stop marker only under the `rebase-merge` backend. The
  `rebase-apply` backend and `git am` never write it even when genuinely stopped on a conflict,
  and neither has an `edit`/`break` stop to be confused with. `rebase-apply` is shared by both, so
  its `rebasing` / `applying` marker file distinguishes an apply-backend rebase from a `git am`
  session, which is finished with `git am --continue`. Where those two leave a clean tree the
  patch never applied at all — reported as such, not as "already resolved".
