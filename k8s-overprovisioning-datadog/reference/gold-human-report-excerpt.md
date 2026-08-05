# Gold Human Report excerpt (format few-shot)

Load in **RENDER** before authoring markdown. Match **section order and formatting** — do not copy
findings; translate from `validated_graph`.

Fictional context: `payment-consumer` · production · bursty Kafka · mixed change + holds.

---

# Deployment Optimization Readiness Assessment

## Recommendation

⬆️ Recommendation

Increase memory requests to approximately 1.5–1.75 GiB.

Keep CPU requests and replica count unchanged until Kafka lag telemetry is available.

Severity: Warning — memory peak exceeds request; CPU and replicas are right-sized pending lag coverage.
Assessment confidence: Moderate (0.72)

Basis:
• Evidence completeness — memory peak and CPU p95 present; Kafka lag partial
• Evidence quality — measured utilization, not inferred
• Telemetry coverage — ★3 Datadog profile
• Contradiction resolution — memory under-requested; CPU bursty but within headroom

Review again in: 14 days

## Current Health

CPU averages 2.1 cores per pod against a 20-core request (11% utilization), but fleet p95 reaches
30.4 cores — 152% of request — indicating burst-driven load. Memory peaks at 1.3 GiB against a 2 GiB
request. Eight replicas run at HPA minimum with consumer lag stable across instrumented groups.

## Optimization Decision

**CPU requests:** Keep unchanged. Fleet p95 exceeds the trim threshold; reducing requests would risk
throttling during bursts.

**Memory requests:** Raise request to ~1.5–1.75 GiB; peak exceeds current request.

**Replicas:** Defer any reduction until partition distribution is validated.

## Evidence

| Signal | Value | Notes |
|--------|-------|-------|
| Fleet CPU p95 | 30.4 cores (152% of request) | Pod-scoped dist; throttle 0.8% |
| Consumer lag (max) | 12 messages | 1/8 groups instrumented |
| Memory peak (worst pod) | 1.34 GiB | Peak proxy, not p95 |
| HPA | min 8 / max 8 / current 8 | Fixed scale |
| CPU average (7d) | 2.12 cores | Understates bursts |

## Recommendations

**P0 — Instrument missing consumer lag**
Decision: Defer
Decision confidence: Low (0.4)
Lag coverage is 1/8 groups. Complete instrumentation before any replica change.

**P1 — Raise memory requests**
Decision: Ready
Decision confidence: High (0.85)
Worst-pod peak reaches 1.34 GiB against a 1 GiB request; raise request to ~1.5–1.75 GiB with limit ≥ 2× request.

**Where to apply:** `helm/payment-consumer/values.yaml` — memory requests under `resources.requests`

**P2 — Keep CPU requests**
Decision: Keep
Decision confidence: Very High (0.9)
Fleet p95 reaches 152% of request; bursts justify current headroom.

**P2 — Keep replica count**
Decision: Keep
Decision confidence: Very High (0.9)
Fixed HPA at 8/8; do not reduce until lag is validated for all consumer groups.

## Changes evaluated but not recommended

**Reduce CPU requests** — Not recommended.
Fleet p95 reaches 152% of request; reducing requests would risk throttling during bursts.
Decision confidence: Very Low (0.3)

## Post-change verification

After you apply memory changes: wait 7 days, re-run this skill, verify memory peak and OOM counts.
Escalate to **incident-rca** if instability appears.

## Risks

Overall: Trimming is unsafe for CPU and replicas until consumer lag is validated for all groups; memory
is under-requested today.

- **Missing telemetry** — lag validated for only 1 of 8 consumer groups
- **Fixed HPA** — min=max may be intentional for warm JVM pools

## Conclusion

Raise memory requests to ~1.5–1.75 GiB; keep CPU and replicas unchanged until lag is validated for all
eight groups. Re-assess in 14 days after instrumentation is complete.

---

*Technical Appendix follows `---` separator — `OBS_*` / `DEC_*` / `REC_*` IDs appear only there.*
