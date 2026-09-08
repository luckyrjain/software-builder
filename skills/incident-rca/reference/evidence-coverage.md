# Evidence coverage dashboard

Load in **Phase 4** (compute) and **Phase 5** (render). Explains *why* confidence capped below HIGH
even when substantial telemetry exists.

## Domains to assess

For each domain, record **status**, **coverage %**, **freshness**, and whether it **blocks** higher confidence.

| Domain | Typical sources | N/A when |
|--------|-----------------|----------|
| Traces | Datadog APM, KubeSense traces | Pure infra-only with no APM |
| Logs | KubeSense MCP `body` (+ SPL fallback); Datadog logs only if org ingests them | acme: Datadog logs **N/A** — assess KubeSense counts + MCP body, not Datadog log queries |
| Metrics | Datadog metrics, KubeSense metrics | — |
| Deploy metadata | `get_change_stories`, Jenkins | No deploy hypothesis |
| Git diff | GitLab MR/commit diff | No deploy in window |
| Customer telemetry | Datadog RUM, business metrics | Backend-only incident |
| Feature flags | `get_change_stories` feature_flag | No flag hypothesis |
| Infrastructure events | K8s metrics, infra_signals | App-only incident |
| Tickets | Jira | Optional — not blocking |

## Status values

| Status | Coverage % | Meaning |
|--------|------------|---------|
| **Complete** | 100 | Queried; sufficient rows/signals in incident window |
| **Partial** | 50–90 | Queried; gaps (truncation, partial window, metadata-only) |
| **Missing** | 0 | Not queried, auth failed, or zero rows |
| **N/A** | — | Excluded from overall completeness denominator |

## Evidence freshness

Record when the signal was **collected relative to incident end** — stale collection lowers effective confidence.

| Freshness | Rule |
|-----------|------|
| **Fresh** | Collected within **15 min** of `window.to_time` |
| **Acceptable** | Collected within **4 hours** of `window.to_time` |
| **Stale** | Collected **>4 hours** after `window.to_time` — note in Gaps; downgrade quality one step if used for HIGH |

Example matrix footnote: *Observed — trace — collected 3 min after incident end*.

## Overall completeness

```text
overall_pct = round(100 × sum(coverage_pct for non-N/A domains) / (100 × count(non-N/A domains)))
```

Round to nearest integer. Show in report **Evidence coverage** section.

## Confidence ceiling

The **maximum band** allowed given coverage gaps (apply before final band; may be lower than score suggests).

| Blocking condition | Ceiling |
|--------------------|---------|
| Single observability source | **MEDIUM** |
| Git diff **Missing** when `deploy_regression` is top hypothesis | **MEDIUM** |
| Traces **Missing** when cascade/dependency hypothesis | **MEDIUM** |
| Any **critical** domain Missing (logs + metrics both Missing) | **LOW** |
| Unresolved contradictory evidence | **MEDIUM** |
| Overall completeness **<70%** | **MEDIUM** |
| Overall completeness **<50%** | **LOW** |

List **blocking gaps** explicitly: e.g. *Git diff unavailable*, *Feature flags not queried*.

## Report section template

```markdown
## Evidence coverage

| Domain | Status | Coverage | Freshness | Notes |
|--------|--------|----------|-----------|-------|
| Traces | ✅ Complete | 100% | Fresh | APM spans in window |
| Logs | ✅ Complete | 100% | Acceptable | |
| Metrics | ✅ Complete | 100% | Fresh | |
| Deploy metadata | ✅ Complete | 100% | Fresh | change stories |
| Git diff | ⚠ Missing | 0% | — | Blocks deploy HIGH |
| Customer telemetry | ⚠ Partial | 65% | Stale | RUM sampled |
| Feature flags | ❌ Missing | 0% | — | Not queried |
| Infrastructure events | ✅ Complete | 100% | Fresh | |
| Tickets | ✅ Complete | 100% | Fresh | INC-4521 |

**Overall investigation completeness:** 91%

**Confidence ceiling:** MEDIUM

**Blocking gaps:** Git diff unavailable
```

Mirror `overall_pct`, `confidence_ceiling`, and `blocking_gaps` into `assessment_metadata.investigation_quality`
when emitting the footer ([assessment-metadata.md](assessment-metadata.md)).
