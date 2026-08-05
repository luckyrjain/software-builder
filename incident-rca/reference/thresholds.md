# Confidence and signal thresholds

Numeric cutoffs for incident-rca. Categorical bands (HIGH / MEDIUM / LOW / UNKNOWN): [confidence-bands.md](../../docs/skill-framework/shared/confidence-bands.md).

Manual scoring weights: [manual-scoring.md](manual-scoring.md). Guardrails: [evidence-schema.md](evidence-schema.md).

## Confidence bands (incident-rca)

| Band | Required evidence |
|------|-------------------|
| **HIGH** | ≥2 independent signal **types** agree; counter-evidence stated; every counted signal `detected_at` within `[window.from_time, window.to_time]` |
| **MEDIUM** | One strong signal **or** only one **observability** source responded (hard cap — GitLab/Jenkins/Jira don't count) |
| **LOW** | Circumstantial / timing-only overlap **or** signals outside the incident window |
| **UNKNOWN** | Minimum evidence gate failed — `error_signals` and `infra_signals` both empty after Phases 1–3 |

**Single-source cap:** one **observability** source (Datadog, KubeSense, Prometheus, Loki — not
GitLab/Jenkins/Jira, which are change-management sources) responded → never exceed **MEDIUM**, regardless
of signal clarity.

**Additional caps** (full table: [evidence-quality.md](evidence-quality.md) §Confidence caps):

| Condition | Maximum band |
|-----------|--------------|
| Unresolved contradictory evidence | **MEDIUM** |
| Missing trigger after required investigation | **LOW** (trigger attribution) |
| Trigger Unknown | Root cause Unknown OK; never **HIGH** for full causal chain |
| Assumed evidence only | **LOW** |

**Multi-cause co-reporting:** when top-2 hypothesis raw scores are within **20%** of each other, report both with `"causality": "multi-cause"`. **Do not force a single root cause** when independent chains both have ≥2 signal types.

## Display format (report body)

Primary hypothesis confidence — **executive / human reports** use band + checklist only (no decimals):

```text
**Confidence:** HIGH

**Reason**
✓ Signal agreement — …
✓ Source diversity — …
✓ Counter-evidence — …
✓ Window coverage — …

**Remaining uncertainty**
- …
```

- **Do not** show `HIGH (0.88)` or similar decimals in Confluence, Jira, or manager-facing narrative —
  readers rarely gain value from 0.82 vs 0.85.
- Numeric `primary_score` belongs in **`assessment_metadata.precision`** only (platform analytics).
- Always include at least two **Reason** checkmarks; list gaps under **Remaining uncertainty**.

## Numeric score (metadata only)

Phase 4 ranking still computes normalized scores for hypothesis ordering. Mirror into
`assessment_metadata.precision.primary_score` — not the human report body.

| Factor | Effect on band |
|--------|----------------|
| ≥2 independent signal types | Supports HIGH when other gates met |
| Single observability source | Hard cap **MEDIUM** |
| Counter-evidence documented | Supports higher band |
| Immediate trigger unknown | Note under Remaining uncertainty — does not block infra-failure HIGH |
| Signals outside window | Cannot count toward HIGH/MEDIUM |
| Thin / sparse Phase 1 | Cap at MEDIUM or LOW |

## Signal density (Phase 1 checkpoint)

Quantitative definitions for the Phase 1 thin-signal summary ([workflow/phase-1.md](../workflow/phase-1.md)):

| Density | Definition |
|---------|------------|
| **Strong** | ≥1 signal with error rate **≥5×** baseline, **or** ≥10 distinct error log lines in window, **or** ≥1 infra signal (OOM, crashloop, HPA max) |
| **Sparse** | Exactly **1** weak signal: magnitude **<2×** baseline **or** &lt;5 log samples **or** signal covers **&lt;50%** of the incident window duration |
| **None** | `error_signals` and `infra_signals` both empty |

When **sparse**, ask the user before Phase 2: *"Signal is thin — continue to deploy correlation or stop here?"*

## Timing and magnitude cutoffs

| Rule | Threshold |
|------|-----------|
| Deploy → spike correlation window | 0–60 min (deploy_regression); 0–30 min (configuration_change, feature_flag_regression) |
| Signal outside incident window | &gt;0 min after `window.to_time` → cannot count toward HIGH/MEDIUM |
| `slo_breach` without error-rate corroboration | Cap at **MEDIUM** unless `magnitude > 10×` baseline |
| Kafka consumer lag spike | Lag **>10×** normal baseline |
| Cross-hypothesis penalty | Subtract **2** from competing hypothesis raw scores (see manual-scoring.md) |
| Phase 0b backstroke | `analysis_from_time = from_time − 15m` for Phase 1 queries |

## Expensive-query branch cutoffs

Apply when CPU/thread-pool/queue saturation is present **and** throughput is flat or **<2× baseline**
(see [query-investigation.md](query-investigation.md) §Step 4b):

| Signal | Threshold |
|--------|-----------|
| CPU saturation | ≥90% sustained ≥5 min in incident window |
| Thread-pool rejections | >0 reject events or reject metric >0 in window |
| Queue full | search/bulk queue at max **or** `queue_full` in logs |
| Throughput flat / no spike | request rate change **<2×** baseline **or** flat/declining vs prior day |
| Expensive query (compound) | top resource exec_rate **<10/min** **and** p95 **>30s** (30_000 ms) |
| Slowlog corroboration | `took_millis` >30_000 on matching resource (when slowlog ingested) |

When compound expensive-query criteria match, prefer **`query_governance`** over pure `infra_capacity`.
Cross-hypothesis: subtract **2** from `infra_capacity` when `query_governance` raw score ≥5.

## Hypothesis score normalization

Manual path — full formula with quality/source bonuses and penalties:
[evidence-quality.md](evidence-quality.md) §Hypothesis score algorithm.

```
base(h)           = sum(signal weights from manual-scoring.md)
adjusted(h)       = base + quality_bonus + source_bonus − counter_penalty − gap_penalty
normalized(h)     = adjusted(h) / sum(adjusted(all h))
display_score(h)  = clamp(round(normalized(h) × 100), 0, 100)
ruled_out         = { h : adjusted(h) < 0.5 × adjusted(primary) }
```
