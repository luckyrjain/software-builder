---
workflow_version: 1.0
phase: draft
produces:
  - questions
consumes:
  - decision_context
  - recipient
---

# Draft — identify the gap, group questions by theme

1. **Find the gap.** Compare what `recipient`'s stated role/expertise implies they know against
   what `decision_context` says the caller needs back. The questionnaire only targets this gap —
   not a generic checklist, and not anything the caller could reasonably answer from the
   repository or their own context (check repository evidence first; a question already answered
   in the repository doesn't need asking).
2. **Group by theme.** Once there are more than a handful of questions, group them under a theme
   heading. Order themes and questions within each theme most-important-first — the recipient may
   only get one pass, especially async.
3. **Write each question as one idea.** Never compound ("what's the load AND the budget" is two
   questions). Add a one-line "why this matters" only where the question could be misread or
   invite a throwaway answer — not on every question.
4. **Never fabricate an answer.** If the caller's own context could plausibly fill in a stub, ask
   the question anyway rather than guessing — the whole point is that this specific person's
   knowledge is missing, not assumed.
