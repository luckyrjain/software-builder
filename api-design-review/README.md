# api-design-review

Reviews a REST, GraphQL, gRPC, or async-event API design or contract for compatibility, pagination
design, idempotency, error semantics, versioning strategy, authorization model, and rate limiting.
Produces a single markdown verdict report — this skill drafts no code, changes no spec, and posts
nowhere.

Point it at a standalone API design or contract — before implementation, alongside a system-design spec,
or independent of either — and optionally a prior version of the same spec to get a real backward/
forward-compatibility diff instead of an internal-consistency-only check.

## When to use

- A REST/GraphQL/gRPC/async-event API design or contract needs review before implementation begins
- "Is this API contract backward compatible? Is pagination/idempotency/versioning/authorization sound?"
- Checking a proposed breaking change has an adequate migration path
- Reviewing an OpenAPI/GraphQL SDL/proto/event-schema document on its own, not as part of a full MR review

Not for a full merge-request code review (**pr-review**), a database schema review (**database-review**),
or implementation-level component/data-model/state-machine design (**system-design**).

## Install

```bash
cd software-builder
make install-api-design-review
```

See [SETUP.md](SETUP.md) for Claude Code and Kiro/in-repo setup.

## Pipeline

`Inputs → Analyze → Report`

Parses `api_spec` (+ optional `previous_spec`, `system_design_context`), runs the seven domain checks,
derives a verdict, and writes `API_DESIGN_REVIEW_REPORT.md`.

Agent instructions: [SKILL.md](SKILL.md).
