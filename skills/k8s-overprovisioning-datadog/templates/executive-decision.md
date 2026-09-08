<!-- Markdown renderer layout — Appendix metadata only. Human summary: human-report.md -->

## ExecutiveDecision

**Assessment Metadata block** — do not emit in the Human Report.

```text
SCHEMA_VERSION=3
FINAL_DECISION: {assessment.final_decision}
ASSESSMENT_SEVERITY: {assessment.severity}
ASSESSMENT_SEVERITY_REASON: {assessment.severity_reason}
REVIEW_AFTER: {assessment.review_after}

ASSESSMENT_CONFIDENCE: {assessment.assessment_confidence.value} ({band})

Derived from:
• Evidence completeness
• Evidence quality
• Telemetry coverage
• Contradiction resolution
```

Store `{assessment.assessment_confidence.arithmetic}` in the graph for INV-07 — **do not** render in default appendix. Formula: [confidence-formula.md](../reference/confidence-formula.md).

Human Report uses [human-report.md](human-report.md#executivesummary) — emoji decision block + band, no arithmetic, no `DEC_*`/`REC_*` references. **Lead with changes, then holds** in the recommendation lead block ([lead-with-changes-then-holds](human-report.md#lead-with-changes-then-holds)).
