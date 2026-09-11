# merge-conflict-analysis

Analyzes an in-progress git merge or rebase conflict from live repository state — not a
hypothetical or already-resolved one. It produces a report-only `MERGE_CONFLICT_ANALYSIS.md` /
`merge_conflict_analysis`; it never resolves a hunk, stages, commits, or continues/aborts the
merge or rebase.

Use it to cite both sides' intent from commit messages and, where discoverable, originating
PR/issue text, recommend a per-hunk resolution that preserves both intents where possible, and —
where the two are genuinely incompatible — recommend the resolution matching the merge's own
stated goal with the trade-off named explicitly.

A hunk whose originating context can't be found becomes an explicit unresolved question, never a
guessed resolution.

## When to use

- A merge or rebase is stuck on conflicts and needs a preserved-intent resolution recommendation.
- Conflicting hunks need their trade-offs named explicitly before a human applies a resolution.
- Another skill (`loop-task-implementer`) needs a vetted per-hunk recommendation to apply.

Do not use it for an already-clean, already-mergeable diff (`pr-review`, `local-diff-review`), or
to actually apply the recommended resolution (`loop-task-implementer`).

## Pipeline

`Inputs → Analyze → Report`

See [SKILL.md](SKILL.md) for the full contract and [examples.md](examples.md) for invocation patterns.
