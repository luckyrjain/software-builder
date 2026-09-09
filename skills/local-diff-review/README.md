# local-diff-review

Reviews the diff since a fixed point (commit, branch, tag, or merge-base) along two independent axes:
Standards (against this repo's documented conventions) and Spec (against a supplied issue/ticket's stated
intent). It produces a report-only `LOCAL_DIFF_REVIEW.md` / `local_diff_review`; it never writes source,
tests, configuration, or posts a comment.

Use it to surface Standards violations and Spec mismatches before a diff becomes a PR/MR.

An issue is named in Spec findings only when the diff evidence supports or contradicts it — no
silently-inferred spec from commit messages or code comments alone.

## When to use

- A diff against a fixed point needs review before it becomes a PR/MR.
- Check a diff against this repo's own documented conventions.
- Check a diff against a supplied issue/ticket's stated intent.

Do not use it for a live PR/MR by number (`pr-review`), an existing-codebase architecture audit
(`codebase-architecture-review`), or a request with no bounded diff scope.

## Pipeline

`Inputs → Standards → Spec → Report`

See [SKILL.md](SKILL.md) for the full contract and [examples.md](examples.md) for invocation patterns.
