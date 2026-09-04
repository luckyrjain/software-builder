# Historical documentation

Design specs, implementation plans, and brainstorming notes that informed shipped skills but are **not**
normative for current behavior.

| Location | Contents |
|----------|----------|
| [superpowers/](../superpowers/) | Dated specs and plans (2025–2026) from skill evolution and platform strategy work |
| [adr/](../adr/) | Accepted architecture decision records for platform engineering choices |
| this directory | Dated one-off review outputs and reports, listed below |

## Dated documents in this directory

| Document | What it is |
|----------|------------|
| [2026-08-31-universal-agent-compatibility-architecture-review.md](2026-08-31-universal-agent-compatibility-architecture-review.md) | Output of one `architecture-review` run against the Universal Agent Compatibility design spec. Records that run's verdict, not the shipped design. |

A skill's own report artifact belongs here, dated, rather than at the repository root: the root path
`ARCHITECTURE_REVIEW_REPORT.md` is the live output path of the `architecture-review` skill and is
`.gitignore`d so a run against this repository cannot overwrite a committed record.

## How to use this tree

- **Implementing or reviewing skills today:** start at [skill-framework/README.md](../skill-framework/README.md) and each skill's `SKILL.md` / `workflow/`.
- **Understanding why a decision was made:** read the relevant ADR first, then the dated superpowers spec if you need full context.
- **Do not treat superpowers plans as backlog:** many items are superseded by shipped PRs (#29–#40). Track open work in GitHub issues (#9, #20).

When a superpowers document is fully superseded, add a one-line status banner at the top pointing to the ADR or CHANGELOG entry — do not delete historical files.
