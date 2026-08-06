# Markdown renderer

Transform `decision_graph` → DORA markdown. **No reasoning** — field mapping and label translation only.

Presentation rules: [workflow/report.md](../workflow/report.md). Section order: [report-schema.md](../reference/report-schema.md).

## Render modes

| Mode | Human Report | Appendix |
|------|--------------|----------|
| `full` (default) | Yes | Decision Graph + Evidence Registry + metadata/validation |
| `summary_only` | Yes | Omit |

## Graph → section mapping

### Human Report

| Graph path | Section slug | Human heading | Template |
|------------|--------------|---------------|----------|
| `assessment.*` | `ExecutiveSummary` | Recommendation | [human-report.md](../templates/human-report.md) |
| `observations[]` (health subset) | `CurrentHealth` | Current Health | [human-report.md](../templates/human-report.md) |
| `decisions[]`, `why_this_matters[]` | `OptimizationDecision` | Optimization Decision | [human-report.md](../templates/human-report.md) |
| `observations[]`, `evidence[]` | `EvidenceSummary` | Evidence | [human-report.md](../templates/human-report.md) |
| `recommendations[]` (not REJECTED) | `RecommendationsSummary` | Recommendations | [human-report.md](../templates/human-report.md) |
| `recommendations[]` (REJECTED only) | `RejectedChanges` | Changes evaluated but not recommended | [human-report.md](../templates/human-report.md) |
| `stop_reasons[]`, rec risks | `RisksSummary` | Risks | [human-report.md](../templates/human-report.md) |
| `assessment.*` + top rec | `Conclusion` | Conclusion | [human-report.md](../templates/human-report.md) |

### Technical Appendix (full mode only)

| Graph path | Appendix section | Template |
|------------|------------------|----------|
| `decisions[]`, `why_this_matters[]`, `assumptions[]` | Decision Graph | [decision.md](../templates/decision.md) |
| `observations[]`, `evidence[]`, `recommendations[]` | Evidence Registry | [observations.md](../templates/observations.md), [evidence.md](../templates/evidence.md), [recommendations.md](../templates/recommendations.md) |
| `metadata.*`, `decision_history` | Assessment Metadata | [metadata.md](../templates/metadata.md) |
| validation output, `contradictions[]` | Validation | [contradictions.md](../templates/contradictions.md) |
| `appendix`, `telemetry`, `trends[]`, `interpretations[]` | Evidence Registry (extended) | [appendix.md](../templates/appendix.md), [telemetry.md](../templates/telemetry.md), [trends.md](../templates/trends.md), [interpretation.md](../templates/interpretation.md) |

## Label translation

Map `OBS_*` → human label via [observation-ids.md](../reference/observation-ids.md) description column. Examples:

| ID | Human label |
|----|-------------|
| `OBS_CPU_USAGE_AVG` | CPU average (7d) |
| `OBS_CPU_P95_FLEET` | Fleet CPU p95 |
| `OBS_DERIVED_CPU_UTIL_P95` | Fleet CPU p95 as % of request |
| `OBS_MEMORY_MAX_POD` | Memory peak (worst pod) |

Map `DEC_*` / `REC_*` → short titles from [decision-ids.md](../reference/decision-ids.md) / [recommendation-ids.md](../reference/recommendation-ids.md).

Map `assessment.final_decision` enum → plain English + emoji per [human-report.md](../templates/human-report.md#executivesummary).

## EvidenceSummary sort order

When rendering the Evidence table, sort rows by **operational importance**:

1. Fleet CPU p95 (`OBS_CPU_P95_FLEET`, `OBS_DERIVED_CPU_UTIL_P95`) — include throttle in Notes
2. Kafka lag (`OBS_KAFKA_LAG_*`)
3. Memory peak (`OBS_MEMORY_MAX_POD`)
4. HPA (`OBS_HPA_*`, replica/HPA fields)
5. CPU average (`OBS_CPU_USAGE_AVG`)
6. HTTP metrics (latency, error rate, RPS)
7. Restarts (`OBS_RESTART_*`)
8. Manifest drift (`MANIFEST_*` vs `RUNNING_*`)

Omit rows with no data unless the gap is material (then note as missing).

## ExecutiveSummary fields (human)

Rendered as **`## Recommendation`**. **Lead with changes, then holds** — see [human-report.md](../templates/human-report.md#lead-with-changes-then-holds).

```text
{emoji} Recommendation

{primary action — what changes; include values/range when known}.

{what stays unchanged + brief why; omit second line when pure KEEP with no secondary holds}.

Severity: {assessment.severity} — {assessment.severity_reason}
Assessment confidence: {band} ({assessment.assessment_confidence.value})

Basis:
• Evidence completeness — {short clause}
• Evidence quality — {short clause}
• Telemetry coverage — {short clause}
• Contradiction resolution — {short clause}

Review again in: {assessment.review_after}
```

Do **not** emit `SCHEMA_VERSION`, numeric confidence arithmetic, or `{assessment.assessment_confidence.arithmetic}` in the Human Report.

## RecommendationsSummary sort order

When rendering the Recommendations section, sort rows (excluding `REJECTED`) by **action tier** first — concrete work before holds; observability before sizing when both are present:

| Tier | Rec patterns | Human intent |
|------|--------------|--------------|
| **1 — Observability** | `REC_KAFKA_LAG_INSTRUMENT`, `REC_PARTITION_VALIDATE`, `REC_SLO_BASELINE`, `REC_HPA_OBSERVE`, `REC_MANIFEST_RECONCILE`, `REC_CPU_DIST_QUERY`, `REC_RESTART_INVESTIGATE`, `REC_*_OBSERVE` | Instrument, validate, observe — highest-leverage concrete work |
| **2 — Actionable change** | `READY` / `COMPLETED` on `REC_*_INCREASE`, `REC_*_REDUCE`, `REC_HPA_ADJUST`, `REC_HPA_EVALUATE`, `REC_SIDECAR_ACCOUNT`; `DEFERRED` change recs that are not Tier 1 or Tier 3 | Resource or HPA changes ready (or waiting on evidence) |
| **3 — Hold** | `REC_*_KEEP`, `REC_REPLICA_KEEP`; `BLOCKED` + keep/observe intent | **Decision: Keep** — no change recommended |

Within each tier, tie-break in order: graph `priority` (`P0` → `P1` → `P2`) → decision confidence (desc) → expected benefit (desc) → engineering effort (asc).

Derive `{priority}` labels from final sort position: Tier 1 → `P0`; Tier 2 → `P1`; Tier 3 → `P2` (use `P3` only when multiple holds need distinct ordering).

**Golden order (bursty Kafka + memory headroom):** Instrument Kafka lag → Raise memory → Keep CPU → Keep replicas.

Full rule: [recommendation-framework.md](../recommendation-framework.md#ordering-rule).

## RecommendationsSummary fields (human)

```text
**{priority} — {title}**
Decision: Keep | Ready | Defer | Blocked
Decision confidence: {band} ({numeric})
{rationale prose}
```

Map graph `status` → human line by rec intent:

- `READY` / `COMPLETED` → **Ready**
- `DEFERRED` → **Defer**
- `BLOCKED` + `REC_*_KEEP` / `REC_*_OBSERVE` → **Decision: Keep**
- `BLOCKED` + change rec → **Blocked**
- `REJECTED` → render in **RejectedChanges** only — not in RecommendationsSummary

## Appendix recommendation status

Map graph `status` → appendix **State** (LifecycleSummary table and per-`REC_*` detail). Graph JSON keeps raw enum.

| Graph `status` | Rec pattern | Appendix State |
|----------------|-------------|----------------|
| `BLOCKED` | `REC_*_KEEP`, `REC_*_OBSERVE` | **KEEP** |
| `BLOCKED` | actionable change blocked by STOP_REASON / dependency | **BLOCKED** |
| `READY` / `COMPLETED` | actionable change | **CHANGE** |
| `DEFERRED` | | **DEFER** |
| `REJECTED` | | **NOT RECOMMENDED** |

Do **not** emit graph enum values (`BLOCKED`, `READY`, …) in appendix recommendation State fields when a display label exists above.

**`delivery_pointer` rendering:**

- `verified: true` — render as: `Where to apply: \`<path>\` (\`<field>\`)`
- `verified: false` on a DEFERRED rec — render as: `Where to apply: \`<path>\` (\`<field>\`) ⚠️ *path unconfirmed — verify before applying*`

Never reach RENDER with READY actionable recs missing `delivery_pointer.path` or `verified: true`
(INV-12 critical). If
`invariant_violations[]` lists INV-12, emit graph + violations only — do not author Human Report.

## RejectedChanges fields (human)

Omit section when no `REJECTED` recs.

```text
**{title}** — Not recommended.
{rationale prose}
Decision confidence: {band} ({numeric})
```

## RisksSummary fields (human)

```text
Overall: {one sentence derived from stop_reasons and blocked dimensions}

- **{risk category}** — {detail}
```

## Conclusion fields (human)

```text
{2–4 sentences — restate recommendation, key constraint, review cadence}
```

No agent mode instructions, posting confirmations, or MCP setup steps.

## AssessmentMetadata fields (appendix)

```text
SCHEMA_VERSION=3
FINAL_DECISION: {assessment.final_decision}
ASSESSMENT_CONFIDENCE: {assessment.assessment_confidence.value} ({band})

Derived from:
• Evidence completeness
• Evidence quality
• Telemetry coverage
• Contradiction resolution
```

Store `assessment.assessment_confidence.arithmetic` in the graph for invariants — **do not** render in default appendix. Formula: [reference/confidence-formula.md](../reference/confidence-formula.md).

## Assessment metadata footer

After Human Report **Conclusion** (and duplicated at end of full DORA before appendix separator when
useful for parsers), emit fenced YAML:

```yaml
assessment_metadata:
  assessment_type: full | repeat
  started: "<from graph.metadata.started>"
  finished: "<from graph.metadata.generated>"
  service: "<assessment.service>"
  final_decision: KEEP_CONFIGURATION
  assessment_confidence: 0.9
  assessment_complete: true
  history: { ... }              # when decision_history present
  precision: { ... }
  investigation_quality: { ... }
```

Map `precision` from `recommendations[]` lifecycle counts and `investigation_quality` from
`assessment.assessment_confidence` factors. Field rules: [workflow/report.md](../workflow/report.md)
§Assessment metadata footer.

## DRY rules

| Layer | Values | IDs |
|-------|--------|-----|
| Graph + appendix | Observations table only | Everywhere else in appendix |
| Human Report | Inline with human labels | **Never** |

## Canvas

Large appendix tables → **canvas** skill (optional). Human Report should stay prose-first (~2–4 pages).
