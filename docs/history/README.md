# Historical documentation

Design specs, implementation plans, and brainstorming notes that informed shipped skills but are **not**
normative for current behavior.

| Location | Contents |
|----------|----------|
| [superpowers/](../superpowers/) | Dated specs and plans (2025–2026) from skill evolution and platform strategy work |
| [adr/](../adr/) | Accepted architecture decision records for platform engineering choices |

## How to use this tree

- **Implementing or reviewing skills today:** start at [skill-framework/README.md](../skill-framework/README.md) and each skill's `SKILL.md` / `workflow/`.
- **Understanding why a decision was made:** read the relevant ADR first, then the dated superpowers spec if you need full context.
- **Do not treat superpowers plans as backlog:** many items are superseded by shipped PRs (#29–#40). Track open work in GitHub issues (#9, #20).

When a superpowers document is fully superseded, add a one-line status banner at the top pointing to the ADR or CHANGELOG entry — do not delete historical files.
