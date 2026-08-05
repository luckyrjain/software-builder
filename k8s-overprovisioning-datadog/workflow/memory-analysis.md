---
workflow_version: 3.3
phase: memory-analysis
produces:
  - memory_verdict
  - memory_inferences
consumes:
  - raw_metrics
  - evidence_ids
---

# Memory analysis

Checklist: [checklists.md](checklists.md#memory-sizing).

## Peak proxy (not p95)

Worst-pod app-container max: `max:kubernetes.memory.usage{...,kube_container_name:<app>} by {pod_name}`. Label **conservative peak proxy** — never call it p95. Cross-check Java: `jvm.heap_memory`.

## Verdicts

Apply [thresholds.md](../thresholds.md#memory-request-utilization). Trim: reduce toward `peak_proxy × 1.15` (~15% above peak proxy), round to 64Mi/128Mi. Check requests:limits ratio and OOM before trim.

OOM kills → `STOP_REASON: oom_kills` — underprovisioned; block trim.

## InitContainer memory

Sum init `memory.requests` into pod-level reservation. Compare init peak usage vs init request; flag
oversized init the same as main container (peak proxy on init container scope).

## Trends

Regressing memory trend lowers trim confidence — [trends.md](trends.md). **Seasonal** pattern blocks trim
on blended average.

## Limit/request ratio

After collecting `OBS_MEMORY_LIMIT` and `OBS_MEMORY_REQUEST`, compute the ratio and evaluate using
[thresholds.md](../thresholds.md#memory-request-utilization):

| Pattern | Risk | Action |
|---------|------|--------|
| `OBS_MEMORY_LIMIT ≈ OBS_MEMORY_REQUEST` (ratio < 1.1×) | High OOM risk on any burst | Subset of the `< 1.5×` BLOCKED rule below — additionally recommend raising the limit first, not just blocking the trim |
| `OBS_MEMORY_LIMIT ≥ 2× OBS_MEMORY_REQUEST` | Safe headroom | Reduce request toward `peak_proxy × 1.15` (~15% above peak proxy), rounded to 64Mi/128Mi |
| Peak usage > `OBS_MEMORY_REQUEST` but < `OBS_MEMORY_LIMIT` | Running on limit buffer | Increase request to ~15% above peak proxy (`peak_proxy × 1.15`, rounded to 64Mi/128Mi) before any trim |
| Peak usage > `OBS_MEMORY_LIMIT` | OOM inevitable | Increase both; `STOP_REASON: oom_kills` |

**Authoritative threshold:** emit `DEC_MEMORY_REQUEST` as BLOCKED with reason `tight_memory_limits`
when ratio `< 1.5×`, regardless of utilization — mirrors `cpu-analysis.md`'s CPU rule. Memory gets the
*same* cutoff, not a laxer one, even though CPU only throttles on breach: an OOM kill is a hard
process kill, so a tight memory limit is at least as risky as a tight CPU limit at the same ratio.

Include `OBS_MEMORY_LIMIT / OBS_MEMORY_REQUEST` ratio in the Human Report whenever recommending
a memory request change.
