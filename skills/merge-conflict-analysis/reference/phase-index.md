# Phase index

Read one `workflow/` file per active phase; do not bulk-load the workflow or references.

| Step | Read now | Produces |
|------|----------|-----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `conflict_state` |
| **Analyze** | [workflow/analyze.md](../workflow/analyze.md) | `hunks` |
| **Report** | [workflow/report.md](../workflow/report.md) | `MERGE_CONFLICT_ANALYSIS.md`, `merge_conflict_analysis` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller situation | Behavior |
|-------------------|----------|
| An in-progress merge, rebase, cherry-pick, revert, squash-merge or stash pop has unmerged paths | Inputs → Analyze → Report |
| Nothing in progress and no unmerged path | Inputs HARD STOP — state plainly; no Analyze phase |
| An operation is in progress but nothing is unmerged | Inputs states "already resolved; stage and commit to finish" — no Analyze phase, no empty hunks list |
| No ref identified the operation (squash-merge / `stash pop`) | Inputs proceeds from unmerged paths; `## Mode` records the operation as `undetermined` and ours/theirs as unconfirmed |
| A hunk's originating context can't be found | Analyze records it as an unresolved question; Report never guesses a resolution |
| Two sides' intents are genuinely incompatible | Analyze recommends the side matching the merge's stated goal (or the more specific, more recent intent as a flagged judgment call) and names the trade-off explicitly |
| Scope becomes an already-clean/mergeable diff review, or actually applying the resolution | Offer the one applicable escalation; do not invoke it |
