# research-brief

Answers one research question with cited, evidence-classified findings gathered from primary sources —
repository evidence and, when available, external documentation. It produces a report-only
`RESEARCH_BRIEF.md` / `research_brief`; it never edits source, tests, configuration, or docs, and never
commits, pushes, or opens a PR.

Use it to investigate a bounded question against repository and external primary sources, cite every
claim's source, and classify each claim's evidence status — degrading to repository-only research and
marking external-dependent claims `UNKNOWN` when `host.web.search`/`host.web.fetch` are unavailable.

A claim is stated as fact only when it carries a cited source. A claim with no source is `UNKNOWN`,
never presented as a fact from unaided recollection.

## When to use

- A question needs an evidenced, cited answer rather than a recollection.
- Repository and/or external documentation together can answer the question.
- Every claim needs a stated evidence status and source.

Do not use it to reconstruct this codebase's own current-state behavior (`domain-comprehension`), or to
decide between options once the facts are already known (`engineering-decision-discovery`).

## Pipeline

`Inputs → Gather → Report`

See [SKILL.md](SKILL.md) for the full contract and [examples.md](examples.md) for invocation patterns.
