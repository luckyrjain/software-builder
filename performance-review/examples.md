# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|--------------|----------|
| 1 | `reviewed_content`: a well-indexed, cached function with no complexity/N+1/memory/concurrency/pool/fanout issues | Inputs → Analyze (all 8 areas clean, no gaps) → Report → `PERFORMANCE_REVIEW_REPORT.md`, **Verdict: Pass** |
| 2 | `reviewed_content`: a function with a low-blast-radius cache invalidation gap only | Inputs → Analyze (1 finding, Cache) → Report → **Verdict: Pass with findings** |
| 3 | `reviewed_content`: a loop issuing one DB query per iteration over an unbounded, user-scaled collection | Inputs → Analyze (N+1 finding, high severity) → Report → **Verdict: Fail — regression risk** |
| 4 | `reviewed_content`: prose only ("the checkout service feels slow"), no actual code/query text | Inputs → Analyze (evidence gap on most of the 8 areas) → Report → **Verdict: Blocked — insufficient evidence** |
| 5 | `reviewed_content` absent | Inputs HARD STOP — ask for it, no Analyze |
| 6 | `reviewed_content` supplied, `profiling_excerpts` omitted, code has a concurrency-sensitive section | Analyze records Concurrency as an evidence gap (can't prove absence of races statically); other 7 areas fully evaluated clean → **Verdict: Pass with findings** (a gap alone still forces at least this, never a bare Pass) |
| 7 | "How many replicas do we need to handle 3x traffic growth?" | **Wrong skill** → capacity-planner directly (this skill reviews code/query/service content, not forward demand forecasting) |
| 8 | "Review this migration's index strategy" | **Wrong skill** → database-review directly (schema/index design is out of scope here) |
| 9 | "Review this whole MR" (broad code-quality ask, not performance-focused) | **Wrong skill** → pr-review directly |
| 10 | A `Fail — regression risk` finding traces to an unindexed high-cardinality query the service now depends on more heavily | Report includes the finding; Cross-skill escalation offered → **capacity-planner** (re-forecast) and **database-review** (root-cause the index) as follow-ups |

---

### Scenario: Clean review — happy path

**Caller:** `reviewed_content`: a paginated list endpoint with indexed queries, a correctly invalidated
cache, bounded memory use, no shared mutable state, and a connection pool sized for its measured
concurrency.

**Agent:**

1. Inputs — `reviewed_content` parsed; `profiling_excerpts` and `scope_hint` absent, defaults apply.
2. Analyze — all 8 focus areas evaluated; no findings, no evidence gaps.
3. Report — verdict derivation hits the bottom case (no findings, no gaps) → `Pass`.

**Expected fragment:**

```
# Performance review — list-endpoint handler

**Verdict: Pass**

## Algorithmic complexity

| Location | Complexity found | Finding |
|----------|-------------------|---------|
| `handlers.list_items` | O(n) single pass | None found |

## N+1

| Location | Pattern | Finding |
|----------|---------|---------|
| `handlers.list_items` | Single batched query, no per-item loop query | None found |

## Cache

| Location | Concern | Finding |
|----------|---------|---------|
| `cache.items_cache` | Invalidated on every write path, keyed on full filter set | None found |
```

---

### Scenario: N+1 query pattern — regression risk

**Caller:** `reviewed_content`: a function that fetches a list of orders, then loops over them issuing
one `get_customer(order.customer_id)` query per order.

**Agent:**

1. Inputs — `reviewed_content` parsed.
2. Analyze § 3 (N+1) — flags the per-order query loop; collection size scales with tenant order volume,
   assessed as a likely real regression under realistic load.
3. Report — a `Fail — regression risk`-level finding exists → **Verdict: Fail — regression risk**.

**Expected fragment:**

```
# Performance review — order-summary handler

**Verdict: Fail — regression risk**

## N+1

| Location | Pattern | Finding |
|----------|---------|---------|
| `handlers.order_summary` | Loop over `orders` issuing `get_customer()` per iteration | N+1: one query per order, unbounded with order volume — batch via `get_customers(ids)` instead |
```

---

### Scenario: Multiple minor findings, no regression

**Caller:** `reviewed_content`: a function with a minor O(n log n)→O(n²) risk only above an unrealistic
input size, plus a connection pool sized slightly below peak-but-rare concurrent load.

**Agent:**

1. Inputs — `reviewed_content` parsed.
2. Analyze — 2 findings recorded (Algorithmic complexity, Connection pools), both assessed low-severity
   — neither meets the `Fail — regression risk` bar.
3. Report — findings exist, none rises to `Fail — regression risk` → **Verdict: Pass with findings**.

**Expected fragment:**

```
# Performance review — batch-export job

**Verdict: Pass with findings**

## Algorithmic complexity

| Location | Complexity found | Finding |
|----------|-------------------|---------|
| `export.dedupe_rows` | O(n²) pairwise comparison | Low severity — input capped at 200 rows by upstream validation; would regress if that cap is ever removed |

## Connection pools

| Location | Concern | Finding |
|----------|---------|---------|
| `db.export_pool` | sizing | Pool sized for 5 concurrent, peak observed at 6 — rare, low blast radius; consider raising by 1-2 |
```

---

### Scenario: Degraded path — sparse input, evidence gap

**Caller:** `reviewed_content`: "the checkout service feels slow under load" — no actual code, query,
or config text supplied.

**Agent:**

1. Inputs — `reviewed_content` parsed as present (non-empty), so no HARD STOP; noted as prose-only.
2. Analyze — Algorithmic complexity, DB behavior, N+1, Cache, Memory, Connection pools, and Downstream
   fanout all recorded as evidence gaps (no code/query text to evaluate); Concurrency also gapped.
3. Report — a majority of areas hit an evidence gap → **Verdict: Blocked — insufficient evidence**, not
   a fabricated per-area finding and not a silently-assumed `Pass`.

**Expected fragment:**

```
# Performance review — checkout service (description only)

**Verdict: Blocked — insufficient evidence**

## Algorithmic complexity

| Location | Complexity found | Finding |
|----------|-------------------|---------|
| — | — | Evidence gap — no code/query text supplied, only a prose description |

## Evidence gaps

- Algorithmic complexity: no code/query text supplied.
- DB behavior: no code/query text supplied.
- N+1: no code/query text supplied.
- Cache: no code/query text supplied.
- Memory: no code/query text supplied.
- Concurrency: no code/query text supplied.
- Connection pools: no code/query text supplied.
- Downstream fanout: no code/query text supplied.
```

---

### Scenario: Cross-skill handoff — findings suggest a capacity re-forecast

**Caller:** `reviewed_content`: a payment-webhook handler; Analyze finds a real N+1 pattern plus a
connection pool that would exhaust under 2x current peak load.

**Agent:**

1. Inputs → Analyze — N+1 finding (Fail-level) and a connection-pool exhaustion-risk finding, both
   recorded.
2. Report — **Verdict: Fail — regression risk**.
3. Per [SKILL.md § Cross-skill escalation](SKILL.md#cross-skill-escalation), since the connection-pool
   finding implies current capacity assumptions may no longer hold once the N+1 fix changes call
   volume, the agent offers a follow-up: *"This review found a connection-pool exhaustion risk under
   projected load — want capacity-planner to re-forecast replica/pool sizing for `payments-webhook`
   once the N+1 fix lands?"*

**Expected fragment:**

```
## Connection pools

| Location | Concern | Finding |
|----------|---------|---------|
| `db.webhook_pool` | exhaustion risk | Sized for current traffic; would exhaust at ~2x peak — re-forecast with capacity-planner once the N+1 fix changes call volume |
```

Caller accepts → handed to **capacity-planner** with the current traffic baseline and this finding as
context.
