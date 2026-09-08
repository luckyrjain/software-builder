# Report schema (markdown view)

Rendered markdown follows this section contract. **Source of truth:** `decision_graph` ([decision-graph-schema.md](decision-graph-schema.md)).

Presentation spec: [workflow/report.md](../workflow/report.md). Layout: [report-template.md](../report-template.md).

```text
SCHEMA_VERSION=3
SKILL_VERSION=v3.0
```

*(Schema tokens above are appendix-only — do not emit in the Human Report body.)*

## Human Report (fixed order — primary output)

| Slug | Graph paths | Human label | Template |
|------|-------------|-------------|----------|
| `ExecutiveSummary` | `assessment.*` | Recommendation | [human-report.md](../templates/human-report.md) |
| `CurrentHealth` | `observations[]` (CPU, memory, replica subset) | Current Health | [human-report.md](../templates/human-report.md) |
| `OptimizationDecision` | `decisions[]`, `why_this_matters[]` | Optimization Decision | [human-report.md](../templates/human-report.md) |
| `EvidenceSummary` | `observations[]`, `evidence[]` | Evidence | [human-report.md](../templates/human-report.md) |
| `RecommendationsSummary` | `recommendations[]` (not REJECTED) | Recommendations | [human-report.md](../templates/human-report.md) |
| `RejectedChanges` | `recommendations[]` (REJECTED only) | Changes evaluated but not recommended | [human-report.md](../templates/human-report.md) |
| `PostChangeVerification` | `recommendations[]` (READY only) | Post-change verification | [human-report.md](../templates/human-report.md#postchangeverification) — conditional, appended only when ≥1 READY change recommendation exists ([workflow/report.md](../workflow/report.md)) |
| `RisksSummary` | `stop_reasons[]`, risk fields on recs | Risks | [human-report.md](../templates/human-report.md) |
| `Conclusion` | `assessment.*` + top rec | Conclusion | [human-report.md](../templates/human-report.md) |

Human-report rules: no `OBS_*` / `DEC_*` / `REC_*` / `EVID_*`; emoji recommendation block; evidence sorted fleet p95 → Kafka lag → memory peak → HPA → CPU avg → HTTP → restarts → manifest; recommendations sorted observability → actionable change → hold (golden: Instrument Kafka lag → Raise memory → Keep CPU → Keep replicas); Decision and Decision confidence on separate lines; assessment confidence band + basis bullets (no arithmetic); no agent mode instructions; < 20 uppercase identifiers.

## Technical Appendix (fixed order — full DORA only)

Emitted after `---` / `## Technical Appendix`. Omitted in summary-only mode.

| Section | Slug | Graph paths | Template |
|---------|------|-------------|----------|
| Decision Graph | `DecisionGraph` | `decisions[]`, `why_this_matters[]`, `assumptions[]` | [decision.md](../templates/decision.md) |
| Evidence Registry | `EvidenceRegistry` | `observations[]`, `evidence[]`, `recommendations[]` | [observations.md](../templates/observations.md), [evidence.md](../templates/evidence.md), [recommendations.md](../templates/recommendations.md) |
| Assessment Metadata | `AssessmentMetadata` | `metadata.*`, `decision_history` | [metadata.md](../templates/metadata.md) |
| Validation | `Validation` | invariant results, `contradictions[]` | [contradictions.md](../templates/contradictions.md), [validate-invariants.md](../workflow/validate-invariants.md) |
| Extended detail | `ExtendedDetail` | `appendix`, `telemetry`, `trends[]`, `interpretations[]` | [appendix.md](../templates/appendix.md), [telemetry.md](../templates/telemetry.md), [trends.md](../templates/trends.md), [interpretation.md](../templates/interpretation.md) |

Legacy slug `ExecutiveDecision` maps to Human `ExecutiveSummary` (emoji recommendation layout) plus assessment-confidence factors in `AssessmentMetadata` (no formula arithmetic).

Renderer: [render/markdown.md](../render/markdown.md). Template index: [templates/index.md](../templates/index.md).

## Rules

1. Build graph first — never author markdown as primary artifact
2. DRY in **graph and appendix** — values in `observations[]`; elsewhere reference IDs
3. **Human Report inverts DRY for readability** — repeat values with human labels; never expose registry IDs
4. `ASSESSMENT_CONFIDENCE` ≠ `RECOMMENDATION_CONFIDENCE` (appendix may show both numerically; human view shows bands only)
5. Invariants INV-01–INV-14 must pass before render; results → Validation appendix only
