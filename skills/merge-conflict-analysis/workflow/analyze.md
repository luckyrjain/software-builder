---
workflow_version: 1.0
phase: analyze
produces:
  - hunks
consumes:
  - conflict_state
---

# Analyze — cite intent, recommend a resolution per hunk

For each conflicted file in `conflict_state`, for each conflict hunk (each `<<<<<<< / ======= /
>>>>>>>` block):

1. **Find each side's primary source.** Read the commit(s) that introduced each side's version of
   the hunk (`git log`, `git show`) — the commit message states intent directly more often than
   the diff alone does. Which ref names each side is mode-dependent — use the mode `conflict_state`
   recorded ([inputs.md](inputs.md) step 5):

   | Mode | Reading "ours" | Reading "theirs" |
   |------|----------------|--------------------|
   | merge | the current branch by name, or `HEAD` | the branch being merged in by name, or `MERGE_HEAD` |
   | cherry-pick | `HEAD` | `git show CHERRY_PICK_HEAD` — its content *is* stage 3 |
   | revert | `HEAD` | content: `git show REVERT_HEAD^:<path>`, or stage 3 directly (`git show :3:<path>`). Intent: `git show REVERT_HEAD` — but that prints the commit being **undone**, the inverse of what theirs contains, so read it as "what is being removed, and why"; `git show -R REVERT_HEAD` prints the change actually being applied |
   | rebase | `HEAD` — the base already replayed onto | `git show REBASE_HEAD` / `git log -1 REBASE_HEAD` — the commit being replayed is **not** reachable by branch name the way a merge's two sides are; `REBASE_HEAD` exists during a conflicted rebase precisely for this |
   | `git am` / apply-backend rebase | `HEAD` | no commit ref for the incoming side yet — read stage 3 (`git show :3:<path>`) and the patch at `$(git rev-parse --git-path rebase-apply)/patch` |
   | undetermined | `HEAD`, with the operation stated as unconfirmed | no ref available — read the working-tree stages (`git show :2:<path>` / `:3:<path>`) and say the commit-level intent could not be recovered |

   A revert is the one mode where the "theirs" ref and the "theirs" content come apart:
   `REVERT_HEAD` is the merge **base**, not the incoming side, and git's own marker labels that
   side `>>>>>>> parent of <sha>`. Citing `REVERT_HEAD`'s diff as theirs' content inverts the
   analysis. Stage 3 is authoritative in every mode — use it to check any ref reading that looks
   surprising.

   Where a commit message references an issue/ticket or the branch name
   suggests a PR, check whether that text is present anywhere in the repository's own history
   (this skill has no external tracker access — cite only what's actually discoverable in-repo;
   an issue number with no corresponding commit-message context stays a bare reference, not
   fabricated content).
2. **State both sides' intent** in one sentence each — what the change was trying to accomplish,
   not a restatement of the diff text.
3. **Recommend a resolution.** Preserve both intents where the hunk allows it (e.g. two additive
   changes to different parts of the same function). Where the two are genuinely incompatible
   (e.g. one side removes what the other side modifies), recommend the resolution that matches
   the merge's own stated goal — read the merge commit message or PR description for that goal
   where discoverable, otherwise state that no stated goal was found and recommend the side with
   the more specific, more recently-authored intent, flagging this as a judgment call. Never
   invent a resolution not traceable to one side's or the other's actual code.
4. **Name the trade-off explicitly** whenever the recommendation drops part of either side's
   intent — which intent survives, which doesn't, and why.

A hunk whose originating context can't be found (no discoverable commit message beyond a bare
"fix" or similar, no PR/issue reference anywhere in history) is recorded as an unresolved question
naming exactly what's missing, never resolved by guessing.
