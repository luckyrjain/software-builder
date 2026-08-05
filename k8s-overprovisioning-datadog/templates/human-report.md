<!-- Markdown renderer layout — Human Report only. Source: decision_graph. See render/markdown.md -->

# Human Report templates

Prose-first layout. **No `OBS_*` / `DEC_*` / `REC_*` / `EVID_*` in output.**

**Anti-patterns (Human Report body):** no agent mode instructions (e.g. "Type ACT"), posting confirmations, MCP setup steps, or PLAN/ACT workflow CTAs. Post-render chat instructions belong in `SKILL.md` only.

## ExecutiveSummary

Rendered heading: **`## Recommendation`**. Lead with a prominent recommendation block — emoji + short headline, then supporting lines.

### Lead with changes, then holds

The first one or two sentences under `{emoji} Recommendation` are the **lead block** — punchy, imperative, max two sentences:

1. **Lead with what will change** — concrete values or range when known (increase/reduce/trim/scale).
2. **Then what stays unchanged** — and a brief why (telemetry gap, dependency, burst risk, etc.).

When the primary action is **no change** (pure KEEP), lead with that hold and state what is deferred or blocked in sentence two.

**Canonical (mixed change + holds):**

> Increase memory requests to approximately 1.5–1.75 GiB. Keep CPU requests and replica count unchanged until Kafka lag telemetry is available.

**Anti-pattern (holds first when a change is primary):**

> Keep CPU and replica counts unchanged. Memory requests are below actual usage…

```text
{emoji} Recommendation

{primary action — what changes, with values/range when known}.

{what stays unchanged + brief why; omit when pure KEEP with no secondary holds}.

Severity: {severity} — {severity_reason}
Assessment confidence: {band} ({numeric})

Basis:
• {factor bullet 1 — short clause with value when known}
• {factor bullet 2}
• {factor bullet 3}
• {factor bullet 4}

Review again in: {review_after}
```

| `assessment.final_decision` | Emoji | Lead sentence (change first) | Second sentence (holds / why) |
|-----------------------------|-------|------------------------------|-------------------------------|
| `KEEP_CONFIGURATION` | 🟢 | Keep the current configuration. | No CPU, memory, or replica changes are recommended. |
| `TRIM_RESOURCES` | 🟢 | Reduce CPU requests from 1000m to 300m. | Keep memory requests and replica count unchanged. |
| `INVESTIGATE` | 🟡 | Complete missing telemetry before any resource cut. | Keep current requests until validation finishes. |
| `BLOCKED` | 🔴 | No changes until blockers are resolved. | See Risks for manifest drift, throttle, or stability gates. |
| Underprovisioned / scale-up path | ⬆️ | Increase memory requests to approximately 1.5–1.75 GiB. | Keep CPU requests and replica count unchanged until Kafka lag telemetry is available. |

Band from numeric score — see [confidence-formula.md](../reference/confidence-formula.md) (sole source):
≥0.85 Very High · 0.65–0.84 Moderate · 0.40–0.64 Low · <0.40 Insufficient.

**Never in Human Report:** `0.35×…`, weighted-sum arithmetic, or `assessment.assessment_confidence.arithmetic`.

Optional 2–3 sentence narrative after the confidence block — reference outcomes, not IDs.

## CurrentHealth

### CPU

Prose: avg utilization, fleet p95 / max, throttle %, verdict phrase (right-sized / overprovisioned / tight / defer).

### Memory

Prose: avg, peak proxy (label as peak proxy, not p95), OOM count, requests:limits ratio if relevant.

### Replicas

Prose: count, HPA min/max/current, lag summary (X/N groups), partition note if relevant.

## OptimizationDecision

Per dimension (CPU requests, memory requests, replicas, HPA, stability):

```text
**{dimension}:** {ALLOW|BLOCKED|DEFER human phrase}. {explanation from DEC_*.explanation}
```

Example:

> **CPU requests:** Keep unchanged. Fleet p95 exceeds the trim threshold.
> **Replicas:** Defer reduction. Consumer lag validated for only 1 of 8 groups.

## EvidenceSummary

Table or bullets — **human label + value + short note**. No ID column.

**Sort rows by operational importance** (most sizing-critical first):

1. Fleet CPU p95 (include throttle % in Notes when present)
2. Kafka consumer lag
3. Memory peak (worst pod)
4. HPA (min / max / current)
5. CPU average (7d)
6. HTTP metrics (latency, error rate, RPS)
7. Pod restarts (7d)
8. Manifest drift

| Signal | Value | Notes |
|--------|-------|-------|
| Fleet CPU p95 | 30.4 cores (152% of request) | Pod-scoped dist; throttle 0.8% |
| Consumer lag (max) | 12 messages | 1/8 groups validated |
| Memory peak (worst pod) | 1.34 GiB | Peak proxy, not p95 |
| HPA | min 8 / max 8 / current 8 | Fixed scale |
| CPU average (7d) | 2.12 cores | App container — understates bursts |
| Pod restarts (7d) | 0 | Stable |

Include missing signals as plain language (*PDB status: not checked*).

## RecommendationsSummary

**Sort order:** concrete work before holds; observability before sizing when both are present.

1. **Tier 1 — Observability** — `REC_KAFKA_LAG_INSTRUMENT`, `REC_PARTITION_VALIDATE`, `REC_*_OBSERVE`, and other instrument/validate/observe recs ([render/markdown.md](../render/markdown.md#recommendationssummary-sort-order))
2. **Tier 2 — Actionable change** — `READY` / `COMPLETED` resource or HPA changes (`REC_*_INCREASE`, `REC_*_REDUCE`, …); `DEFERRED` change recs that are not holds
3. **Tier 3 — Hold** — `REC_*_KEEP`, `REC_REPLICA_KEEP` → **Decision: Keep**

Within tier: `priority` (`P0`/`P1`/`P2`) → decision confidence → benefit → effort. **Separate state from confidence** — do not combine as `(Blocked, High confidence)`.

Render only recommendations where `status` is **not** `REJECTED` (see RejectedChanges).

```text
**{priority} — {title}**
Decision: Keep | Ready | Defer | Blocked
Decision confidence: {band} ({numeric})
{prose rationale with inline values}.
```

Human State mapping from graph `status` and rec intent:

| Graph `status` | Rec pattern | Human line |
|----------------|-------------|------------|
| `BLOCKED` | `REC_*_KEEP`, `REC_*_OBSERVE` | **Decision: Keep** |
| `BLOCKED` | change rec blocked by STOP_REASON / dependency | **Blocked** |
| `READY` / `COMPLETED` | actionable change | **Ready** |
| `DEFERRED` | | **Defer** |
| `REJECTED` | | → RejectedChanges section only |

Include rollback triggers as plain metrics (*rollback if throttle exceeds 5%*).

For each **Ready** change recommendation, add a **Where to apply** line pointing to the likely
delivery path (from git MCP manifest lookup or user-provided repo layout):

```text
**Where to apply:** `helm/<service>/values.yaml` (CPU requests under `resources.requests`)
```

Use the best match among Helm `values.yaml`, Kustomize overlay, raw Deployment manifest, Terraform
module, or GitOps path (ArgoCD Application / Flux Kustomization). When unknown, state *path not
verified — confirm with service owner*.

## RejectedChanges

Rendered heading: **`## Changes evaluated but not recommended`**. Omit when no `REJECTED` recs.

```text
**{title}** — Not recommended.
{prose rationale with inline values}.
Decision confidence: {band} ({numeric})
```

Do **not** use inline prefix `Rejected —` in Recommendations bullets.

## PostChangeVerification

When ≥1 **Ready** change recommendation exists, append this block (default **7d** unless
`assessment.review_after` differs):

```text
### After you apply

1. **Wait {review_after}** (typically 7d) for metrics to stabilize post-deploy.
2. **Re-run this skill** on the same service with the same window length.
3. **Verify:** throttle rate, fleet p95, OOM count, and consumer lag match projections; rollback
   triggers from the recommendation still hold.
4. **Escalate** to **incident-rca** if errors or instability appear during the soak period.
5. **Machine metadata:** set `assessment_metadata.history.review_after`, `next_assessment_due`, and
   `scheduled_recheck_prompt` per [report.md](../workflow/report.md) §Assessment metadata footer.
```

Cross-skill: paste the Human Report recommendation block into a follow-up invocation when comparing
before/after.

## RisksSummary

Rendered heading: **`## Risks`**. Open with one-sentence overall framing, then bullets ordered by **operational impact** (highest first):

```text
Overall: {one sentence — e.g. "Trimming is low risk for memory but unsafe for CPU and replicas until lag coverage improves."}
```

1. **Missing telemetry** — invalidates or caps the recommendation (lag gaps, p95 unavailable, PDB unchecked)
2. **Partition skew** — replica cuts unsafe until distribution validated
3. **Fixed HPA** — min=max may be intentional (warm pools, SLAs)
4. **Batch behavior** — seasonal or cyclic load; weekly average understates peak need
5. **Cost** — savings estimate caveats, node-packing uncertainty (nice-to-have context)

No `STOP_REASON` slugs or `INV-*` codes in the Human Report.

Optional short table with human signal names only:

| Check | Status |
|-------|--------|
| Fleet CPU p95 supports trim | No |
| All consumer groups lag validated | 1/8 |

## Conclusion

Rendered heading: **`## Conclusion`**. Last Human Report section before the Technical Appendix separator.

```text
{2–4 sentences — restate recommendation, key constraint, review cadence. No IDs, no automation CTAs.}
```

Example:

> Keep CPU and memory requests unchanged and defer replica changes until consumer lag is validated for all eight groups. Re-assess in 14 days after instrumentation is complete.
