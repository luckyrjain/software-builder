---
workflow_version: 1.0
phase: report
produces:
  - CAPACITY_PLAN.md
consumes:
  - rps_concurrency_targets
  - cpu_requirements
  - memory_requirements
  - db_load
  - queue_throughput
  - storage_growth
  - replica_requirements
  - assumptions_used
  - evidence_gaps
---

# Report — derive verdict, build CAPACITY_PLAN.md

## Verdict derivation

Fixed, four states, precedence **`Insufficient` > `Unknown` > `Marginal` > `Sufficient`** (worst-first):

1. **`Insufficient`** — set if any forecast section's projected requirement (RPS/concurrency, CPU,
   memory, DB, queue, storage, or replicas) exceeds a known ceiling from `current_baseline` within
   `forecast_horizon`. A proven shortfall always wins, regardless of how many other sections are clean.
2. **`Unknown — insufficient historical data`** — set, if `Insufficient` was not already set, when any
   section is present in `evidence_gaps` for lack of usable historical data (no derivable trend and no
   `growth_rate` supplied, no queue/DB/storage numbers, no baseline ceiling to compare against). An
   evidence gap is not proof of a shortfall and not proof of sufficiency — it is its own state.
3. **`Marginal`** — set, if neither of the above applies, when at least one section's projection sits
   within a narrow margin of a known ceiling, or an assumption used to derive it carries real stated
   uncertainty even though a number was produced.
4. **`Sufficient`** — set only when every section has a usable projection, none exceeds or sits near a
   known ceiling, and `evidence_gaps` is empty.

Never collapse an evidence gap into `Insufficient` (fabricates a finding no check made) or into
`Sufficient` (hides a real gap) — see
[reference/report-format.md § Rules](../reference/report-format.md#rules) for the full derivation and the
`Unknown` handling this section feeds.

## Build

Build per [reference/report-format.md](../reference/report-format.md) — fixed section order (RPS &
concurrency, CPU, Memory, Database, Queue, Storage, Replica requirements, Assumptions), every section
present even when marked `Unknown`, Notes naming every evidence gap and any discrepancy or suspicious
embedded content flagged during Inputs/Analyze.

## Machine artifact v2

Emit the common machine fields and map `Sufficient` to `PASS`, `Marginal` to `CONDITIONAL`,
`Insufficient` to `FAIL`, and `Unknown — insufficient historical data` to `UNKNOWN`. Preserve the
human Headroom verdict in `raw_verdict` and record assumptions as conditions.
