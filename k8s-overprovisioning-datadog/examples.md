# Examples — v3.0 graph-first

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md)

Every assessment starts **DISCOVER_SOURCES → RESOLVE → COLLECT** before graph construction. Scenario
steps may begin at COLLECT when source discovery and service resolution are not the behavior under test.
Build graph → validate invariants → render. Schema: [decision-graph-schema.md](reference/decision-graph-schema.md).
Examples: [decision-graph.example.yaml](reference/decision-graph.example.yaml) (KEEP),
[decision-graph.trim.example.yaml](reference/decision-graph.trim.example.yaml) (TRIM_RESOURCES),
[decision-graph.scale-up.example.yaml](reference/decision-graph.scale-up.example.yaml) (SCALE_UP).

## Invocation table

| # | User says | Resolves to | Notes |
|---|-----------|-------------|-------|
| 1 | "Is `payment-consumer` overprovisioned in prod?" | DISCOVER_SOURCES→RENDER full path | Happy path; 7d window default |
| 2 | "Right-size `api-gateway` deployment" | DISCOVER_SOURCES→RENDER; may emit TRIM_RESOURCES | Stateless HTTP trim candidate |
| 3 | "Namespace waste ranking for `payments`" | orchestrator namespace_ranking intent | Skips per-svc memory deep-dive |
| 4 | "Replicas too high on `kafka-consumer`?" | replica-analysis + workload path | Kafka lag gates replica cuts |
| 5 | "Assess checkout-api prod — RCA found OOM" | DISCOVER_SOURCES→COLLECT with handoff window | Cross-skill from incident-rca |
| 6 | "`checkout-worker` CPU throttling — need more headroom?" | SCALE_UP path | throttle_high stop reason |
| 7 | "Rightsize `unknown-svc`" (ambiguous tag) | resolve-service disambiguation | Service not found / multiple matches |
| 8 | "RCA for checkout-api outage" | **Wrong skill** → incident-rca | Not a sizing request |
| 9 | "Rightsize payment-consumer — open canvas for namespace ranking" | DISCOVER_SOURCES→RENDER full DORA → offer canvas for REC/cost table after report | [post-action-templates §6](../docs/skill-framework/shared/post-action-templates.md#6-canvas-hints) |

## Pre-flight announcement (first output)

**User:** "Is payment-consumer overprovisioned in prod?"

**Agent (DISCOVER_SOURCES start):**

```
**k8s source profile:** Kubernetes MCP ✅ live / ❌ history | Datadog ✅ history | Git provider ✅ manifests

**Scope:** deployment `payment-consumer` · env `production` · window `7d` utilization (cost `30d` if gated)
```

---

### Scenario: Overprovisioned verdict blocked (bursty Kafka)

**User:** "Is payment-consumer overprovisioned?"

**Agent:**
1. COLLECT — fleet p95, throttle, Kafka lag, HPA bounds
2. REASON — `DEC_CPU_REQUEST` BLOCKED (fleet p95 above trim threshold)
3. BUILD_GRAPH → VALIDATE_INVARIANTS → RENDER

**Expected fragments:**

```
🟢 Recommendation

Keep the current configuration.

No CPU, memory, or replica changes are recommended.

Severity: Warning — bursty utilization warrants monitoring, not trimming.
Assessment confidence: Very High (0.9)

Basis:
• Evidence completeness — fleet p95, throttle, and replica count present
• Evidence quality — measured utilization, not inferred
• Telemetry coverage — ★3 Datadog profile
• Contradiction resolution — avg vs p95 resolved in favor of p95

Review again in: 14 days
```

```
## Recommendations

**P0 — Instrument missing consumer lag**
Decision: Defer
Decision confidence: Low (0.4)
Lag coverage is 1/8 groups. Complete instrumentation before any replica change.

**P1 — Raise memory requests**
Decision: Ready
Decision confidence: High (0.85)
Worst-pod peak reaches 1.34 GiB against a 1 GiB request; raise request to ~1.5–1.75 GiB.

Where to apply: `helm/payment-consumer/values.yaml` — memory requests under `resources.requests`

**P2 — Keep CPU requests**
Decision: Keep
Decision confidence: Very High (0.9)
Fleet p95 reaches 152% of request; throttle rate is low but bursts justify current headroom.

**P2 — Keep replica count**
Decision: Keep
Decision confidence: Very High (0.9)
Fixed HPA at 8/8; do not reduce until lag is validated for all consumer groups.
```

```
## Changes evaluated but not recommended

**Reduce CPU requests** — Not recommended.
Fleet p95 reaches 86% of request; reducing requests would risk throttling during bursts.
Decision confidence: Very Low (0.3)
```

```
## Risks

Overall: Trimming is unsafe for CPU and replicas until consumer lag is validated for all groups.

- **Missing telemetry** — lag validated for only 1 of 8 consumer groups
- **Fixed HPA** — min=max may be intentional for warm JVM pools
```

```
## Conclusion

Keep CPU and memory requests unchanged and defer replica changes until consumer lag is validated for all eight groups. Re-assess in 14 days after instrumentation is complete.
```

Graph excerpt: `final_decision: KEEP_CONFIGURATION` — see [decision-graph.example.yaml](reference/decision-graph.example.yaml).

---

### Scenario: Conservatively right-sized (KEEP)

**User:** "Right-size neo-disbursement — metrics look low but we had lag spikes"

**Agent:**
1. COLLECT — consumer lag per group; partial lag → defer replica verdict
2. REASON — CPU/memory KEEP; replica DEFER
3. RENDER — Human Report leads with keep recommendation

**Expected fragments:**

```
🟢 Recommendation

Keep the current configuration.

Defer replica reduction until consumer lag is validated for all eight groups.

Severity: Warning — bursty CPU and partial lag coverage.
Assessment confidence: Very High (0.9)

Basis:
• Evidence completeness — fleet p95, throttle, and replica count present
• Evidence quality — measured utilization, not inferred
• Telemetry coverage — ★3 Datadog profile
• Contradiction resolution — avg vs p95 resolved in favor of p95

Review again in: 14 days
```

```
## Conclusion

Keep CPU and memory requests unchanged; defer replica changes until lag is validated across all consumer groups. Re-assess in 14 days.
```

**Golden `assessment_metadata` footer:**

```yaml
assessment_metadata:
  assessment_type: full
  started: "2026-06-28T11:00:00Z"
  finished: "2026-06-28T11:18:00Z"
  service: neo-disbursement
  final_decision: KEEP_CONFIGURATION
  assessment_confidence: 0.9
  assessment_complete: true
  precision:
    recommendations_evaluated: 4
    recommendations_ready: 0
    recommendations_deferred: 2
    recommendations_blocked: 1
    avg_decision_confidence: 0.9
  investigation_quality:
    coverage_pct: 100
    evidence_pct: 95
    telemetry_coverage_stars: 3
    confidence: high
```

---

### Scenario: Memory increase + KEEP CPU/replicas (mixed)

**User:** "neo-disbursement memory looks tight — peak above request but CPU is bursty"

**Agent:**
1. COLLECT — memory peak 1.34 GiB vs 1 GiB request; fleet CPU p95 152%; Kafka lag 1/8 groups
2. REASON — `REC_MEMORY_INCREASE` READY; `DEC_CPU_REQUEST` BLOCKED; replica DEFER
3. RENDER — Human Report leads with memory change, then CPU/replica holds

**Expected fragments:**

```
⬆️ Recommendation

Increase memory requests to approximately 1.5–1.75 GiB.

Keep CPU requests and replica count unchanged until Kafka lag telemetry is available.

Severity: Warning — memory peak exceeds request; CPU bursty but within headroom.
Assessment confidence: Moderate (0.72)

Basis:
• Evidence completeness — memory peak and CPU p95 present; Kafka lag partial
• Evidence quality — measured peak proxy, not inferred
• Telemetry coverage — ★3 Datadog profile
• Contradiction resolution — memory under-requested; CPU trim blocked by p95

Review again in: 14 days
```

```
## Conclusion

Increase memory requests to 1.5–1.75 GiB; keep CPU and replicas unchanged until lag is validated for all eight groups. Re-assess in 14 days.
```

---

### Scenario: TRIM_RESOURCES (stateless HTTP)

**User:** "Trim CPU on api-gateway — 8% average utilization"

**Agent:**
1. COLLECT — fleet p95 22%, limit/request ratio 2× (safe headroom)
2. REASON — `DEC_CPU_REQUEST` ALLOW; `REC_CPU_REDUCE` READY
3. RENDER — delivery pointer when git MCP found manifest path

**Expected fragments:**

```
🟢 Recommendation

Reduce CPU requests from 1000m to 300m.

Keep memory requests and replica count unchanged.

Severity: Info — fleet p95 well below trim threshold; no throttling observed.
Assessment confidence: Very High (0.9)

Basis:
• Evidence completeness — fleet p95, throttle, and memory peak present
• Evidence quality — measured utilization, not inferred
• Telemetry coverage — ★3 Datadog profile
• Contradiction resolution — avg vs p95 resolved; both support trim

Review again in: 7 days
```

```
## Risks

Overall: CPU trim is low risk with headroom confirmed; monitor throttle during soak.

- **Batch behavior** — weekly average understates peak if traffic is cyclic
```

```
## Conclusion

Reduce CPU requests to 300m; keep memory and replicas unchanged. Re-run this assessment in 7 days to verify throttle and fleet p95 remain within rollback triggers.
```

Graph: [decision-graph.trim.example.yaml](reference/decision-graph.trim.example.yaml).

---

### Scenario: Underprovisioned / SCALE_UP

**User:** "checkout-worker is throttling — do we need more CPU?"

**Agent:**
1. COLLECT — throttle 12%, fleet p95 98%, tight limit/request ratio
2. REASON — `STOP_REASON: throttle_high`; block trims; scale-up advisory
3. RENDER — `final_decision: SCALE_UP`

**Expected fragments:**

```
⬆️ Recommendation

Increase CPU requests to approximately 1500m to relieve sustained throttling.

Keep memory requests and replica count unchanged.

Severity: Critical — fleet p95 at 98% of request; throttle 12% over 7d.
Assessment confidence: Very High (0.9)

Basis:
• Evidence completeness — throttle, fleet p95, and limit/request ratio present
• Evidence quality — measured utilization, not inferred
• Telemetry coverage — ★3 Datadog profile
• Contradiction resolution — throttle confirms underprovisioned CPU

Review again in: 3 days
```

```
## Conclusion

Increase CPU requests to relieve sustained throttling; keep memory and replicas unchanged. Re-assess in 7 days after the change stabilizes.
```

Graph: [decision-graph.scale-up.example.yaml](reference/decision-graph.scale-up.example.yaml).

---

### Scenario: Service not found / disambiguation

**User:** "Is disbursement overprovisioned?"

**Agent:**
1. resolve-service — multiple deployments match `disbursement`
2. Stop before COLLECT — ask user to pick deployment + env

**Expected fragments:**

```
**Service resolution — disambiguation required**

Multiple deployments match `disbursement`:
- `neo-disbursement` (namespace `payments`, env `production`)
- `legacy-disbursement` (namespace `batch`, env `staging`)

Reply with deployment name and env to continue.
```

---

### Scenario: Metrics unavailable (degraded)

**User:** "Rightsize new-checkout — deployed 2 days ago"

**Agent:**
1. COLLECT — redeploy detected; `metrics_stale_redeploy` flag
2. REASON — defer cuts; partial assessment or blocked graph per user preference

**Expected fragments:**

```
**Gaps:** Metrics cover only 2d post-redeploy — cuts deferred until ≥7d stable window.

Assessment confidence: Low (0.4)

Basis:
• Evidence completeness — post-redeploy window too short
• Telemetry coverage — ★2 partial history
```

```
## Conclusion

Defer all trim recommendations until a full 7-day stable metrics window is available; re-run this skill after the soak period.
```

---

### Scenario: Namespace-level waste ranking

**User:** "Which services in namespace payments are most wasteful?"

**Agent:**
1. orchestrator `namespace_ranking` intent
2. COLLECT per deployment (lightweight); cost gate if CCM available
3. RENDER — ranked table by estimated waste

**Expected fragments:**

```
## Namespace waste ranking — `payments` (production)

| Deployment | CPU util (fleet p95) | Est. waste signal | Recommendation |
| payment-api | 18% | High request vs p95 | Trim candidate |
| payment-consumer | 86% | Bursty | Keep |
| ledger-sync | missing metrics | — | Defer |
```

---

### Scenario: Handoff from incident-rca (OOM)

**User:** "Assess checkout-api prod — RCA found OOMKilled"

**Expected fragments:**

```
**Handoff accepted** — window 2026-06-28T10:00Z–12:00Z from RCA.

**Assessment confidence:** Moderate (0.72)

Basis:
• Evidence completeness — OOM events and memory peaks present
• CPU headroom — low; memory limit 2× request

**Handoff → incident-rca** if new OOM events appear after sizing change.
```

---

### Scenario: Datadog fallback when Kubernetes history is unavailable

**User:** "Is api-gateway overprovisioned?" (Kubernetes MCP has live state; Datadog has 7d metrics)

**Expected fragments:**

```text
**k8s source profile:** Kubernetes MCP ✅ live / ❌ history | Datadog ✅ history + monitors

Live requests, limits, replicas, and HPA come from Kubernetes MCP. Seven-day fleet p95 and memory
peak use Datadog fallback because the cluster source exposes only point-in-time metrics.
```

### Scenario: Datadog absent but Kubernetes history is sufficient

**User:** "Right-size api-gateway" (Kubernetes MCP has live state + equivalent 7d history)

**Expected fragments:**

```text
**k8s source profile:** Kubernetes MCP ✅ live + history | Datadog ❌

Assessment continues. Incident, monitor, APM, change-history, and cost signals are marked unavailable;
their existing confidence/safety gates still apply.
```

### Scenario: neither source can support sizing

**User:** "Right-size api-gateway" (Kubernetes MCP has live state only; Datadog unavailable)

**Expected fragments:**

```text
Live state collected; seven-day CPU p95 and memory peak are missing.
STOP_REASON: insufficient_metrics
Blocked assessment — no sizing recommendation. Attempted sources and missing capabilities are listed.
```

---

## Machine vs human render contrast

### Before (machine-oriented — do not emit as primary report)

```text
SCHEMA_VERSION=3
FINAL_DECISION: KEEP_CONFIGURATION
DEC_CPU_REQUEST | BLOCKED | ✓ OBS_CPU_P95_FLEET
```

### After (human-first — default deliverable)

```text
## Recommendation
🟢 Recommendation

Keep the current configuration.

Fleet p95 reaches 30.4 cores — 152% of request — so weekly average understates burst demand; no trim is safe.

Assessment confidence: Very High (0.9)

Basis:
• Evidence completeness — all required sizing signals present
• Evidence quality — measured utilization
• Contradiction resolution — avg vs p95 resolved in favor of p95

## Conclusion

Keep the current configuration; re-assess in 14 days.
```

Internal IDs and formulas remain in the graph; weighted-sum arithmetic is developer reference only
([confidence-formula.md](reference/confidence-formula.md)).

### Appendix recommendation lifecycle (display labels)

Graph stores raw enum; appendix maps to report-aligned vocabulary:

```text
| REC_ID | State |
| REC_KAFKA_LAG_INSTRUMENT | DEFER |
| REC_MEMORY_INCREASE | CHANGE |
| REC_CPU_KEEP | KEEP |
| REC_REPLICA_KEEP | KEEP |
| REC_CPU_REDUCE | NOT RECOMMENDED |
```

Per-rec detail — `REC_CPU_KEEP` shows **State: KEEP** (graph `status: BLOCKED`), not `BLOCKED`.
True stop-gates on change recs remain **State: BLOCKED** in the appendix.

## Scenario contrast (decision paths)

| Path | `DEC_CPU_REQUEST` | `REC_CPU_REDUCE` | `assessment.final_decision` |
|------|-------------------|------------------|----------------------------|
| Bursty Kafka | BLOCKED | REJECTED | KEEP_CONFIGURATION |
| Stateless HTTP | ALLOW | READY | TRIM_RESOURCES |
| Throttle / OOM | ALLOW (scale) | — | SCALE_UP |

Assessment confidence 0.9 can coexist with `REC_REPLICA_REDUCE` confidence 0.3 — separate scores
(appendix shows numerics; human report shows bands per [confidence-bands.md](../docs/skill-framework/shared/confidence-bands.md)).
