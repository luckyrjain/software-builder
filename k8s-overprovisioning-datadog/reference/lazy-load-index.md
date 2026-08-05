# Lazy-load index

Read reference files **one at a time** when the active workflow phase says to.

| When | Also load |
|------|-----------|
| Prerequisites | [mcp-capabilities.md](mcp-capabilities.md) |
| COLLECT | [observation-ids.md](observation-ids.md), analysis modules as triggered |
| NORMALIZE | [observation-ids.md](observation-ids.md), [evidence-schema.md](evidence-schema.md) |
| REASON | [confidence-formula.md](confidence-formula.md), [precedence.md](precedence.md), [invariants.md](invariants.md) |
| VALIDATE | [evidence-weights.md](evidence-weights.md) |
| BUILD_GRAPH | [decision-graph-schema.md](decision-graph-schema.md), [decision-ids.md](decision-ids.md) |
| VALIDATE_INVARIANTS | [invariants.md](invariants.md) |
| RENDER | [gold-human-report-excerpt.md](gold-human-report-excerpt.md) (few-shot), [report-schema.md](report-schema.md), [templates/](../templates/) |
| Smoke / install | [smoke-test.md](smoke-test.md) |
| Maintainer edits | [pressure-tests.md](pressure-tests.md) |

[examples.md](../examples.md) is for humans — never bulk-load during a live assessment.
