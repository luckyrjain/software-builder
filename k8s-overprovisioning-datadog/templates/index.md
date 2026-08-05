# Markdown renderer templates

**Not authoring forms** — layout specs for [render/markdown.md](../render/markdown.md).

Source: `decision_graph` ([decision-graph-schema.md](../reference/decision-graph-schema.md)).
Presentation: [workflow/report.md](../workflow/report.md).

```text
schema_version: 3
skill_version: v3.0
```

## Human Report (primary)

| Slug | Template | Graph paths | Human heading |
|------|----------|-------------|---------------|
| ExecutiveSummary | [human-report.md](human-report.md) | `assessment.*` | Recommendation |
| CurrentHealth | [human-report.md](human-report.md) | `observations[]` (health subset) | Current Health |
| OptimizationDecision | [human-report.md](human-report.md) | `decisions[]`, `why_this_matters[]` | Optimization Decision |
| EvidenceSummary | [human-report.md](human-report.md) | `observations[]`, `evidence[]` | Evidence |
| RecommendationsSummary | [human-report.md](human-report.md) | `recommendations[]` (not REJECTED) | Recommendations |
| RejectedChanges | [human-report.md](human-report.md) | `recommendations[]` (REJECTED only) | Changes evaluated but not recommended |
| RisksSummary | [human-report.md](human-report.md) | `stop_reasons[]`, rec risks | Risks |
| Conclusion | [human-report.md](human-report.md) | `assessment.*` + top rec | Conclusion |

## Technical Appendix (full DORA)

| Section | Template(s) | Graph paths |
|---------|-------------|-------------|
| Decision Graph | [decision.md](decision.md), [assumptions.md](assumptions.md) | `decisions[]`, `why_this_matters[]`, `assumptions[]` |
| Evidence Registry | [observations.md](observations.md), [evidence.md](evidence.md), [recommendations.md](recommendations.md), [appendix.md](appendix.md) (extended) | `observations[]`, `evidence[]`, `recommendations[]`, `appendix`, `telemetry`, `trends[]`, `interpretations[]` |
| Assessment Metadata | [metadata.md](metadata.md), [executive-decision.md](executive-decision.md) | `metadata.*`, `decision_history`, confidence factors |
| Validation | [contradictions.md](contradictions.md) | `contradictions[]`, invariant results |

Legacy appendix letters (A–E) and section names (`ExecutiveDecision`, `Metadata`, …) map to the rows above when rendering machine-oriented blocks.
