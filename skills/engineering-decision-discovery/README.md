# engineering-decision-discovery

Finds the engineering decisions a bounded scope has not yet made, and resolves them with the user one
decision frontier at a time. It is ambient, **interactive**, read-only, and report-only: it emits
`ENGINEERING_DECISION_RECORD.md` / `engineering_decision_record` without changing repository state and
without writing an ADR.

The shared [codebase design doctrine](../../docs/skill-framework/shared/codebase-design-principles.md) is
normative. **Facts belong to the skill; decisions belong to the user.** The skill retrieves repository
evidence and builds a decision tree; it never treats its own recommendation as the user's approval, and it
never silently resolves a decision on their behalf.

Every decision node states its dependencies, options, and evidence. A node is on the frontier only when
every node it `depends_on` is resolved — independent nodes may share a frontier, but a dependent node is
never asked alongside an unresolved prerequisite. Each round: compute the frontier, ask only frontier
questions, recommend an option with rationale for each, ask the user to decide, record the decision, and
recompute. The interview stops once every material decision is resolved or the user explicitly leaves the
frontier open — it never runs unbounded. In `unattended: true` composition, an unresolved material
frontier returns `BLOCKED` with the frontier attached rather than synthesizing an answer.

## Pipeline

`Inputs → Tree → Frontier → Interaction → Report`

See [SKILL.md](SKILL.md) for the contract and [examples.md](examples.md) for invocation patterns.
