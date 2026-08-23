# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|--------------|----------|
| 1 | `demand_data` (clean 12-month trend), `forecast_horizon: 6 months`, `current_baseline` (4 replicas, 2 cores each, 100 DB connections) | Inputs → Analyze → Report → all sections computed, projections well within known ceilings → `CAPACITY_PLAN.md` with Headroom: `Sufficient` |
| 2 | Same, but projected peak RPS exceeds current replica ceiling within the horizon | Headroom: `Insufficient` (proven shortfall) |
| 3 | Same, but projected DB connections land within 10% of the known connection limit | Headroom: `Marginal` (thin headroom, no known ceiling exceeded) |
| 4 | `demand_data` with no derivable trend and no `growth_rate` supplied | Headroom: `Unknown — insufficient historical data` |
| 5 | `demand_data` and `forecast_horizon` both missing | Inputs HARD STOP — ask, no Analyze |
| 6 | `demand_data` supplied but no historical queue data | Queue section marked `Unknown` in Notes, excluded from that dimension's Insufficient/Marginal check, does not upgrade overall verdict to `Sufficient` |
| 7 | No `current_baseline` supplied at all | Forecast sections still compute; sections needing a known ceiling record the missing baseline as a gap, not a fabricated ceiling |
| 8 | "Is `payments-service` currently overprovisioned?" (asking about live/current resource usage, not a forward-looking forecast) | **Wrong skill** → k8s-overprovisioning-datadog directly |
| 9 | "Review this service for N+1 queries and cache invalidation issues" | **Wrong skill** → performance-review directly |
| 10 | A clean `Sufficient` plan is produced and the caller asks whether it holds against live metrics | Cross-skill escalation → k8s-overprovisioning-datadog |
| 11 | An `Insufficient` plan is produced and the caller wants it turned into a scaling/cost sprint | Cross-skill escalation → cost-optimization-sprint-planner |

---

### Scenario: Clean happy-path forecast

**Caller:** `demand_data`: 12 months of average RPS (rising from 800 to 1,400, ~4%/month), peak:average
ratio steady at 2.3:1; `forecast_horizon: 6 months`; `current_baseline`: 6 replicas at 2 cores/4GB each,
DB connection limit 200, 90 active DB connections, 50ms average request latency, 500GB storage capacity.

**Agent:**

1. Inputs — `demand_data`, `forecast_horizon`, `current_baseline` all present; `growth_rate` derived
   from the trend (~4%/month), `peak_avg_ratio` derived from the data (2.3:1)
2. Analyze — projects average RPS to ~1,770 at horizon end, peak RPS ~4,070; concurrency derived from
   peak RPS × the stated 50ms average request latency (current: 3,220 peak RPS × 0.05s ≈ 161; projected:
   4,070 × 0.05s ≈ 204); CPU/memory scaled linearly from baseline; DB connections projected from
   concurrency × a connections-per-concurrent-request ratio derived from `current_baseline` (90 current
   connections ÷ 161 current concurrency ≈ 0.56), giving ~114 projected connections (well under the 200
   limit); storage growth projected from the data-volume trend to ~340GB (under 500GB capacity); replica
   requirement projected to 10 — bare-minimum 8.14 (4,070 ÷ 500), the stated 20% headroom margin applied
   on top (8.14 × 1.2 = 9.768), rounded up once to 10 — (under no known ceiling, since `current_baseline`
   states current count, not a hard cap) — no evidence gaps recorded
3. Report — no section exceeds or sits near a known ceiling, no gaps → Headroom `Sufficient`

**Expected fragment:**

```
# Capacity plan — payments-api, 6 months

**Headroom: Sufficient**

## Replica requirements

| Component | Current replicas | Projected replicas | Basis |
|-----------|-------------------|----------------------|-------|
| `payments-api` | 6 | 10 | Projected peak RPS (4,070) ÷ per-replica capacity (500 RPS), 20% headroom margin applied |

## Database

| Metric | Current | Projected | Basis |
|--------|---------|-----------|-------|
| Connections | 90 | 114 | Concurrency (204) × connections-per-concurrent-request ratio (0.56, derived from current_baseline: 90 ÷ 161 current concurrency) |
```

---

### Scenario: Proven shortfall — Insufficient

**Caller:** Same demand series, but `current_baseline` states a hard replica ceiling of 8 (infrastructure
budget cap for the quarter).

**Agent:** Analyze projects 10 replicas needed at horizon end against a stated ceiling of 8 — a proven
shortfall. Report derives Headroom `Insufficient` (precedence winner over any other section's state).

**Expected fragment:**

```
**Headroom: Insufficient**

> Insufficient — projected replica requirement (10) exceeds the stated replica ceiling (8) within the
> 6-month horizon.

## Replica requirements

| Component | Current replicas | Projected replicas | Basis |
|-----------|-------------------|----------------------|-------|
| `payments-api` | 6 | 10 (ceiling: 8) | Projected peak RPS (4,070) ÷ per-replica capacity (500 RPS), 20% headroom margin applied |
```

---

### Scenario: Thin headroom — Marginal

**Caller:** Same demand series as the clean happy-path scenario, but `current_baseline` states a DB
connection limit of 125 (no stated replica ceiling).

**Agent:**

1. Inputs — `demand_data`, `forecast_horizon`, `current_baseline` all present; `growth_rate` and
   `peak_avg_ratio` derived from the trend as in the happy-path scenario
2. Analyze — same projections as the happy-path scenario (replica requirement 10, projected DB
   connections ~114); 114 projected connections against a stated limit of 125 is 91% utilization — within
   10% of the known ceiling, though it does not exceed it; no other section proves or nears a shortfall
3. Report — no section exceeds a known ceiling, but the DB dimension sits within 10% of its stated limit
   → Headroom `Marginal` (thin headroom, no known ceiling exceeded)

**Expected fragment:**

```
**Headroom: Marginal**

> Marginal — projected DB connections (114) sit within 10% of the stated connection limit (125); no
> known ceiling is exceeded, but headroom is thin.

## Database

| Metric | Current | Projected | Basis |
|--------|---------|-----------|-------|
| Connections | 90 | 114 (limit: 125) | Concurrency (204) × connections-per-concurrent-request ratio (0.56, derived from current_baseline: 90 ÷ 161 current concurrency) |
```

---

### Scenario: Evidence gap — Unknown

**Caller:** `demand_data`: only 6 weeks of usage numbers with no clear upward or downward pattern
(high week-to-week noise), no `growth_rate` supplied; `forecast_horizon: 12 months`.

**Agent:**

1. Inputs — `demand_data` and `forecast_horizon` present, but no clean trend is derivable and no
   `growth_rate` was supplied
2. Analyze — records this as an evidence gap in `evidence_gaps`; RPS/concurrency, CPU, memory, DB, and
   replica sections cannot produce a confident projection and are marked `Unknown` rather than guessed
3. Report — no section proves a shortfall, but the evidence gap is real and unresolved → Headroom
   `Unknown — insufficient historical data`

**Expected fragment:**

```
**Headroom: Unknown — insufficient historical data**

> Unknown — insufficient historical data: only 6 weeks of noisy demand_data with no derivable trend, and
> no growth_rate supplied.

## RPS & concurrency

| Metric | Current | Projected (end of horizon) | Basis |
|--------|---------|------------------------------|-------|
| Average RPS | 950 (noisy) | Unknown | No derivable trend in demand_data, no growth_rate supplied |
```

This is the degraded-path scenario: the required check (a growth-based projection) cannot be completed
for lack of usable historical data, and the gap is recorded as an explicit `Unknown`, never silently
folded into `Sufficient` or dropped from the report.

---

### Scenario: Cross-skill handoff to k8s-overprovisioning-datadog

**Caller:** After receiving a `Sufficient` `CAPACITY_PLAN.md` for `payments-api`, "does this hold up
against what's actually deployed right now?"

**Agent:** This forecast projects forward from historical demand; it does not verify what's currently
running matches `current_baseline` or is itself rightsized. Per
[SKILL.md § Cross-skill escalation](SKILL.md#cross-skill-escalation), routes to
**k8s-overprovisioning-datadog** directly, handing it `payments-api` as the service to check against live
metrics — the forecast's projected targets (10 replicas at horizon end) are offered as context, not
re-derived by the other skill.
