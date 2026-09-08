# Smoke test — expected minimal output

Run after install or any edit to this skill. Use a `demand_data` series with at least a few months of
usage numbers and a visible trend, a `forecast_horizon`, and a `current_baseline` (current replica count,
resource sizing) so the happy path is exercised, not just the evidence-gap path.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> `demand_data: <monthly RPS/usage series with a visible upward trend>, forecast_horizon: 6 months, current_baseline: {replicas: 4, cpu_per_replica: 2 cores, db_connections: 100}`

## A correct minimal output contains

1. **Phase announcement** — Inputs parsed (`demand_data`, `forecast_horizon`, `current_baseline` present
   or defaulted) before Analyze starts.
2. **Scope announcement** — which sections have usable data to project (RPS/concurrency, CPU, memory,
   DB, queue, storage, replicas) and which, if any, are marked `Unknown` for lack of input.
3. **Assumptions stated explicitly** — growth rate and peak:average ratio, each tagged as
   derived-from-data, caller-supplied, or default.
4. **`CAPACITY_PLAN.md` produced**, per [reference/report-format.md](report-format.md), with all eight
   sections present in fixed order (RPS & concurrency, CPU, Memory, Database, Queue, Storage, Replica
   requirements, Assumptions), a bold `**Headroom: <state>**` line, and Notes naming any evidence gaps.
5. **No section silently dropped** — a section with no usable input still appears, marked `Unknown`, not
   omitted.
6. **Confirmation / next step** — a one-line pointer to the Cross-skill escalation table when the
   forecast should be checked against live rightsizing data or feeds a cost/scaling sprint.

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| `demand_data` has no derivable trend and no `growth_rate` supplied | Analyze records the gap; Headroom verdict is `Unknown — insufficient historical data`, not a silently assumed `Sufficient` |
| No `current_baseline` supplied | Forecast sections still compute projected targets; any section that needs a known ceiling to score headroom (e.g. replica requirements) is scored against the forecast's own targets only, with the missing ceiling named in Notes |
| No historical queue or DB data supplied | Those sections' rows are marked `Unknown`, named in Notes, and excluded from the `Insufficient`/`Marginal` check for that dimension — they do not silently upgrade the overall verdict to `Sufficient` |
| `demand_data` or `forecast_horizon` missing entirely | Inputs HARD STOP — ask, no Analyze |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
