# Recommendation Decision Framework

Extracted from `thresholds.md` for maintainability. Covers decision confidence, recommendation
ordering, lifecycle, impact dimensions, rollback triggers, risk scoring, and verdict labels.

> **Note:** R0/R1/R2 in [cost-estimation.md](cost-estimation.md) are **recommendation priority tiers** — do not confuse with the pipeline phase priorities P0–P3 in SKILL.md/orchestrator.md.

## Decision Confidence (numeric 0–1)

**Relationship to confidence-formula.md:** the canonical `RECOMMENDATION_CONFIDENCE` arithmetic is the
weighted sum in [reference/confidence-formula.md](reference/confidence-formula.md) — that formula is
what gets computed, stored, and validated (INV-11). This section is **not** a second, competing
0–1 score. Its job is narrower: the deduction sizes and the keep-vs-cut 0.33× multiplier below describe
how missing evidence should lower the `support_quality` and `support_completeness` **inputs** that feed
the weighted sum, and the caps in confidence-formula.md (`BLOCKED` → 0.3, telemetry ★≤3 → no rec >0.7,
missing critical `OBS_*` → floor 0.3) are applied after that sum, not after the deduction-from-1.0
walkthrough below. Treat the deduction table and "Example scores" as **illustrative calibration**, not
an alternate arithmetic path — do not compute both and pick one.

Confidence in each **recommendation**, not raw telemetry quality. Assign per recommendation. Start at **1.0** and subtract for missing evidence:

| Missing evidence | Score impact |
|------------------|-------------|
| p95/p99 unavailable (dist + gauge fallback) | −0.10 to −0.15 |
| Consumer lag unvalidated per group | −0.10 per missing group (replica-cut score floors at **0.30** after lag deductions only) |
| Partition distribution unknown | −0.15 (applied after lag floor; can take replica-cut score below 0.30) |
| SLO baseline unknown | −0.10 |
| Manifest drift | cap optimization recs at **0.50** |
| Metric scope ambiguous (pod vs container) | −0.20 |
| Stability blocker (throttle/OOM/restarts) | cap affected dimension at **0.30** |
| Active firing monitor (required severity) | cap affected dimension at **0.30** |

**Keep vs reduce deduction rule:** deductions apply **fully** to active change recommendations (reduce
requests, cut replicas, change HPA). For conservative **"keep"** recommendations, apply deductions at
a **fixed 0.33× multiplier** (one-third weight) — the risk of wrongly keeping is lower than the risk
of wrongly cutting.

Example: p95 unavailable is −0.15 for "Reduce CPU requests" but −0.05 (0.15 × 0.33) for "Keep CPU
requests", because keeping conservative headroom is the safer default when evidence is incomplete. This
is why "Keep CPU requests" illustratively scores 1.00 − 0.05 = **0.95** while a matching "Reduce CPU
requests" for the same missing evidence scores 1.00 − 0.15 = **0.85**.

**Quick rubric (bands):** start here, then apply the deductions above for precision.

| Score | When |
|-------|------|
| **≥ 0.90** | All signals present, no blockers, Kafka lag validated across all groups |
| **~0.70** | Exactly one minor unknown (e.g. PDB unverified, CA activity unknown) |
| **~0.50** | A key signal missing (fleet p95 unavailable, or lag missing for one group) |
| **< 0.30** | Multiple unknowns, or an active blocker (firing monitor / stability) — **advisory only** |

**Example scores:**

| Recommendation | Decision confidence | Missing evidence |
|----------------|--------------------:|------------------|
| Keep CPU requests | 0.95 | p95 CPU unavailable (−0.15 × 0.33 = −0.05) |
| Keep memory requests | 0.99 | None |
| Reduce replicas | 0.15 | 7/8 consumer groups lack lag (−0.70 → floor 0.30); partition distribution unknown (−0.15) |
| HPA metric evaluation (Phase 2) | 0.50 | Phase 1 observation incomplete |

Scores **< 0.50** → observe-first ordering; **≥ 0.80** → actionable with monitoring.

## Ordering rule

Sort all recommendations (excluding `REJECTED`) by **action tier** first — **concrete work before holds**; **observability before sizing** when both are present:

| Tier | Rec patterns | Role |
|------|--------------|------|
| **1 — Observability** | `REC_KAFKA_LAG_INSTRUMENT`, `REC_PARTITION_VALIDATE`, `REC_SLO_BASELINE`, `REC_HPA_OBSERVE`, `REC_MANIFEST_RECONCILE`, `REC_CPU_DIST_QUERY`, `REC_RESTART_INVESTIGATE`, `REC_*_OBSERVE` | Instrument, validate, observe — highest-leverage concrete work |
| **2 — Actionable change** | `READY` / `COMPLETED` on `REC_*_INCREASE`, `REC_*_REDUCE`, `REC_HPA_ADJUST`, `REC_HPA_EVALUATE`, `REC_SIDECAR_ACCOUNT`; `DEFERRED` change recs that are not Tier 1 or Tier 3 | Resource or HPA changes ready (or waiting on evidence) |
| **3 — Hold** | `REC_*_KEEP`, `REC_REPLICA_KEEP`; `BLOCKED` + keep/observe intent | **Decision: Keep** — no change recommended |

Within each tier, tie-break:

1. Graph `priority` field when set (`P0` → `P1` → `P2`)
2. **Decision confidence** — descending
3. **Expected benefit** — descending
4. **Engineering effort** — ascending

Derive human `{priority}` labels from final sort position: Tier 1 → `P0`; Tier 2 → `P1`; Tier 3 → `P2` (use `P3` only when multiple holds need distinct ordering).

**Golden order (bursty Kafka + memory headroom):** Instrument Kafka lag → Raise memory → Keep CPU → Keep replicas.

Render spec: [render/markdown.md](render/markdown.md#recommendationssummary-sort-order).

## Lifecycle status (graph enum)

| Status | Meaning |
|--------|---------|
| **READY** | Prerequisites met; safe to execute |
| **BLOCKED** | Hard stop |
| **DEFERRED** | Waiting on evidence or observation period |
| **REJECTED** | Analysis concluded action is wrong |
| **COMPLETED** | Done (repeat assessments) |

Finite state machine — no `Observe` / `Ready` variants. Validator and graph YAML use these values only.

## Appendix State labels (render mapping)

Technical Appendix LifecycleSummary and per-rec **State** use human-oriented labels — not raw graph enum:

| Graph `status` | Rec pattern | Appendix State |
|----------------|-------------|----------------|
| `BLOCKED` | `REC_*_KEEP`, `REC_*_OBSERVE` | **KEEP** |
| `BLOCKED` | change rec gated by STOP_REASON | **BLOCKED** |
| `READY` / `COMPLETED` | actionable change | **CHANGE** |
| `DEFERRED` | | **DEFER** |
| `REJECTED` | | **NOT RECOMMENDED** |

Mapping spec: [render/markdown.md](render/markdown.md#appendix-recommendation-status).

## Impact dimensions

Per recommendation, rate each dimension:

| Dimension | Values |
|-----------|--------|
| **Cost** | None \| Low \| Medium \| High |
| **Latency** | None \| Low \| Medium \| High |
| **Risk** | Low \| Medium \| High |
| **Availability** | None \| Low \| Medium \| High |
| **Engineering effort** | e.g. `1 hour`, `1 day`, `1 week` |

Each recommendation must include:

| Field | Purpose |
|-------|---------|
| **Status** | Appendix: `KEEP` \| `DEFER` \| `CHANGE` \| `NOT RECOMMENDED` \| `BLOCKED` (gated change only). Graph: raw enum. |
| **Priority** | `P0` / `P1` / `P2` — derived from ordering rule |
| **Supports** | Evidence IDs (E*) |
| **Decision confidence** | 0–1 score |
| **Impact** | Cost, latency, risk, availability, engineering effort |
| **Before executing** | Prerequisite checklist (✓/✗) — distinct from blockers |
| **Blockers** | Evidence IDs or STOP_REASONs preventing Ready status |
| **Missing evidence** | E* still needed |
| **Potential benefit** | Capacity or cost |
| **Rollback trigger** | Metric that causes revert |

## Human phrasing (rendered report)

Graph and appendix keep IDs and numeric confidence. The **Human Report** translates to prose ([workflow/report.md](workflow/report.md)):

| Graph field | Human Report |
|-------------|--------------|
| `REC_CPU_KEEP` + BLOCKED | **P2 — Keep CPU requests** · Decision: Keep · Decision confidence: Very High (0.9) |
| `REC_CPU_REDUCE` + REJECTED | **Changes evaluated but not recommended** — Not recommended · Decision confidence: Very Low (0.3) |
| `OBS_DERIVED_CPU_UTIL_P95` = 152% | *Fleet p95 reaches 152% of request* |
| `recommendation_confidence` 0.9 | *Decision confidence: Very High (0.9)* — separate from Decision line; no formula |
| `STOP_REASON` `missing_kafka_lag` | *Consumer lag not validated for all groups* |

Lead with **changes, then holds** in the `## Recommendation` lead block ([human-report.md](templates/human-report.md#lead-with-changes-then-holds)): *"Increase memory requests to approximately 1.5–1.75 GiB. Keep CPU requests and replica count unchanged until Kafka lag telemetry is available."* Per-recommendation bullets may lead with **why**: *"Keep CPU requests unchanged because fleet p95 reaches 152% of request and throttle stays below 5%."*

**Priority vs decision confidence — keep them separate.** *Priority* is the order to act/observe in;
*decision confidence* is how sure you are the recommendation is correct. An P0 instrument-lag task can
have low confidence (0.40) yet still come first because everything else depends on it.

| Priority | Meaning |
|----------|---------|
| **P0** | Tier 1 — observability / instrumentation (instrument lag, partition validation, observe phases) |
| **P1** | Tier 2 — primary actionable resource change (raise/trim CPU or memory, HPA adjust when READY) |
| **P2** | Tier 3 — holds (`REC_*_KEEP`, replica keep); use **P3** only to distinguish multiple holds |

## Rollback trigger format (required on every READY change rec)

Every actionable cut/scale recommendation must include a **structured rollback trigger** — not freeform prose.

```text
ROLLBACK_IF <metric_or_signal> <comparator> <threshold> FOR <duration>
REVERT_TO <prior_value_or_action>
```

| Field | Valid values | Example |
|-------|--------------|---------|
| `<metric_or_signal>` | Named OBS/metric: `OBS_CPU_THROTTLE_RATE`, `OBS_KAFKA_LAG_MAX`, `p99_latency`, `error_rate`, `payment_success_rate` | `OBS_CPU_THROTTLE_RATE` |
| `<comparator>` | `>`, `>=`, `<`, `<=`, `delta_pct_above` | `>` |
| `<threshold>` | Numeric with unit (% , ms, messages, cores) | `5%` |
| `<duration>` | `1m`, `5m`, `15m`, `1h` sustained | `5m` |
| `<prior_value_or_action>` | Previous request/replica count or *restore prior manifest* | *restore 500m CPU request* |

**Valid examples:**

- `ROLLBACK_IF OBS_CPU_THROTTLE_RATE > 5% FOR 5m REVERT_TO restore prior CPU request`
- `ROLLBACK_IF OBS_KAFKA_LAG_MAX delta_pct_above 50% FOR 15m REVERT_TO restore prior replica count`
- `ROLLBACK_IF p99_latency >= baseline×1.2 FOR 10m REVERT_TO restore prior manifest`

**Invalid (do not emit):** *"monitor closely"*, *"rollback if things look bad"*, triggers without duration or threshold.

**HPA changes:** Phase 1 (observe lag, queue depth, oldest message age ≥2 weeks) before Phase 2 (evaluate correlation). Do not recommend metric switch until Phase 1 complete.

**Fixed HPA risk:** min=max may be intentional (warm JVMs, latency/payment SLAs, failover) — flag Medium risk; ask before cutting replicas.

## Risk scoring (Likelihood × Impact)

Per recommendation, rate:

| Field | Values |
|-------|--------|
| **Likelihood** | Low \| Medium \| High |
| **Impact** | Low \| Medium \| High \| Critical |
| **Risk score** | Low \| Medium \| High \| Critical (from L×I matrix) |
| **Residual risk** | After mitigation (staged rollout, rollback triggers) |

Example — `REPLICA_REDUCE`: Likelihood Medium · Impact Critical · Score High · Residual Medium.

## Confidence display (v2.0)

Weighted sum per [reference/confidence-formula.md](reference/confidence-formula.md). Default appendix shows band + factor list only — **no `0.35 ×` arithmetic** in rendered output ([workflow/report.md](workflow/report.md)). Human Report shows emoji decision block + band + one-line reason.
`ASSESSMENT_CONFIDENCE` ≠ `RECOMMENDATION_CONFIDENCE`. Round to 1 decimal + band in appendix.

## Verdict labels

Dimension-level labels below. The **Human Report** uses **Recommendation** for the overall lead (see [workflow/report.md](workflow/report.md)); these verdicts apply per-dimension analysis and appendix.

| Verdict | When |
|---------|------|
| **Conservatively right-sized** | Avg suggests waste but bursts, incomplete telemetry, or stability blockers prevent reductions |
| **Overprovisioned** | Clear trim opportunity with p95 support and no blockers |
| **Right-sized** | Utilization in target bands |
| **Mixed** | Some dimensions wasteful, others tight |
| **Mixed / cyclic** | Avg suggests waste but strong cyclic pattern means peak-period capacity is genuinely needed — size on peak window, not weekly avg |
| **Mixed / defer** | **CPU-dimension label** (see CPU request utilization table): avg low but fleet p95 unavailable, so sizing evidence is incomplete — keep requests conservatively, do not cite a p95 formula |
| **Underprovisioned** | Throttle, OOM, or sustained high utilization |

**Dimension vs overall mapping:** `Mixed / defer` is a **per-dimension** (usually CPU) verdict, not an
overall one. When a dimension is `Mixed / defer` and a reduction is blocked, the **overall** verdict is
**Conservatively right-sized** (CPU = Mixed / defer → overall = Conservatively right-sized when blocked).
