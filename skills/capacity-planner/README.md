# capacity-planner

Turn historical demand data — traffic/usage numbers, growth rate, seasonality — into forward-looking
capacity requirements: RPS and concurrency targets, CPU and memory sizing, database load, queue
throughput, storage growth, and replica-count requirements for a given forecast horizon.

Unlike a live rightsizing check, this is a **forecast**: every derived number is traced back to an
explicit assumption (growth rate, peak:average ratio, per-request resource cost) so the reader can see
exactly what the projection depends on, and any section without enough historical data to project from
is surfaced as an honest gap rather than a guess.

## When to use

- "What capacity do we need for 3x growth over the next 6 months?"
- Replica-count / headroom planning ahead of a launch, migration, or seasonal peak
- Turning a traffic-growth trend into CPU/memory/DB/queue/storage sizing targets
- Deciding whether current headroom is sufficient, marginal, or insufficient for a forecast horizon

## Install

```bash
make install-capacity-planner
```

Details: [SETUP.md](SETUP.md).

## Pipeline

```
Inputs → Analyze → Report
```

Agent instructions: [SKILL.md](SKILL.md).
