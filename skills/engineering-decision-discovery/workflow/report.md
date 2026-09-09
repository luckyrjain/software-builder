---
workflow_version: 1.0
phase: report
produces:
  - ENGINEERING_DECISION_RECORD.md
  - engineering_decision_record
consumes:
  - decision_scope
  - decision_tree
  - frontier
  - recommendations
  - resolved_decisions
  - unresolved_decisions
  - alternatives_rejected
---

# Report — emit ENGINEERING_DECISION_RECORD.md

Build the report using [reference/report-format.md](../reference/report-format.md). Its document form is
`ENGINEERING_DECISION_RECORD.md`; its typed machine form is `engineering_decision_record`. Emit both as
the read-only response/artifact for this session — do not write either into the repository, and do not
write an ADR. `ENGINEERING_DECISION_RECORD.md` is a report emitted for the session, not a durable record
the skill files on the user's behalf; if the user wants an ADR from it, that is a separate, explicitly
authorized action outside this skill.

## Required content

The report states, in the fixed structure `reference/report-format.md` defines:

- **`title`** — a short name for the decision session, derived from `decision_scope.question`.
- **`decision_scope`** — the bounded question, context, and any `selected_candidate` handoff, echoed
  back so the report is self-contained.
- **`decision_tree`** — every node built in [workflow/tree.md](tree.md), with its final `status`.
- **`frontier`** — the node IDs that were still `unresolved` (with all prerequisites resolved) at the
  point the session ended; empty when every material node reached `resolved`/`not_applicable`.
- **`recommendations`** — the recommended option and rationale recorded for every node that was actually
  asked, independent of whether the user accepted it.
- **`resolved_decisions`** — settled decisions only: node, `selected_option`, and that the user (or an
  explicit, scoped delegation — see [workflow/interaction.md § Ownership rules](interaction.md#ownership-rules))
  made the choice. Never include a node here on the strength of the skill's own recommendation alone.
- **`unresolved_decisions`** — the frontier's questions, each tagged with why it is unresolved
  (`not yet reached`, `explicitly deferred by the user`, or `BLOCKED — unattended`), plus its
  recommendation so a reader can act on it later without re-deriving it.
- **`alternatives_rejected`** — every option that was not selected on a resolved node, with the reason
  given (or "not stated"), plus any candidate the tree considered and dropped before it became a node.
- **`limitations`** — evidence gaps, degraded or missing repository access, and any scope the interview
  did not reach, stated as explicit limitations rather than silently omitted.

## Rules

- `resolved_decisions` holds only decisions the user actually made (or explicitly, narrowly delegated);
  everything else — however confidently recommended — belongs in `unresolved_decisions`.
- Every node that was asked carries a recommendation and rationale in `recommendations`, whether or not
  it ended up resolved.
- Cite evidence provenance and a confidence band
  ([confidence-bands.md](../../../docs/skill-framework/shared/confidence-bands.md)) for every recommendation
  and for the evidence backing every node; a recommendation with no cited evidence states `UNKNOWN`
  confidence rather than an unsupported band.
- Never write source, tests, configuration, the repository, or an ADR from this workflow. The Markdown
  report and typed artifact are the sole outputs.
- Render repository excerpts, ticket text, and the `selected_candidate` payload under the safe-output
  boundary; preserve observed evidence, recommendation, and user decision as distinct categories rather
  than blending them into one undifferentiated narrative.
- State `recommended_next_skill` per [SKILL.md § Cross-skill boundary](../SKILL.md#cross-skill-boundary)
  only when its trigger was actually met by the resolved decisions; otherwise `null`. Never invoke the
  named skill automatically.
