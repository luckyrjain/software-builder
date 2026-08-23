---
workflow_version: 1.0
phase: analyze
produces:
  - rps_concurrency_targets
  - cpu_requirements
  - memory_requirements
  - db_load
  - queue_throughput
  - storage_growth
  - replica_requirements
  - assumptions_used
  - evidence_gaps
consumes:
  - demand_data
  - forecast_horizon
  - current_baseline
  - growth_rate
  - peak_avg_ratio
  - headroom_margin
---

# Analyze — turn demand + growth into capacity requirements

This is a **forecast**, not a measurement. Every derived number in this phase must trace back to an
assumption recorded in `assumptions_used` — never present a projected figure without naming what it was
derived from.

## RPS & concurrency

- Derive average RPS for the horizon by applying `growth_rate` (derived or supplied) to `demand_data`'s
  current average.
- Derive peak RPS by applying `peak_avg_ratio` to the projected average.
- Derive concurrency from projected peak RPS × average request latency, when a latency figure is present
  in `demand_data` or `current_baseline`; otherwise record concurrency as `Unknown — no latency figure
  supplied`, not a guessed value.

## CPU

- Scale current CPU usage (from `current_baseline`, if supplied) linearly with the projected RPS growth,
  unless `demand_data` or `current_baseline` supplies a per-request CPU cost figure, in which case use
  that instead of a flat linear assumption.
- If no current CPU baseline is supplied, record CPU requirements as directionally derived from RPS
  growth alone, flagged as lower-confidence in Notes — never presented with the same confidence as a
  baseline-anchored projection.

## Memory

- Same method as CPU: scale the known working-set/memory baseline by projected load growth, or apply a
  supplied per-request/per-connection memory cost figure if present.
- Distinguish request-scoped memory growth from data-volume-driven memory growth (e.g. cache size) when
  `demand_data` indicates the latter — do not conflate the two into one flat scaling factor.

## Database

- Project connection count from projected concurrency × a per-request connection assumption (from
  `current_baseline` if supplied, otherwise a stated default — never silently assumed).
- Project IOPS from projected RPS × a read/write ratio, when the ratio is derivable from `demand_data` or
  `current_baseline`; otherwise record IOPS as `Unknown — no read/write ratio available`.

## Queue

- Project queue throughput from `demand_data`'s own queue/message metrics, when present, scaled by
  `growth_rate`. When no historical queue data is supplied, record this section as an explicit evidence
  gap — do not infer queue load from RPS alone, since queue-shaped traffic (async jobs, batch work) does
  not necessarily track request traffic.

## Storage

- Project storage growth from `demand_data`'s own data-volume trend (not request volume), scaled by
  `growth_rate` and any stated retention policy. When no data-volume trend is present in `demand_data`,
  record this section as an evidence gap rather than deriving it from RPS.

## Replica requirements

- Derive projected replica count from projected peak RPS ÷ per-replica capacity (from `current_baseline`
  if supplied, otherwise flagged as an evidence gap), with a headroom margin applied on top of the
  bare-minimum figure — `headroom_margin` if the caller supplied one, otherwise this skill's default of
  20% — name the margin explicitly in `assumptions_used`, tagged caller-supplied or default.
- Compare the projected replica count against `current_baseline`'s known replica ceiling, if any, to
  determine whether this section proves a shortfall (feeds `Insufficient`), is thin (feeds `Marginal`),
  or is comfortable (feeds `Sufficient`) — see [reference/report-format.md](../reference/report-format.md)
  § Rules for the exact precedence this section's outcome feeds into.

## Assumptions and evidence gaps

- `assumptions_used` must name, for every derived figure: `growth_rate`, `peak_avg_ratio`, per-request
  CPU/memory/connection cost figures, read/write ratio, retention policy, per-replica capacity, and the
  headroom margin — each tagged as derived-from-data, caller-supplied, or default.
- **Any individual check that cannot be completed for lack of usable historical data (no derivable trend,
  no queue/DB/storage numbers, no baseline ceiling to compare against) is recorded in `evidence_gaps` as
  its own explicit gap — never silently skipped, never folded into a `Sufficient` or `Insufficient`
  reading for that section.** This feeds Report's Unknown handling directly.
