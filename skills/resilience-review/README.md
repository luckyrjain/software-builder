# resilience-review

Review a proposed design or current implementation for resilience and failure-mode behavior:
timeout budgets, retries, circuit breaking, load shedding, backpressure, queues, idempotency,
downstream/partial failures, and recovery. It lands on one of four verdicts — Approved, Approved
with conditions, Changes required, or Blocked — insufficient evidence — derived from evidence
against all ten resilience dimensions, never a checklist pass.

Unlike a generic PR review, a current candidate may only pass with repository or authoritative-host
evidence tied to its exact revision; caller-only material is corroboration, not authoritative pass
evidence, and missing required evidence fails closed to UNKNOWN rather than a silent pass.

## When to use

- Resilience or failure-mode review of a design or implementation outside a live incident
- Assess timeout, retry, circuit-breaker, queue, idempotency, and reconciliation controls before
  release
- Review a current candidate's resilience evidence against its exact revision

Not for: diagnosing a live incident (`incident-rca`), forecasting demand or headroom
(`capacity-planner`), Kubernetes rightsizing, or generic PR review (`pr-review` first).

Full routing table: [SKILL.md](SKILL.md#when-to-use-not-to-use).

## Install

```bash
make install-resilience-review
```

Details: [SETUP.md](SETUP.md).

## Pipeline

```
Inputs → Analyze → Report
```

Agent instructions: [SKILL.md](SKILL.md).
