# performance-review

Reviews code, a query, or a service for performance regression risk — algorithmic complexity, database
access behavior, N+1 query patterns, caching correctness, memory allocation patterns, concurrency
hazards, connection pool sizing, and downstream call fanout — and produces a single verdict on whether
the reviewed content is safe to ship as-is.

Analysis is static-first: it works from the supplied code/query content alone, and gets sharper when
optional profiling/metrics excerpts corroborate what the code implies. Any area it can't evaluate is
reported as an explicit gap, never silently assumed clean.

## When to use

- Reviewing a function, query, or service change for performance regression risk before it ships.
- Checking for N+1 query patterns, cache correctness, or connection pool sizing.
- Evaluating profiling/metrics excerpts against the code that produced them.
- Not for turning demand/growth into forward capacity numbers — use **capacity-planner**.
- Not for reviewing schema/index design directly — use **database-review**.

## Install

```bash
cd software-builder
make install-performance-review
```

See [SETUP.md](SETUP.md) for full setup, prerequisites, and troubleshooting.

## Pipeline

`Inputs → Analyze → Report`

Agent instructions: [SKILL.md](SKILL.md).
