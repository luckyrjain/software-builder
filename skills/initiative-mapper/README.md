# initiative-mapper

Breaks one large, foggy, too-big-for-one-session effort into a decision-ticket map with dependency
edges — not a full-repository audit, and not a plan. It produces a report-only `INITIATIVE_MAP.md` /
`initiative_map`; it never writes a ticket, PRD, or plan, commits, pushes, or opens a PR.

Use it to break an ambiguous effort into bounded sub-questions, sequence which tickets can start
immediately versus which are blocked on another ticket's answer, and — for every ticket — state which
downstream skill it's ready for right now.

A ticket is created only when it materially affects sequencing: a fact already settled by evidence
becomes evidence on a ticket, not a ticket of its own. A ticket with no clear ready-for skill yet stays
explicitly unresolved rather than being force-fit into one.

## When to use

- An effort is too large or too ambiguous for `prd-architect` or `implementation-planner` to take
  directly.
- Dependent and independent sub-questions need sequencing before implementation planning begins.
- Some tickets need `engineering-decision-discovery` first, others are already PRD-ready or
  design-ready, and the mix needs to be made explicit before anyone starts.

Do not use it for one already-scoped idea (`prd-architect`), or an already-approved design ready for
task decomposition (`implementation-planner`).

## Pipeline

`Inputs → Decompose → Report`

See [SKILL.md](SKILL.md) for the full contract and [examples.md](examples.md) for invocation patterns.
