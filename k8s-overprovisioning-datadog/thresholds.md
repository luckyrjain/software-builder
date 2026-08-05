# Overprovisioning Thresholds

Conservative defaults for production Java/K8s services. Tighten for latency-sensitive or batch-heavy workloads; loosen for services with extreme burst patterns.

## CPU request utilization

Measured as: `(avg cpu usage in cores) / (cpu request in cores)` per pod, and summed at deployment level.

| Range | Label | Action |
|-------|-------|--------|
| 0–30% avg (7d) but peak-window avg > 60% of request | Mixed / cyclic | Do not size on weekly avg; re-run on peak window and size from that |
| 0–30% avg, fleet p95 < 70% of request | Overprovisioned | Reduce requests; target 50–70% avg with headroom |
| 0–30% avg, fleet p95 ≥ 70% of request | Mixed | Avg low but fleet bursts use headroom — trim cautiously or defer |
| 0–30% avg, fleet p95 unavailable | Mixed / defer | Use app max per pod conservatively; do not cite p95 formula |
| 30–60% avg | Moderate waste | Trim only if p95 < 70% of request |
| 60–85% avg | Right-sized | No change unless cost pressure |
| 85–100% avg | Tight | Monitor; do not reduce |
| Throttle rate > 5% (7d avg) | Underprovisioned | Increase requests or limits — see CPU throttle rate table below |

**Peak check:** **fleet** p95 from `kubernetes.pod.cpu.usage.dist` / `req_pct.dist` (no `by {pod_name}`) for sizing. **App-container max per pod** from `max:kubernetes.cpu.usage.total{...,kube_container_name:<app>} by {pod_name}` for burst/outlier checks. If fleet p95 < 50% of request and worst-pod max < 150% of request, strong overprovision signal. If fleet p95 > 70% of request, do not reduce requests.

`kubernetes.pod.cpu.usage.dist` is **pod-scoped (sidecar-inclusive)** — with sidecars present, treat its fleet p95 as a **conservative (over-) estimate** of app usage and cross-check the app-container max; never compare dist p95 directly to app-only requests without noting the scope mismatch.

**Burst ratio:** fleet `req_pct.dist` p95 for sizing; worst-pod app max/request for outlier classification (> 1.5× = bursty).

**Suggested CPU request after trim:** `ceil(fleet_p95_cores * 1.5, 50m)` from `kubernetes.pod.cpu.usage.dist`. Without fleet p95, defer trim.

**Post-change projection (mandatory before any CPU cut):** After computing the proposed request, verify
`proposed_cpu_request >= fleet_p95_cores` (must still cover measured fleet p95 — the 1.5× multiplier is
headroom above p95, not a target below it). If any cut would set requests below fleet p95, **block the
cut** (`STOP_REASON: projection_failed`). Same for memory: `proposed_mem_request >= peak_proxy` before
emitting a memory trim.

## CPU limits

Limits much higher than peak usage are normal but wasteful for scheduling visibility.

| Limit / peak ratio | Label |
|--------------------|-------|
| > 4× | Limit likely too high |
| 2–4× | Acceptable headroom |
| < 2× | Tight; watch throttling |

## CPU throttle rate

Measured as: `(rate(throttled.periods) / rate(cfs.periods)) × 100` over the analysis window.

| Throttle % (7d avg) | Label | Action |
|---------------------|-------|--------|
| 0% | None | Safe to trim if utilization is low |
| 1–5% | Low | Monitor; trimming OK with caution |
| 5–25% | Moderate | Do not reduce requests |
| > 25% | High | Underprovisioned — increase CPU request or limit |

**Cross-reference (resolves the >5% boundary):** **> 5% throttle (7d avg) → CPU dimension verdict =
Underprovisioned; action = do not reduce requests** (Moderate 5–25% blocks any trim; High > 25% calls
for an increase). This is the same > 5% gate used in the CPU request utilization table and *Signals
that block downsizing*.

## Memory request utilization

Measured as: `(avg memory usage bytes) / (memory request bytes)`.

| Range | Label | Action |
|-------|-------|--------|
| 0–50% avg | Overprovisioned | Reduce memory request |
| 50–90% avg | Right-sized | Keep |
| 90–100% avg, peaks ≤ limit | Borderline | Consider +128Mi–256Mi on request |
| Peaks > request, < limit | Running on limit buffer | Increase request to ~15% above peak proxy (`peak_proxy × 1.15`, rounded to 64Mi/128Mi) |
| OOM kills | Underprovisioned | Increase request and/or limit |

**Suggested memory request after trim:** `peak_proxy_usage × 1.15` (~15% above observed peak proxy), rounded to 64Mi or 128Mi. Example: peak proxy 1.34 GiB (~1372Mi) → `1372 × 1.15` ≈ 1600Mi.

**Memory peak proxy (single method — not a true p95):** Kubernetes has no `.dist` metric for memory.
Use the **worst-pod app-container max over the analysis window**:
`max:kubernetes.memory.usage{...,kube_container_name:<app>} by {pod_name}` — the highest single pod's
peak. This is a **conservative peak proxy**; label it as such and **never call it p95** (no actual
percentile is computed). For Java services, cross-check with
`avg:jvm.heap_memory{service:<name>,env:production}` when available. Do **not** use the deployment-wide
`sum` for this calculation — always use the per-pod max.

Do not conflate **limit headroom** (2 GiB limit, 0.5 GiB usage) with overprovisioned **requests**.

**Memory limits ratio:** check the `requests:limits` ratio against peak usage to assess OOM risk before recommending a request trim:

| Pattern | Risk | Action |
|---------|------|--------|
| `requests ≈ limits` (tight limits) | High OOM risk on any burst | Do not trim requests; consider raising limits first |
| `limits ≥ 2× requests` | Safe headroom | Reduce request toward `peak_proxy × 1.15` (~15% above peak proxy), rounded to 64Mi/128Mi |
| Peak usage > requests but < limits | Running on limit buffer | Increase request to ~15% above peak proxy (`peak_proxy × 1.15`, rounded to 64Mi/128Mi) before any trim |
| Peak usage > limits | OOM inevitable | Increase both request and limit; block trim |

Query per-pod limits alongside requests in the per-pod config section: `avg:kubernetes.memory.limits{...} by {pod_name}`. Include the `requests:limits` ratio in the report whenever recommending a memory request change.

## Replica / HPA

| Pattern | Label |
|---------|-------|
| min = max = current, low per-pod CPU | Fixed over-scale |
| min = max, high per-pod CPU | Fixed but possibly necessary |
| min < max, replicas at min most of 7d | HPA floor may be too high |
| Replicas at max frequently | Under-scaled for traffic |
| desired > current sustained | Scale-up lag or pressure — do not reduce |
| desired < current, low CPU, restrictive `scaleDown.policies` | Scale-down policy lag — not overscaled |
| desired at max, low CPU utilization | HPA metric misaligned — investigate |
| No HPA (metrics absent) | Fixed replica count — use `replicas_ready` only |

**Do not recommend a specific CPU target %** (e.g. 65%) unless CPU is proven to be the correct scaling signal. For Kafka-heavy bursty workloads, recommend **custom/external metrics** (consumer lag, queue depth, processing latency) instead.

### HPA metric suitability

Pick the autoscaling signal from the **workload type**, not by default to CPU. Use this to justify
(or reject) a CPU target before recommending any HPA metric change (apply the two-phase rule below:
Phase 1 observe ≥2 weeks → Phase 2 evaluate correlation).

| Workload type | Candidate metrics | Suitability | CPU target forbidden when |
|---------------|-------------------|-------------|---------------------------|
| Stateless HTTP/gRPC, CPU-bound | CPU utilization %, RPS | CPU **High** | — (CPU is valid once correlation confirmed) |
| Kafka / SQS / queue consumer | Consumer lag, oldest message age, queue depth | Lag/age **Very High**; CPU **Low** | Always — lag-driven work decouples CPU from backlog |
| Bursty JVM (warm pools, GC-heavy) | RPS, queue depth, latency | CPU **Low–Medium** | Avg CPU low but fleet p95/max bursts — GC spikes masquerade as load |
| I/O-bound (proxies, log shippers, file processors) | Network throughput, connection count | CPU **Low** | CPU avg < 20% with high sustained network I/O |
| Batch / cron-driven | Queue depth, scheduled concurrency | CPU **Low** | Load is time-of-day cyclic, not CPU-tracked |

**Mirror this per recommendation** as a one-line `Metric suitability:` row in the **Technical Appendix** (e.g.
`CPU Low | Kafka lag High | Oldest message age Very High`). Human Report: one prose sentence — see [examples.md](examples.md).

Before lowering `minReplicas`:

- **Kafka consumer lag** stable and within SLO for **every consumer group** (mandatory — quantify coverage X/N)
- **Lag duration** computed (`lag / consume_rate`) — not raw message count alone
- **Kafka partition count** documented; `proposed_replicas ≤ partitions` unless justified
- PDB `minAvailable` / `maxUnavailable`
- Multi-AZ spread requirements
- **Cluster Autoscaler** — confirm node reduction is possible for $ savings
- Known batch windows not visible in 7d window

**Scale-down policy lag:** when `hpa_desired < hpa_current` but per-pod CPU is low, check
`spec.behavior.scaleDown` in the manifest — `stabilizationWindowSeconds` and restrictive `policies`
(e.g. max 10% or 4 pods per minute) intentionally hold replicas above desired. This is not fixed
over-scale; do not recommend replica cuts until desired ≈ current has held through the policy window.

**Staged rollout:** never cut replicas > 25% in one step. Example: 10 → 8 (monitor 1 week) → 6 → 4. Track lag, p99 latency, throttle %, GC pauses, error rate between steps.

## Container restarts

Measured with `sum:monotonic_diff(kubernetes_state.container.restarts)` per pod over the analysis window.

| Per-pod restarts (7d) | Deployment signal | Action |
|-----------------------|-------------------|--------|
| 0 on all pods | Stable | No restart concern |
| 1–2 on any pod | Low | Note in report; does not block downsizing |
| 3–4 on any pod | Elevated | Investigate; caution on replica/request cuts |
| ≥ 5 on any pod, or max per-pod ≥ 10 | High | Blocks downsizing until root cause found |
| Avg > 2 restarts/pod (`restarts` total ÷ `pods` scalar) | Crash-loop risk | Blocks downsizing |

Ignore deployment-wide total > 0 alone — always check `restarts_max_per_pod` and per-pod distribution.

## Active monitors

A currently-firing **required-severity** monitor for the service blocks downsizing — the workload is
already in a degraded/alerting state. Discover via `search_datadog_monitors`
(`service:<name> status:alert`; see [queries.md](queries.md#active-monitors-alerts-check-before-recommending-downsizing)).

| Monitor state | Effect |
|---------------|--------|
| Required-severity monitor in `alert` | **Blocks downsizing** for the affected dimension; cap that dimension's decision confidence at 0.30 |
| Warn-only / low-priority monitor in `alert` | Note in report; does not block |
| `status:no data` | Ignore for the block decision (often missing telemetry, not a live alert) |

## Deployment-level waste estimate

```
wasted_cpu_cores = sum(cpu_requests) - sum(cpu_usage_in_cores)
waste_pct = wasted_cpu_cores / sum(cpu_requests) * 100
```

Report waste in cores and percentage. Memory waste uses the same formula with GiB.

**Data consistency gate:** before reporting waste or cost, verify `per_pod × replicas ≈ deployment_total` (within ~5%) for CPU and memory requests and usage. Arithmetic mismatch blocks waste/cost sections until reconciled.

## Cost estimation

Moved to **[cost-estimation.md](cost-estimation.md)** for maintainability. Sections:

- [Priority for recommendations (R0 → R1 → R2)](cost-estimation.md#priority-for-recommendations-r0-r1-r2)
- [Monthly savings formulas](cost-estimation.md#monthly-savings-formulas)
- [Calibrating $/core and $/GiB](cost-estimation.md#calibrating-core-and-gib)
- [Node packing](cost-estimation.md#node-packing)
- [Sidecar capacity planning](cost-estimation.md#sidecar-capacity-planning)

## Confidence levels (qualitative)

**Use the numeric 0–1 scores below (Decision Confidence) for reports; this qualitative table is legacy
shorthand only.**

| Level | When |
|-------|------|
| **High** | 7d+ stable metrics, no throttling/OOM, clear utilization gap, p95-based sizing |
| **Medium** | CPU/memory trim on non-bursty workloads; partial workload context |
| **Low** | Replica/HPA changes, bursty CPU (p95 > request or max-only sizing), Kafka consumers, missing lag coverage (X/N groups) |

## Decision Confidence & Recommendation Framework

Moved to **[recommendation-framework.md](recommendation-framework.md)** for maintainability. Sections:

- [Decision Confidence (numeric 0–1)](recommendation-framework.md#decision-confidence-numeric-01)
- [Ordering rule](recommendation-framework.md#ordering-rule)
- [Lifecycle status](recommendation-framework.md#lifecycle-status-graph-enum)
- [Impact dimensions](recommendation-framework.md#impact-dimensions)
- [Human phrasing](recommendation-framework.md#human-phrasing-rendered-report)
- [Rollback trigger format](recommendation-framework.md#rollback-trigger-format-required-on-every-ready-change-rec)
- [Risk scoring](recommendation-framework.md#risk-scoring-likelihood-impact)
- [Verdict labels](recommendation-framework.md#verdict-labels)
