# stakeholder-questionnaire

Turn an unresolvable decision into a discovery questionnaire for one named recipient. This
ambient, **read-only**, report-only skill drafts `STAKEHOLDER_QUESTIONNAIRE.md` and the typed
`stakeholder_questionnaire`; it does not send, post, or write the questionnaire anywhere — it is
the response/artifact itself.

Use it to turn a decision you can't resolve alone into targeted questions for a specific person who
holds the missing knowledge, grouped by theme, most-important-first.

A questionnaire is proposed only when both `decision_context` and `recipient` are named: a specific
decision that's blocked by one person's knowledge, and a specific person whose expertise is the gap.

## When to use

- The blocker is one named person's knowledge, not your own reasoning
- Questions need to target the specific gap between what the recipient knows and what's needed
- A discovery document to hand to one person, async or in a meeting

Do not use it for a decision you can answer with enough interrogation
(`engineering-decision-discovery`), or turning already-answered questions into a PRD
(`prd-architect`).

## Pipeline

`Inputs → Draft → Report`

See [SKILL.md](SKILL.md) for the full contract and [examples.md](examples.md) for invocation patterns.
