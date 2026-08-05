---
workflow_version: 3.3
phase: cpu-analysis
produces:
  - cpu_verdict
  - cpu_inferences
consumes:
  - raw_metrics
  - evidence_ids
  - service_identity
---

# CPU analysis

Requires unit conversion before ratios. Checklist: [checklists.md](checklists.md#cpu-sizing).

## Unit conversion

| Convert | Formula |
|---------|---------|
| Nanocores → cores | `/ 1_000_000_000` |
| Utilization % | `(usage_nanocores / 1e9) / cpu_requests_cores × 100` |
| Throttle % | `(cpu_throttled_rate / cpu_period_rate) × 100` |

Never compare raw nanocores to core-based requests.

## Two CPU signals

| Signal | Source | Use |
|--------|--------|-----|
| Fleet p95/p99 | `kubernetes.pod.cpu.usage.dist` / `req_pct.dist` | **Sizing** |
| App max per pod | `max:kubernetes.cpu.usage.total{...,kube_container_name:<app>} by {pod_name}` | **Burst** |

`.dist` is pod-scoped (sidecar-inclusive) — cross-check app max; note scope mismatch.

Fleet p95 unavailable → `STOP_REASON: missing_fleet_p95`; defer trim; do not cite `ceil(p95 × 1.5)`.

## Deployment total cross-check

`per_pod × replicas ≈ deployment_total` (~5%). Mismatch → `deployment_total_mismatch` — blocks waste/cost.

## Cyclic check

Before CPU verdict tables when trim proposed. Visualize 7d CPU; if cyclic, re-run scalars on **peak window** ([queries.md](../queries.md#peak-window-queries-step-4a)). Peak avg > 60% request while 7d avg < 30% → **Mixed / cyclic** — size on peak.

## Verdicts

Apply [thresholds.md](../thresholds.md#cpu-request-utilization). Trim from fleet p95: `ceil(p95_cores × 1.5, 50m)` when available.

## InitContainer CPU

When init containers exist, include their requests in pod CPU totals. Flag init request **> 2× init usage
max** as auxiliary waste — main-container trim does not fix init bloat.

## Trends

Classify per [trends.md](trends.md) before inference — **Seasonal** blocks trim on blended 7d avg.

## Limit/request ratio

After collecting `OBS_CPU_LIMIT` and `OBS_CPU_REQUEST`, compute the ratio and evaluate using
[thresholds.md](../thresholds.md#cpu-limits):

| Ratio | Label | Action |
|-------|-------|--------|
| `OBS_CPU_LIMIT / OBS_CPU_REQUEST > 4×` | Limit likely too high | Note in observations; scheduling visibility reduced |
| `2–4×` | Acceptable headroom | No action |
| `1.5–2×` | Tight limits (advisory) | Flag in observations — worth a human look, but does not itself set `DEC_CPU_REQUEST: BLOCKED` (see authoritative threshold below) |
| `OBS_CPU_LIMIT ≈ OBS_CPU_REQUEST` (< 1.1×) | Near-zero burst headroom | Subset of the `< 1.5×` BLOCKED rule below — additionally recommend raising the limit first, not just blocking the trim |

**Authoritative threshold:** emit `DEC_CPU_REQUEST` as BLOCKED with reason `tight_cpu_limits` when
ratio `< 1.5×`, regardless of utilization — a seemingly over-provisioned request against a tight
limit creates a silent throttle trap on any load spike. The `1.5–2×` table row above is advisory
only; only this rule sets formal `BLOCKED` status.
