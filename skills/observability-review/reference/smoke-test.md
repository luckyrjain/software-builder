# Smoke test — expected minimal output

Run after install and after any skill edit. Use a fixture service with real (or realistic sample)
`observability_material` covering all six categories — metrics definitions, a handful of structured log
lines, tracing/span config for at least one critical-path hop, one dashboard definition, at least one
alert rule, and one SLO definition — so the smoke run exercises every section, not just the empty-input
path.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> Review observability coverage for `checkout-service` — metrics/logs/tracing/dashboards/alerts/SLOs
> attached below.

## A correct minimal output contains

1. **Phase announcement** — Inputs resolved (`service_name`, which categories of `observability_material`
   were supplied, `critical_path` supplied or inferred) before Analyze starts.
2. **Scope announcement** — which of the seven categories (Metrics, Logs, Tracing, Dashboards, Alerts,
   SLOs, Correlation IDs) had material to assess vs. none supplied.
3. **Core findings** — every check in every section present as a row, clean (`Yes`/`Present`), gapped
   (`Partial`/`No`/`Missing`), or `Unknown` — never an omitted row.
4. **Report** — `OBSERVABILITY_REVIEW_REPORT.md` per [report-format.md](report-format.md), bold `Coverage:`
   verdict line first.
5. **Confirmation / next step** — a one-line pointer to the relevant cross-skill escalation
   (**incident-rca** or **deployment-risk-review**) when a finding matches one of the
   [SKILL.md](../SKILL.md) § Cross-skill escalation rows; otherwise none needed.

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| `service_name` or `observability_material` absent | Inputs HARD STOP — ask, no Analyze |
| `observability_material` supplied for only some categories (e.g. metrics + logs, no alert rules or SLOs) | Analyze records the uncovered categories as no-material; Report marks those sections `Unknown`, verdict at least `Unknown — insufficient input` unless a `Critical gaps` finding is separately proven elsewhere |
| `critical_path` not supplied and cannot be inferred from `observability_material` | Tracing and Correlation IDs sections note the scope as unconfirmed rather than assuming full coverage |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
