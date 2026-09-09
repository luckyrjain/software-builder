# Smoke test — research-brief

Run after install or any substantive edit. Use a real, bounded research question answerable from this
repository's own evidence, plus one external-documentation angle that needs `host.web.search`/
`host.web.fetch`. The skill remains read-only: inspect and emit a report; do not modify source, tests,
configuration, docs, or any other fixture repository state.

Conventions: [smoke-test-conventions](../../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> `research_question: <a real bounded question>`

Example: `research_question: Does this repository's rate limiter apply per IP address or per API key?`
Run it twice: once with `host.web.search`/`host.web.fetch` available (repository evidence plus any
external documentation the question needs), and once in degraded mode without them (repository
evidence only).

## A correct minimal output contains

1. A HARD STOP if `research_question` is absent.
2. Repository evidence and (when available) external evidence, each labeled with its cited source.
3. At least one finding with a stated evidence status (OBSERVED/INFERRED/UNKNOWN/CONFLICTED), or an
   explicit statement that none could be gathered.
4. Any claim with no citable source rendered as `UNKNOWN` — never asserted as fact.
5. An unresolved-questions entry for any real evidence gap, or an explicit statement that none exist.
6. `RESEARCH_BRIEF.md` / `research_brief` emitted as a report only — no source, test, configuration, or
   doc write, and no automatic downstream invocation.

## Degraded paths

| Condition | Expected behavior |
|-----------|---------------------|
| No `research_question` named | HARD STOP — ask for the bounded question to investigate |
| `host.web.search`/`host.web.fetch` unavailable | Proceed repository-only; mark every external-dependent claim `UNKNOWN`; state the degraded mode explicitly |
| No citable source exists for a claim | Render that claim `UNKNOWN`; never assert it as fact |
| Research question actually spans multiple independent sub-questions | Ask which one to start with; do not attempt an unbounded "everything about X" pass |
| Caller asks the skill to edit repository files or open a PR with the findings | Reject the write; emit `RESEARCH_BRIEF.md` as a report only |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
