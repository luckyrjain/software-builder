---
workflow_version: 1.0
phase: classify
produces:
  - issues_classified
consumes:
  - issues
---

# Classify — category, severity, duplicate-of, recommended owner

For each issue in `issues`:

1. **Category** — bug, feature request, question, security, or duplicate. Cite the text that supports
   the chosen category.
2. **Severity** — cite evidence (user-facing impact, blocking vs. cosmetic, affected scope) rather
   than a bare guess.
3. **Duplicate-of** — check for an evidence match (matching symptom, matching stack trace, matching
   repro) against other issues in this batch or repository-visible prior issues. Record "none found"
   rather than a proximity-based guess.
4. **Recommended owner** — cite CODEOWNERS, squad-map data, or prior-handling evidence; record
   "unclear — no ownership evidence found" rather than guessing.
5. **Incident check** — if the issue describes active, ongoing user-facing impact right now (not a
   past occurrence), flag it for the `incident-rca` escalation instead of routine backlog handling.

Never silently skip an issue with insufficient detail — record what's missing as part of its
classification.
