# domain-modeling

Sharpens one project's domain model from the terms, decisions, and scenarios actually in play during the
current session — not a full-repository audit. It produces a report-only `DOMAIN_MODEL_UPDATE.md` /
`domain_model_update`; it never writes `CONTEXT.md`, `CONTEXT-MAP.md`, or `docs/adr/*.md`.

Use it to challenge a term against the existing glossary, sharpen fuzzy or overloaded language, stress-test
a domain relationship with concrete edge-case scenarios, cross-check a stated behavior against the code,
and — only when an actual decision point exists — propose an ADR draft.

An ADR is proposed only when a real decision crystallized this session: a choice made, at least one
alternative rejected, and a consequence stated. Restating an existing, uncontested definition or code
behavior never earns an ADR.

## When to use

- A term used this session conflicts with, or is missing from, `CONTEXT.md`.
- A decision crystallizes mid-conversation and is worth recording as an ADR.
- Another skill needs live domain vocabulary while designing or building.

Do not use it for a full unfamiliar-domain reconstruction from scratch (`domain-comprehension`), one
concrete module's contract/seam (`module-design`), or an architecture-wide trade-off verdict
(`architecture-review`).

## Pipeline

`Inputs → Challenge → Report`

See [SKILL.md](SKILL.md) for the full contract and [examples.md](examples.md) for invocation patterns.
