# system-design

Turns an approved architecture decision (from `architecture-review`) or a PRD into an
implementation-oriented technical design: component boundaries, API and event surface, data model, state
machines, consistency and retry/idempotency strategy, rough capacity, failure strategy, observability, and
a phased rollout plan.

The skill's only output is `SYSTEM_DESIGN_SPEC.md` — a Readiness-verdict report (`Ready to implement |
Ready with open questions | Not ready`) with one section per design dimension, each populated or marked as
an explicit Open question. It never edits code, posts anywhere, or writes tickets.

## When to use

- An architecture decision has been approved and needs to become a concrete component/API/data-model
  design before implementation starts.
- A PRD needs a technical design doc: state machines, consistency model, retry strategy, rollout plan.
- You need a rough capacity estimate, failure-mode strategy, or observability plan alongside a new design.
- You need a phased rollout/migration plan (feature flags, migration order) for a new implementation.

## Install

```bash
cd software-builder
make install-system-design
```

See [SETUP.md](SETUP.md) for Claude Code and Kiro/Cursor install variants.

## Pipeline

`Inputs → Analyze → Report`

See [SKILL.md](SKILL.md) for the full contract, required inputs, and cross-skill escalation matrix.
