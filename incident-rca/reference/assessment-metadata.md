# Assessment metadata footer (incident-rca)

Machine-readable YAML emitted at Phase 5 closeout. Normative shared blocks:
[review-metadata-schema.md](../../docs/skill-framework/shared/review-metadata-schema.md) §8.1.

## When to emit

Append a fenced ` ```yaml ` block under **Appendix — machine metadata** (after **Conclusion**). Include
in the report file and chat when delivering the full report. **Do not** include in Confluence/wiki
export or Jira narrative paste — executives do not need machine metadata in the main artifact.

| Block | When |
|-------|------|
| **Core** (`assessment_type`, `service`, `incident_window`, `primary_hypothesis`, `confidence`) | Every complete RCA |
| **`history`** | Re-run on same incident/service when prior `assessment_metadata` is parseable |
| **`precision`** | Every RCA where Phase 4 ranked hypotheses |
| **`investigation_quality`** | When computable; omit on partial/stopped reports |

Omit `history` on first investigation with no prior footer.

## `history` — investigation iterations

Analogous to pr-review `history.approval_iteration` — tracks RCA re-runs on the same incident or
service within a rolling window.

```yaml
history:
  investigation_iteration: 2
  first_investigation:
    finished: "2026-06-27T10:00:00Z"
    primary_hypothesis: infra_capacity
    confidence: medium
  prior_investigation:
    finished: "2026-06-28T08:00:00Z"
    primary_hypothesis: deploy_regression
    confidence: high
```

| Field | Rule |
|-------|------|
| `investigation_iteration` | Count of prior parseable `assessment_metadata` on same service/incident + 1 |
| `first_investigation` | Earliest parseable footer snapshot |
| `prior_investigation` | Immediately preceding footer snapshot |

**Snapshot fields:** `finished`, `primary_hypothesis`, `confidence` (band lowercase).

## `precision` — hypothesis and signal selectivity

```yaml
precision:
  hypotheses_evaluated: 5
  hypotheses_ranked: 2
  primary_score: 0.88
  signals_total: 8
  signals_in_window: 7
  counter_evidence_count: 2
  correlator_sha: null
```

| Field | Rule |
|-------|------|
| `hypotheses_evaluated` | Hypothesis types considered in Phase 4 |
| `hypotheses_ranked` | Hypotheses with score ≥ 50% of primary in report |
| `primary_score` | Numeric score of primary hypothesis (0–1) |
| `signals_total` | Counted signals in evidence bundle |
| `signals_in_window` | Signals with `detected_at` within incident window |
| `counter_evidence_count` | Signals that ruled out alternates |
| `correlator_sha` | `optionalExternal.incident-rca-correlator-cli.commitSha` from `skills-lock.json` when the correlator CLI ranked this run's hypotheses; `null` when [manual-scoring.md](manual-scoring.md) was used instead — this is what makes the pin in `skills-lock.json` ([dependencies.md](../dependencies.md)) actually reproducible per-report, not just recorded and unused |
| `process_failure` | `true` when trigger Unknown and mandatory KubeSense log fallback skipped while KubeSense ✅ |
| `observability_backend_error` | `true` when KubeSense returned backend fetch error (distinct from skip) |

On first investigation with no prior footer: omit prior-resolution fields (none apply).

## `investigation_quality` — coverage and evidence depth

Schema extension of pr-review `review_quality` — same field types, RCA-specific semantics.

```yaml
investigation_quality:
  coverage_pct: 100
  evidence_pct: 90
  source_diversity: 3
  confidence: high
```

| Field | Rule |
|-------|------|
| `coverage_pct` | Phases completed / 5 (Phase 0–4) × 100; cap at 80 for partial stop |
| `evidence_pct` | Share of evidence rows with deep links and confidence ≥ medium |
| `source_diversity` | Distinct MCP sources (datadog, gitlab, jira, …) with ≥1 signal |
| `confidence` | Overall band — same as top-level `confidence` |

## Complete example

```yaml
assessment_metadata:
  assessment_type: full
  started: "2026-06-28T15:00:00Z"
  finished: "2026-06-28T15:22:00Z"
  service: neo-disbursement-service
  incident_window:
    from: "2026-06-28T14:00:00Z"
    to: "2026-06-28T16:00:00Z"
  primary_hypothesis: deploy_regression
  confidence: high
  assessment_complete: true
  precision:
    hypotheses_evaluated: 5
    hypotheses_ranked: 2
    primary_score: 0.88
    signals_total: 8
    signals_in_window: 7
    counter_evidence_count: 2
  investigation_quality:
    coverage_pct: 100
    evidence_pct: 90
    source_diversity: 3
    confidence: high
    process_failure: false
    observability_backend_error: false
```
