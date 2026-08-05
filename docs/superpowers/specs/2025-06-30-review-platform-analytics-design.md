# Review Platform Analytics — Phase 1 Design

**Date:** 2025-06-30  
**Status:** Approved  
**Branch:** `cursor/skill-improvements-r3`  
**Sub-project:** B — Platform analytics (Phase 1)

## Problem

Sub-project A delivered evidence gates and a machine-readable `review_metadata` YAML footer on every
pr-review summary. EMs and framework maintainers still lack **trend metadata** across re-reviews on the
same MR: how many prior findings were resolved, whether regressions occurred, and whether review quality
(coverage, evidence depth, precision) is improving over approval iterations.

## Goals (Phase 1)

1. **Extend `review_metadata` v2** with `history`, `precision`, and `review_quality` blocks — backward
   compatible with existing v1 footers (`findings[]`, `findings_stats`, `review_hash`).
2. **Emit from pr-review Phase 5** on every review; populate `history` on incremental re-review when
   prior footer is parseable.
3. **Normative shared schema** in `docs/skill-framework/shared/review-metadata-schema.md` for
   cross-skill adoption.
4. **Stub `repository_health`** schema only — full rollup deferred.

## Non-goals (Phase 1)

- External dashboard application or UI
- Database or time-series storage
- incident-rca / k8s emission (documented as future consumers; not implemented here)
- Automated aggregation across MRs or repos

## Schema — `review_metadata` v2 extensions

All new blocks are **optional on first review** except `review_quality` (emit when metrics are
computable). On incremental re-review, emit `history` when prior `review_metadata` is available.

### `history` (incremental re-review)

Tracks review iterations on the same MR for trend dashboards that parse posted notes.

```yaml
history:
  approval_iteration: 2              # 1 = first bot review on MR; +1 each subsequent bot review
  first_review:
    head_sha: "<sha>"
    finished: "<ISO-8601>"
    findings_count: 3
    highest_severity: high
    recommendation: request_changes
  prior_review:                      # immediately preceding review (not always "second")
    head_sha: "<sha>"
    finished: "<ISO-8601>"
    findings_count: 1
    highest_severity: medium
    recommendation: comment
  regressions:                       # empty list when regression_check: pass
    - id: PRR-DATA-001
      location: payments/refund.py:88
      prior_status: fixed
      note: "Decimal fix reverted"
```

**Population rules:**

| Field | Source |
|-------|--------|
| `approval_iteration` | Count of prior `<!-- cursor-pr-review -->` notes with `review_metadata` + 1 |
| `first_review` | Earliest parseable `review_metadata` on MR (or current if first) |
| `prior_review` | Most recent prior `review_metadata` before current head |
| `regressions[]` | Findings with `status: fixed` in prior `findings[]` that reappear in diff |

Omit `history` entirely on first review when no prior footer exists.

### `precision`

Quantifies how well prior review feedback was addressed and how selective the reviewer was.

```yaml
precision:
  prior_total: 3
  prior_resolved: 3
  prior_resolved_pct: 100
  regression_count: 0
  regression_rate: 0.0                 # regression_count / prior_resolved (0 when prior_resolved=0)
  false_positives_withdrawn: 0         # prior findings marked fixed with no code change (author disputed)
  candidates: 12
  emitted: 3
  finding_precision: 0.25            # emitted / candidates after pipeline filters
```

Emit on every review where `review_metrics` was recorded in Phase 2. On first review, `prior_*` fields
are `0` / omitted.

### `review_quality`

Executive-summary quality signals for framework tuning (definitions in `review-metrics.md`).

```yaml
review_quality:
  coverage_pct: 100
  evidence_pct: 85                     # share of emitted findings with ≥1 anchor + conf high|medium
  confidence: high                     # overall review confidence band
  finding_precision: 0.25              # duplicate of precision.finding_precision for convenience
```

Omit on trivial mechanical MRs when all values would be N/A.

### `repository_health` (stub)

Reserved for cross-MR repo maturity rollup. Phase 1 emits schema placeholder only.

```yaml
repository_health:
  schema_version: 1
  # Deferred: CI, docs, lint, automation dimension scores
  # See review-metrics.md §Repository maturity
```

## Emitters

| Skill | Phase | Phase 1 scope |
|-------|-------|---------------|
| **pr-review** | Phase 5 footer | **Implement** — `history`, `precision`, `review_quality`, stub `repository_health` |
| incident-rca | Closeout | Future — adapt `history` for investigation iterations |
| k8s-overprovisioning-datadog | Human report | Future — adapt `precision` for recommendation confidence |

pr-review remains the reference implementation. Other skills link to
`docs/skill-framework/shared/review-metadata-schema.md` when they adopt the footer.

## Parsing prior footer (incremental)

Phase 1 step 3 and Phase 5 closeout:

1. Scan MR notes for latest `review_metadata` YAML block.
2. Extract `head_sha`, `findings[]`, `findings_stats`, `finished`, `recommendation`, `history` (if any).
3. Compute `approval_iteration` from note count.
4. Diff prior `findings[]` against current emission for `precision` and `history.regressions`.

Detail: `pr-review/reference/incremental-rerun.md` §Parsing prior metadata.

## Files changed (Phase 1)

| File | Change |
|------|--------|
| `docs/superpowers/specs/2025-06-30-review-platform-analytics-design.md` | This spec |
| `docs/skill-framework/shared/review-metadata-schema.md` | Normative v2 schema |
| `docs/skill-framework/README.md` | Link new shared file |
| `pr-review/workflow/phase-5.md` | Emit v2 blocks in footer |
| `pr-review/reference/incremental-rerun.md` | Parse prior footer → `history` |
| `pr-review/reference/review-metrics.md` | Wire definitions to footer fields |
| `pr-review/examples.md` | Golden YAML footer with `history` |
| `pr-review/reference/pressure-tests.md` | 1–2 new rows |
| `Makefile` | `lint-framework` includes new shared doc |

## Verification

```bash
make lint-pr-review
make lint-framework
```

## Future (Phase 2+)

- incident-rca / k8s footer parity
- `repository_health` full implementation from engineering-improvements signals
- Cross-MR aggregation scripts (out of repo; consumers parse posted YAML)
