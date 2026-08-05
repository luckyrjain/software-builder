# Evidence quality and hierarchy

Load in **Phase 4** (ranking) and **Phase 5** (report rendering). Normative for the **Evidence matrix**,
**Ranked hypotheses**, and **confidence caps** in [report-template.md](../report-template.md).

## Evidence hierarchy (conflict resolution)

When signals disagree, prefer the higher tier. Lower tiers support but do not override higher tiers.

```text
Distributed traces (APM span, trace)
↓
Application logs (structured errors, slowlog)
↓
Metrics (rates, saturation, lag)
↓
Deployment / change events
↓
Infrastructure metrics (K8s, node-level)
↓
Code diff
↓
Tickets / human narrative
↓
Hypothesis (unverified inference)
```

**Rule:** If logs and metrics disagree on timing or magnitude, **logs win** for attribution; metrics win
for fleet-wide saturation when logs are sparse. Document the conflict in **Gaps** and apply confidence caps
below.

## Evidence quality (matrix and timeline column)

Tag each row with exactly one **Evidence quality** label:

| Evidence quality | Meaning | Example |
|------------------|---------|---------|
| **Observed** | Directly measured or logged in the incident window | 500s started at 12:01; CPU 99% on node-3 |
| **Correlated** | Time-aligned with the incident but causality not proven | Deploy at 11:59 before errors at 12:01 |
| **Inferred** | Derived from observed facts + domain knowledge | GC pauses inferred from heap metrics + latency |
| **Assumed** | No direct evidence; stated explicitly as assumption | Thread starvation assumed without thread dump |

Record **freshness** for Observed/Correlated rows when investigation ended long after the incident —
see [evidence-coverage.md](evidence-coverage.md) §Evidence freshness.

**Rules:**

- Do not label **Assumed** signals as supporting **HIGH** confidence.
- **Correlated** deploy + error spike requires diff-on-path evidence before upgrading to **Observed** cause.
- Prefer **Observed** > **Correlated** > **Inferred** > **Assumed** when ranking hypotheses.

## Hypothesis score algorithm (0–100)

**CLI output is canonical when present.** When ranking manually, compute scores with this formula so runs
are reproducible. Document in **Gaps** when manual path used.

### Step 1 — Base points

Sum matched signal weights from [manual-scoring.md](manual-scoring.md) for hypothesis `h`:

```text
base(h) = sum(signal weights matched for h)
```

Apply cross-hypothesis penalties from manual-scoring **before** bonuses.

### Step 2 — Adjustments

```text
quality_bonus(h)  = min(15, sum per supporting signal: +5 Observed, +2 Correlated, 0 Inferred, −5 Assumed)
source_bonus(h)   = +10 if ≥2 independent signal types support h (deploy + error, trace + log, etc.)
counter_penalty(h)= −10 × count(unresolved contradicting signals for h)
gap_penalty(h)    = −15 if critical evidence missing for h:
                      • deploy_regression: no diff on failing path
                      • query_governance: saturation but no query investigation attempts
                      • any primary: trigger required but Unknown after investigation
```

```text
adjusted(h) = base(h) + quality_bonus(h) + source_bonus(h) − counter_penalty(h) − gap_penalty(h)
adjusted(h) = max(0, adjusted(h))
```

### Step 3 — Normalize and display

```text
normalized(h)   = adjusted(h) / sum(adjusted(all h))     # if sum > 0; else 0
display_score(h)= clamp(round(normalized(h) × 100), 0, 100)
primary         = argmax(adjusted)
ruled_out       = { h : adjusted(h) < 0.5 × adjusted(primary) }
```

Show **integer** `display_score` in **Ranked hypotheses** only. Apply **confidence caps** (below) after
computing scores — caps may lower the band below what score alone suggests.

| Score range | Typical band (if caps allow) |
|-------------|------------------------------|
| 75–100 | HIGH |
| 50–74 | MEDIUM |
| 25–49 | LOW |
| 0–24 | UNKNOWN / ruled out |

## Confidence caps (apply after scoring)

Caps limit the **confidence band**; they do not change display scores.

| Condition | Maximum band |
|-----------|--------------|
| Single observability source responded | **MEDIUM** |
| Unresolved contradictory evidence | **MEDIUM** |
| Missing trigger after required investigation | **LOW** for trigger attribution |
| Trigger **Unknown** | Root cause may be **Unknown**; never **HIGH** for full causal chain |
| Any supporting signal **Assumed** only | **LOW** |
| Phase 4 incomplete / partial report | **MEDIUM** |
| KubeSense mandatory skip (`mcp_process_failure`) + trigger Unknown | **MEDIUM** |

**Unknown root cause permitted** when trigger Unknown and evidence insufficient — state explicitly in
Conclusion; do not force HIGH to satisfy stakeholders.

## Supporting and contradicting evidence (required per hypothesis)

Every ranked hypothesis (H1, H2, H3…) MUST include in the report:

| Field | Required |
|-------|----------|
| **Supporting evidence** | ≥1 bullet with source + link |
| **Contradicting evidence** | ≥1 bullet **or** explicit *"None found after [checks]"* |
| **Confidence band** | HIGH / MEDIUM / LOW / UNKNOWN (after caps) |
| **Remaining uncertainty** | ≥1 bullet **or** *"None"* |

Contradicting signals that remain **unresolved** → **STOP** ranking until explained in Gaps; apply **MEDIUM** cap.

## Causal graph rules

- Graph must be **acyclic** (DAG) — no `A ↓ B ↓ A` loops in the vertical chain
- **Feedback loops** (e.g. latency → retries → more latency): identify the **initiating event** first;
  describe the loop in prose **after** the acyclic graph, not as circular `↓` steps
- Customer-visible symptoms at the **bottom** of the graph

## Hypothesis deduplication (Phase 4)

Before final ranking, **merge materially identical hypotheses** — do not split one causal chain into
competing hypotheses.

| Keep separate | Merge into one chain |
|---------------|----------------------|
| Deploy regression **vs** infra capacity (independent explanations) | Slow query → DB saturation → app errors (same chain) |
| External third-party **vs** deploy regression | OpenSearch saturation **vs** slow queries (layers of one chain) |
| Kafka lag **vs** deploy on unrelated service | H1/H2/H3 all describing search overload |

When merging: use **Causal graph** for chain steps; keep one primary hypothesis type for the **root**
layer; note merged IDs in **Gaps**: *"Merged query_governance + infra_capacity steps into single causal graph."*

## Multi-cause incidents

**Independent causal chains may both rank HIGH** when each has ≥2 independent signal types **and** the
pair has no documented cross-hypothesis penalty relationship ([manual-scoring.md](manual-scoring.md)
§Cross-hypothesis penalty). Do **not** force a single root cause when evidence supports multiple
contributors — but a pair explicitly penalized against each other (e.g. `query_governance` +
`infra_capacity`, where a high `query_governance` score subtracts from `infra_capacity`'s raw score)
will rarely both clear HIGH after penalty; report the penalized pair as primary + co-cause (see below),
not dual-HIGH.

- Existing 20% raw-score rule: top-2 within 20% → `"causality": "multi-cause"` ([evidence-schema.md](evidence-schema.md))
- `query_governance` + `infra_capacity` under saturation: co-report both when query workload exhausted headroom
  — typically primary (HIGH) + co-cause (MEDIUM) after the cross-hypothesis penalty, per the worked example
  in [manual-scoring.md](manual-scoring.md) §Worked example — query_governance + infra_capacity multi-cause
- Customer-visible symptom (5xx, timeout) belongs at the **bottom** of the causal graph, not as a competing hypothesis

## Evidence matrix (required on complete RCAs)

Map every material signal to the hypothesis it supports. Hypothesis IDs: **H1** = primary, **H2**, **H3** = alternates.

| Signal | Source | Time (UTC) | Supports | Evidence quality | Confidence | Freshness | Link |
|--------|--------|------------|----------|------------------|------------|-----------|------|
| 500s on transfer-money | Datadog | 12:01 | H1 | Observed | HIGH | Fresh | … |
| Production deploy MR !482 | GitLab | 11:59 | H1 | Correlated | HIGH | … |
| CPU p95 94% | Datadog | 12:03 | H2 | Observed | MEDIUM | … |

One row per distinct finding — no duplicates.

## Incident class (Phase 4 → Incident scope)

Set from primary hypothesis; use **Unknown** when inconclusive. Label field **Incident class** in report.

| Primary hypothesis | Incident class |
|--------------------|----------------|
| `deploy_regression`, `feature_flag_regression` | Deploy |
| `infra_capacity`, `kafka_lag_spike` | Capacity |
| `dependency_failure` | Dependency |
| `configuration_change` | Configuration |
| `deploy_regression` / code defect path | Software defect |
| `query_governance` (code path) | Software defect |
| `query_governance` (data/query) | Data quality |
| `external_third_party` | Third-party |
| Security-related evidence (auth bypass, CVE) | Security |
| `slo_breach` with network symptoms | Network |
| `inconclusive` | Unknown |

Coverage dashboard: [evidence-coverage.md](evidence-coverage.md).

## Insufficient evidence (explicit Unknown)

When **no hypothesis exceeds MEDIUM** after confidence caps, the **Conclusion** MUST state *No defensible
root cause* — **do NOT select the highest-ranked hypothesis as primary** merely because it scored highest.
List ranked alternates as inconclusive with scores.

When no hypothesis reaches MEDIUM after guardrails, the **Conclusion** MUST state:

```text
No defensible root cause identified. Evidence insufficient for a causal claim.
Additional telemetry required: [list specific gaps].
```

Do not force a primary hypothesis when confidence is **UNKNOWN** — use `inconclusive` and list ranked
alternates with scores if Phase 4 completed.
