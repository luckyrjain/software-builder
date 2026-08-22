# observability-review

Evaluate a service's **metrics, logs, tracing, dashboards, alerts, SLOs, and correlation IDs** for
coverage and gaps, and produce a single markdown coverage verdict — the review a team runs before the next
incident forces the question, not during one.

Every check is run against text/config the caller supplies (metrics definitions, log samples, tracing/span
config, dashboard definitions, alert rules, SLO definitions) — this skill never queries a live
metrics/logging/tracing backend itself, so its output is only as complete as the material it's given, and
it says so explicitly whenever a category has nothing to assess.

## When to use

- "Review our observability coverage for `<service>`"
- Alert-coverage or SLO-definition audit ahead of a launch or on-call handoff
- Tracing/correlation-ID propagation gap check across a critical path
- A postmortem action item to "improve observability" that needs a concrete gap list, not a vibe check

## Install

```bash
make install-observability-review
```

Details: [SETUP.md](SETUP.md).

## Pipeline

```
Inputs → Analyze → Report
```

Agent instructions: [SKILL.md](SKILL.md).
